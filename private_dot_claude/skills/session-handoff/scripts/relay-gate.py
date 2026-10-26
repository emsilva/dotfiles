#!/usr/bin/env python3
"""Relay gate: fire /relay when a herdr lead reaches 50% context. A Claude Code hook.

  stop   Stop hook: at the first safe turn end at or above the threshold, block with "run /relay now"
  tool   PostToolUse hook: once per band, tell the lead a relay is due

On stop, an unnamed session that is the only agent in a project's main checkout is named lead-<project>.

Reads the hook's JSON on stdin and prints a hook decision, or nothing. It never fails closed: an error is
logged to <project>/relay/gate/errors.log, toasted once per session, and the call exits 0 with no output.
Only a lead (herdr name lead-*, or the session in <project>/relay/lead.json) is gated, and only a lead gets
a state file, <project>/relay/gate/<session-id>.json. Design: docs/superpowers/specs/2026-10-13-relay-gate-design.md.

Test-only overrides: RELAY_GATE_THRESHOLD, RELAY_GATE_CAP, RELAY_GATE_STEP, RELAY_GATE_BACKOFF_S,
RELAY_GATE_THROTTLE_S, RELAY_GATE_OWNER_S, RELAY_GATE_WINDOW (tokens).
"""
import datetime
import glob
import json
import math
import os
import subprocess
import sys
import time
import traceback

# In development this dir is chezmoi source: bytecode written beside the script would be deployed.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import relaylib  # noqa: E402
import transcript  # noqa: E402

HERDR_BOUND = 2            # seconds, any one herdr call
BUDGET = {'stop': 7, 'tool': 3}   # seconds of gathering, inside the 10 s and 5 s hook timeouts
PRUNE_AFTER = 7 * 24 * 3600
LOG_KEEP = 100 * 1024
HANDOVER_ALERT_AFTER = 30 * 60
OWNER_RECENT = 10 * 60
MAX_ASKS = 3
ASK_HOLD = 15 * 60         # seconds an ask holds the nudge: the lead may be running /relay before its relay dir exists
PENDING_EXPIRY = 120       # seconds a printed nudge waits for the transcript to confirm it; then it counts as delivered
NUDGE_MARK = 'relay-gate:'   # the nudge's prefix: its delivery is recognised by it in the transcript (settle)
STATE_TYPES = {'version': int, 'meter': (dict, type(None)), 'nudged': list, 'drain_owed': bool, 'alerted': list,
               'asked': (dict, type(None)), 'given_up': bool, 'handover_alerted': list, 'toasted': list,
               'pending': (dict, type(None)), 'hold': (dict, type(None))}


class Late(Exception):
    """The call ran past its budget: exit silently and let the next call decide."""


class Config:
    def __init__(self, env):
        self.threshold = number(env, 'RELAY_GATE_THRESHOLD', 50)
        self.cap = number(env, 'RELAY_GATE_CAP', 60)
        self.step = number(env, 'RELAY_GATE_STEP', 10)
        self.backoff = number(env, 'RELAY_GATE_BACKOFF_S', 1800)
        self.throttle = number(env, 'RELAY_GATE_THROTTLE_S', 60)
        self.owner = number(env, 'RELAY_GATE_OWNER_S', OWNER_RECENT)
        self.window = int(number(env, 'RELAY_GATE_WINDOW', 0)) or None


def number(env, name, default):
    """A positive number from the environment (an int when whole), else the default."""
    try:
        value = float(env.get(name, ''))
    except ValueError:
        return default
    if not value > 0 or math.isinf(value):
        return default
    return int(value) if value.is_integer() else value


class Clock:
    def __init__(self, budget):
        self.end = time.monotonic() + budget

    def left(self, cap):
        """Seconds a call may take: at most cap; Late once the budget is spent."""
        remaining = self.end - time.monotonic()
        if remaining <= 0:
            raise Late()
        return min(cap, remaining)


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')


def band_of(pct, cfg):
    """The band of a fill at or above the threshold: T + S * floor((F - T) / S)."""
    band = cfg.threshold + cfg.step * math.floor((pct - cfg.threshold) / cfg.step)
    return int(band) if float(band).is_integer() else band


def fresh():
    return {'version': 1, 'meter': None, 'nudged': [], 'drain_owed': False, 'alerted': [], 'asked': None,
            'given_up': False, 'handover_alerted': [], 'toasted': [], 'pending': None, 'hold': None}


def _shape_ok(state):
    for key, kind in STATE_TYPES.items():
        if not isinstance(state[key], kind) or (kind is int and isinstance(state[key], bool)):
            return False
    meter, asked, pending = state['meter'], state['asked'], state['pending']
    hold = state['hold']
    if hold is not None and not (isinstance(hold.get('reasons'), list) and hold['reasons']
                                 and all(isinstance(r, str) for r in hold['reasons'])
                                 and isinstance(hold.get('at'), str)):
        return False
    if meter is not None and not (isinstance(meter.get('pct'), (int, float)) and isinstance(meter.get('read_at'), str)):
        return False
    if asked is not None and not (isinstance(asked.get('band'), (int, float)) and isinstance(asked.get('attempt'), int)
                                  and isinstance(asked.get('tasks'), list) and isinstance(asked.get('count'), int)
                                  and isinstance(asked.get('at'), str)):
        return False
    if pending is not None and not (isinstance(pending.get('band'), (int, float))
                                    and not isinstance(pending['band'], bool)
                                    and isinstance(pending.get('tool_use_id'), str) and pending['tool_use_id']
                                    and isinstance(pending.get('drain'), bool) and isinstance(pending.get('at'), str)):
        return False
    return all(isinstance(b, (int, float)) for b in state['nudged'] + state['alerted'])


def load_state(path):
    """The state at path; a missing, unreadable or wrong-shaped file is a fresh state."""
    try:
        data = relaylib.read_json(path)
    except (OSError, ValueError):
        return fresh()
    if not isinstance(data, dict) or data.get('version') != 1:
        return fresh()
    state = dict(fresh(), **{k: v for k, v in data.items() if k in STATE_TYPES})
    return state if _shape_ok(state) else fresh()


def save_state(path, state):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = '%s.tmp.%d' % (path, os.getpid())
    with open(tmp, 'w') as fh:
        json.dump(state, fh)
    os.replace(tmp, path)


def prune(gate_dir, keep, now):
    """Remove other sessions' state files untouched for 7 days."""
    for path in glob.glob(os.path.join(glob.escape(gate_dir), '*.json')):
        if path != keep:
            try:
                if now - os.path.getmtime(path) > PRUNE_AFTER:
                    os.remove(path)
            except OSError:
                pass


def reset_bands(state, pct, cfg):
    """Forget the bands of a fuller context once the fill drops more than a step below them (a compaction)."""
    bands = state['nudged'] + state['alerted'] + [r['band'] for r in (state['asked'], state['pending']) if r]
    if bands and pct < min(bands) - cfg.step:
        state.update(nudged=[], alerted=[], asked=None, drain_owed=False, pending=None)
        return True
    return False


def herdr_name(pane, timeout):
    """The herdr name of the agent in pane, or None when it has none.

    HerdrError when herdr failed or was slow: that is not an unnamed agent, and must not be renamed."""
    try:
        r = subprocess.run(['herdr', 'agent', 'get', pane], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise relaylib.HerdrError('herdr agent get did not answer within %s s' % timeout)
    except Exception as e:
        # OSError is a missing herdr; a test (and only a test) makes Popen raise RuntimeError. Either way herdr
        # did not answer, which is not a gate bug.
        raise relaylib.HerdrError('herdr agent get: %s' % e)
    if r.returncode != 0:
        raise relaylib.HerdrError('herdr agent get exited %d' % r.returncode)
    try:
        result = json.loads(r.stdout).get('result')
        agent = result.get('agent') if isinstance(result, dict) else None
    except (ValueError, AttributeError):
        raise relaylib.HerdrError('herdr agent get printed no agent')
    if not isinstance(agent, dict):
        raise relaylib.HerdrError('herdr agent get printed no agent')
    name = agent.get('name')
    return name if isinstance(name, str) else None


def is_lead(call):
    """Whether this session is a lead: lead.json, or a herdr name starting with lead-.

    The name is Call.pane_name, read once per call. A herdr failure is not a lead by name."""
    try:
        lead = relaylib.read_json(os.path.join(call.project, 'relay', 'lead.json'))
        if isinstance(lead, dict) and lead.get('session_id') == call.session:
            return True
    except (OSError, ValueError):
        pass
    try:
        name = call.pane_name()
    except relaylib.HerdrError:
        return False
    return bool(name) and name.startswith('lead-')


def toast(title, body, where):
    """Fire and forget: the toast is never waited on, and its failure changes nothing but the error log.

    It runs after the decision is printed, so it never raises: a non-zero exit would make Claude Code drop a block
    the state already records (a NUL byte in a body raises ValueError, not OSError)."""
    try:
        subprocess.Popen(['herdr', 'notification', 'show', title, '--body', body, '--sound', 'request'],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except Exception:
        report_error(where, traceback.format_exc(), notify=False)


def trim(path, keep):
    if os.path.getsize(path) > keep:
        with open(path, 'rb') as fh:
            fh.seek(-keep, os.SEEK_END)
            tail = fh.read()
        with open(path, 'wb') as fh:
            fh.write(tail)


def report_error(where, text, notify=True):
    """Log the traceback; if notify, toast once per session (an O_EXCL marker, independent of the state).

    Never raises: it is the last resort of a hook that must not fail closed."""
    project, session = where.get('project'), where.get('session') or 'unknown'
    if project and os.path.isdir(project):
        log = os.path.join(project, 'relay', 'gate', 'errors.log')
        marker = os.path.join(project, 'relay', 'gate', session + '.error')
    else:
        log = os.path.expanduser('~/.claude/relay-gate-errors.log')
        marker = os.path.expanduser('~/.claude/relay-gate-%s.error' % session)
    try:
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, 'a') as fh:
            fh.write('== %s session %s\n%s\n' % (utc_now(), session, text.rstrip()))
        trim(log, LOG_KEEP)
        if not notify:
            return
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except Exception:
        return
    toast('Relay gate: error', 'The relay gate failed in session %s; see %s' % (session[:8], log), where)


class Call:
    """One hook call: its input, paths, settings and the toasts to raise after the output."""

    def __init__(self, inp, cfg, clock, now):
        self.inp, self.cfg, self.clock, self.now = inp, cfg, clock, now
        self.session = inp.get('session_id')
        self.transcript = inp.get('transcript_path')
        self.project = os.path.dirname(self.transcript)
        self.state_path = os.path.join(self.project, 'relay', 'gate', '%s.json' % self.session)
        self.pane = os.environ.get('HERDR_PANE_ID')
        self.label = os.path.basename((inp.get('cwd') or self.project).rstrip('/')) or 'lead'
        self.toasts = []
        self._lead = None
        self._name = None
        self._name_read = False
        self._name_error = None

    def pane_name(self):
        """This pane's herdr name, or None when it has none. Read once. HerdrError if herdr failed or was slow."""
        if self._name_read:
            if self._name_error is not None:
                raise self._name_error
            return self._name
        try:
            name = herdr_name(self.pane, self.clock.left(HERDR_BOUND))
        except relaylib.HerdrError as e:
            self._name_read = True
            self._name_error = e
            raise
        self._name_read = True
        self._name = name
        return name

    def lead(self):
        """Whether this session is a lead: checked once per call, since it cannot change within one."""
        if self._lead is None:
            self._lead = is_lead(self)
        return self._lead

    def alert(self, text, then):
        """An owner alert: a toast now, and a block asking the lead to push the same text."""
        self.toasts.append(('Relay gate: %s' % self.label, text))
        return {'decision': 'block', 'reason': (
            'relay-gate: %s Load the push tool with ToolSearch select:PushNotification and send the owner: "%s" '
            'Then %s.' % (text, text, then))}


def unknown_model(call):
    """A lead whose model has no known window: one tooling toast per session; otherwise inert."""
    model = transcript.last_model(call.transcript)
    if not model or call.cfg.window or model in transcript.WINDOWS or not call.lead():
        return
    state = load_state(call.state_path)
    if 'unknown-model' not in state['toasted']:
        state['toasted'].append('unknown-model')
        save_state(call.state_path, state)
        call.toasts.append(('Relay gate: %s' % call.label, 'Lead session %s runs %s, whose context window the relay '
                            'gate does not know: it will not relay this session automatically.'
                            % (call.session[:8], model)))


def below(call, pct):
    """Below the threshold: only an existing state (a lead) is touched, to forget bands after a drop."""
    if os.path.exists(call.state_path):
        state = load_state(call.state_path)
        if reset_bands(state, pct, call.cfg):
            save_state(call.state_path, state)


def main_checkout(cwd, timeout):
    """The absolute top of cwd's main working tree, or None.

    A linked worktree's git dir is not the common dir, so a herd builder never names itself. Git failing or not
    answering cannot tell: None, and the caller does nothing."""
    code, out = relaylib.run(
        ['git', '-C', cwd, 'rev-parse', '--show-toplevel', '--absolute-git-dir', '--git-common-dir'],
        timeout=timeout)
    if code != 0:
        return None
    lines = out.splitlines()
    if len(lines) != 3 or not all(lines):
        return None
    top, git_dir, common = lines
    if not os.path.isabs(common):
        common = os.path.join(cwd, common)   # relative --git-common-dir is relative to the -C directory
    if os.path.realpath(git_dir) != os.path.realpath(common):
        return None
    return os.path.realpath(top)


def _inside(path, root):
    """path is root, or a directory inside it. Both absolute, no trailing slash."""
    if path == root:
        return True
    return path.startswith('/' if root == '/' else root + '/')


def agent_place(agent):
    """Where the agent is working: foreground_cwd, or cwd when that is absent or empty."""
    if not isinstance(agent, dict):
        return None
    fg = agent.get('foreground_cwd')
    if isinstance(fg, str) and fg:
        return fg
    cwd = agent.get('cwd')
    return cwd if isinstance(cwd, str) and cwd else None


def in_checkout(path, top):
    """Whether path is the main checkout or inside it, and not under <top>/.claude/worktrees."""
    path = os.path.realpath(path).rstrip('/') or '/'
    root = top.rstrip('/') or '/'
    trees = os.path.join(root, '.claude', 'worktrees')
    if _inside(path, trees):
        return False
    return _inside(path, root)


def other_in_checkout(agent, pane, top):
    if not isinstance(agent, dict) or agent.get('pane_id') == pane:
        return False
    place = agent_place(agent)
    return bool(place) and in_checkout(place, top)


def lead_named_here(agent, top):
    if not isinstance(agent, dict):
        return False
    name = agent.get('name')
    place = agent_place(agent)
    return isinstance(name, str) and name.startswith('lead-') and bool(place) and in_checkout(place, top)


def tell_shared(call, top, target):
    """One toast per session when several agents share a checkout and none is named lead-…. Not the state file."""
    marker = os.path.join(call.project, 'relay', 'gate', '%s.autoname' % call.session)
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except OSError:
        return
    call.toasts.append(('Relay gate: %s' % call.label,
                         'Two or more sessions share %s and none is named lead-…; name the lead with '
                         'herdr agent rename %s %s.' % (top, call.pane, target)))


def maybe_name_lead(call):
    """Name an unnamed session lead-<project> when it is the only agent in a main checkout.

    Before the fill is read, so it does not depend on context use. A herdr or git failure leaves the name unset;
    the next turn end tries again. Late propagates. Any other error is reported, and the call prints nothing."""
    try:
        _name_if_only(call)
    except Late:
        raise
    except relaylib.HerdrError:
        return
    except Exception:
        report_error({'project': call.project, 'session': call.session}, traceback.format_exc())


def _name_if_only(call):
    if call.pane_name() is not None:   # any name, whatever it is: never rename a named agent
        return
    cwd = call.inp.get('cwd')
    if not isinstance(cwd, str) or not cwd:
        return
    top = main_checkout(cwd, call.clock.left(relaylib.GIT_BOUND))
    if not top:
        return
    target = relaylib.lead_name(top)
    agents = relaylib.herdr_list('agents', 'agent', 'list', timeout=call.clock.left(HERDR_BOUND))
    if any(other_in_checkout(agent, call.pane, top) for agent in agents):
        if not any(lead_named_here(agent, top) for agent in agents):
            tell_shared(call, top, target)
        return
    if any(isinstance(agent, dict) and agent.get('name') == target for agent in agents):
        return
    relaylib.herdr_text('agent', 'rename', call.pane, target, timeout=call.clock.left(HERDR_BOUND))
    call._lead = True
    call.toasts.append(('Relay gate: %s' % call.label,
                         'Named this session %s: it is the only agent in %s.' % (target, top)))


def stop(call):
    maybe_name_lead(call)   # before the fill: naming does not depend on context use
    cfg = call.cfg
    fill = transcript.context_fill(call.transcript, cfg.window)
    if fill is None:
        unknown_model(call)
        return None
    pct = fill['pct']
    if pct < cfg.threshold:
        below(call, pct)
        return None
    if not call.lead():
        return None
    state = load_state(call.state_path)
    prune(os.path.dirname(call.state_path), call.state_path, call.now)
    return commit(call, state, pct, decide)


def commit(call, state, pct, rule):
    """Meter a lead's state at pct, let rule (decide or nudge) rule on its band, and save the state.

    Nothing is printed or recorded for a session that is not a lead now: a state file outlives a lead (lead.json
    names another session, the pane is renamed). Stop has always checked by now, and so has tool mode for a session
    with no state file; Call.lead() remembers the answer, so the check costs a lookup only when a known session's
    nudge is due."""
    band = band_of(pct, call.cfg)
    reset_bands(state, pct, call.cfg)
    state['meter'] = {'pct': round(pct, 1), 'read_at': utc_now()}
    out = rule(call, state, pct, band)
    if out is not None and not call.lead():
        return None
    call.clock.left(HERDR_BOUND)   # past the budget: say nothing and record nothing
    save_state(call.state_path, state)
    return out


def relay_hold(relays, cfg, now):
    """What in this session's relays holds the gate, or None; the first of, in order:

    in_progress, frozen, handover (a hand-over-stage failure: never retried), given_up (two failures, or one that
    will repeat), backoff (one failure, younger than the back-off)."""
    if any(r['state'] == 'in_progress' for r in relays):
        return 'in_progress'
    if any(r['state'] == 'frozen' for r in relays):
        return 'frozen'
    failures = failures_of(relays)
    if any(r['stage'] == 'handover' for r in failures):
        return 'handover'
    if len(failures) >= 2 or any(relaylib.will_repeat(r) for r in failures):
        return 'given_up'
    if failures and now - failures[0]['failed_at'] < cfg.backoff:
        return 'backoff'
    return None


def decide(call, state, pct, band):
    """The Stop decision for a gated lead at pct in band; mutates state."""
    cfg, now = call.cfg, call.now
    relays = relaylib.relays_of(call.project, call.session, now)
    failures = failures_of(relays)
    hold = relay_hold(relays, cfg, now)
    state['hold'] = {'reasons': ['relay_hold:' + hold], 'at': utc_now()} if hold else None
    if hold == 'frozen':
        for r in relays:
            if r['state'] == 'frozen' and now - r['handover_at'] >= HANDOVER_ALERT_AFTER \
                    and r['id'] not in state['handover_alerted']:
                state['handover_alerted'].append(r['id'])
                return call.alert('The hand-over of relay %s is not closed after %d minutes: the successor never '
                                  'closed this session.' % (r['id'], (now - r['handover_at']) // 60), 'end your turn')
    if hold == 'given_up' and not state['given_up']:
        state['given_up'] = True
        return call.alert('Automatic relays of lead %s failed (%s) and will not be retried; run /relay by hand.'
                          % (call.label, ', '.join(r['id'] for r in failures)), 'end your turn')
    if hold:
        return None
    attempt = 1 + len(failures)
    tasks = call.inp.get('background_tasks')
    reasons = unsafe(call, tasks)
    if reasons:
        state['hold'] = {'reasons': reasons, 'at': utc_now()}
        if band < cfg.cap:
            pending = state['pending']    # printed, not yet confirmed: if lost, tool mode prints the band again anyway
            if band not in state['nudged'] and not (pending and pending['band'] == band):
                state['drain_owed'] = True
            return None
        if band in state['alerted']:
            return None
        state['alerted'].append(band)
        return call.alert('Lead %s is at %d%% and cannot relay yet: %s.' % (call.label, pct, '; '.join(reasons)),
                          'keep draining (start nothing new in-session) and end your turn; do not run /relay yet')
    if band < cfg.cap and owner_recent(call):
        state['hold'] = {'reasons': ['owner_recent'], 'at': utc_now()}
        return None
    open_tasks = [t for t in tasks if isinstance(t, dict) and t.get('status') not in transcript.TERMINAL]
    ids = sorted(str(t.get('id')) for t in open_tasks)
    asked = state['asked']
    count, asked_band = 1, band
    if asked and asked['attempt'] == attempt and band <= asked['band']:    # only a rise asks again
        if asked['count'] >= MAX_ASKS or all(i in ids for i in asked['tasks']):
            return None
        count, asked_band = asked['count'] + 1, asked['band']    # after a fall, going back up is no rise
    state['asked'] = {'band': asked_band, 'attempt': attempt, 'tasks': ids, 'count': count, 'at': utc_now()}
    state['drain_owed'] = False    # the lead is asked to relay, not to drain
    listing = '; '.join("%s '%s' (%s)" % (t.get('id'), t.get('description') or t.get('command') or '', t.get('type'))
                        for t in open_tasks) or 'none'
    reason = ('relay-gate: context is %d%% (threshold %s%%). Run /relay now, automatic relay attempt %d of 2. '
              'Open background tasks: %s. The successor re-arms waiters. If one of them is long work that must '
              'finish first, end your turn instead: the gate asks again when a listed task closes or the next band '
              'starts.' % (pct, cfg.threshold, attempt, listing))
    if band >= cfg.cap and band not in state['alerted']:
        state['alerted'].append(band)
        text = 'Lead %s is at %d%% and has not relayed yet; the gate asked it to run /relay.' % (call.label, pct)
        call.toasts.append(('Relay gate: %s' % call.label, text))
        reason += (' Also load the push tool with ToolSearch select:PushNotification and send the owner: "%s"'
                   % text)
    return {'decision': 'block', 'reason': reason}


def failures_of(relays):
    return [r for r in relays if r['state'] in ('failed', 'abandoned')]


def unsafe(call, tasks):
    """Why a relay cannot start now, or []: the same rules as relay-check.py checklist, plus the live task list."""
    if not isinstance(tasks, list):
        return ['the hook input carries no background task list']
    out = []
    for t in tasks:
        if not isinstance(t, dict):    # unknown counts as not safe
            out.append('background task entry %s is not a JSON object' % repr(t)[:60])
        elif t.get('status') not in transcript.TERMINAL and t.get('type') != 'shell':
            out.append('%s %s is running (%s)' % (t.get('type'), t.get('id'), t.get('description') or ''))
    repo = call.inp.get('cwd') or call.project
    return out + relaylib.blockers(repo, transcript.open_tasks([call.transcript]))


def owner_recent(call):
    for p in transcript.prompts(call.transcript):
        when = transcript.epoch(p['timestamp'])
        if when is not None and call.now - when < call.cfg.owner:
            return True
    return False


def tool(call):
    cfg = call.cfg
    known = os.path.exists(call.state_path)
    state = load_state(call.state_path) if known else None
    if state and not state['drain_owed'] and state['meter']:
        read = transcript.epoch(state['meter']['read_at'])
        if read is not None and call.now - read < cfg.throttle:
            return None
    fill = transcript.context_fill(call.transcript, cfg.window)
    if fill is None:
        return None
    pct = fill['pct']
    if pct < cfg.threshold:
        if state is not None:
            reset_bands(state, pct, cfg)
            state['meter'] = {'pct': round(pct, 1), 'read_at': utc_now()}
            save_state(call.state_path, state)
        return None
    if state is None:
        if not call.lead():
            return None
        state = fresh()
    return commit(call, state, pct, nudge)


def asked_lately(call, state, relays):
    """Whether Stop asked for /relay in the current attempt less than ASK_HOLD ago. The lead may be running it, and
    nothing shows that until checklist writes the relay dir (relay_hold covers the time after)."""
    asked = state['asked']
    if not asked or asked['attempt'] != 1 + len(failures_of(relays)):
        return False
    at = transcript.epoch(asked['at'])
    return at is not None and call.now - at < ASK_HOLD


def settle(call, state):
    """Resolve the pending nudge from the transcript; False while it still awaits its outcome.

    Delivered counts its band (and a drain nudge pays drain_owed). Cancelled (Claude Code killed the hook past its
    timeout and dropped the output) counts nothing, so it may be printed again. Neither, PENDING_EXPIRY after it was
    printed (or with a time that is unreadable or in the future), counts as delivered: a transcript the gate cannot
    read degrades to one print per band, never to a reprint every few minutes."""
    pending = state['pending']
    outcome = transcript.hook_outcome(call.transcript, pending['tool_use_id'], NUDGE_MARK)
    if outcome is None:
        at = transcript.epoch(pending['at'])
        # Aged by the clock now, not call.now: a parallel call may have saved this nudge after this call began.
        if at is not None and 0 <= time.time() - at < PENDING_EXPIRY:
            return False
        outcome = 'delivered'
    if outcome == 'delivered':
        if pending['band'] not in state['nudged']:
            state['nudged'].append(pending['band'])
        if pending['drain']:
            state['drain_owed'] = False
    state['pending'] = None
    return True


def nudge(call, state, pct, band):
    relays = relaylib.relays_of(call.project, call.session, call.now)
    hold = relay_hold(relays, call.cfg, call.now)
    if hold:
        state['hold'] = {'reasons': ['relay_hold:' + hold], 'at': utc_now()}
    if hold or state['given_up'] or asked_lately(call, state, relays):
        return None
    if state['pending'] and not settle(call, state):
        return None    # one nudge awaits its outcome: print nothing, even for a higher band
    if band in state['nudged'] and not state['drain_owed']:
        return None
    tid = call.inp.get('tool_use_id')
    if isinstance(tid, str) and tid:    # it counts once the transcript shows it delivered (settle)
        state['pending'] = {'band': band, 'tool_use_id': tid, 'drain': state['drain_owed'], 'at': utc_now()}
    else:    # nothing to confirm it by: count it now
        if band not in state['nudged']:
            state['nudged'].append(band)
        state['drain_owed'] = False
    return {'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': NUDGE_MARK + (
        ' context is %d%%. A relay is due. Finish the current step, start nothing new in-session (no subagents, no '
        'attached runs), then end your turn; the gate runs /relay at turn end.' % pct)}}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if len(argv) == 1 else None
    if mode not in BUDGET:
        print('usage: relay-gate.py stop|tool (a Claude Code hook; reads the hook JSON on stdin)', file=sys.stderr)
        return 1    # a hook's exit 2 would block the session: a usage error must not
    if os.environ.get('HERDR_ENV') != '1' or not os.environ.get('HERDR_PANE_ID'):
        return 0
    where = {}
    call = None
    try:
        inp = json.loads(sys.stdin.read())
        if not isinstance(inp, dict):
            raise ValueError('the hook input is not a JSON object')
        if inp.get('agent_id'):
            return 0
        where['session'] = inp.get('session_id') if isinstance(inp.get('session_id'), str) else None
        path = inp.get('transcript_path')
        if not where['session'] or not isinstance(path, str) or not path:
            return 0
        where['project'] = os.path.dirname(path)
        call = Call(inp, Config(os.environ), Clock(BUDGET[mode]), time.time())
        out = (stop if mode == 'stop' else tool)(call)
    except Late:
        return 0
    except Exception:
        report_error(where, traceback.format_exc())
        return 0
    if out is not None:
        sys.stdout.write(json.dumps(out))
        sys.stdout.flush()
    for title, body in call.toasts:
        toast(title, body, where)
    return 0


if __name__ == '__main__':
    sys.exit(main())
