"""Read a Claude Code session transcript (JSONL) the way the relay scripts need it.

Stdlib only. The CLIs run under `python3 -I`, which leaves the script's own
directory off sys.path, so each CLI inserts it before importing this module.

Record formats, verified on Claude Code 2.1.296 (2026-10-12):
- A background launch is read from the structured `toolUseResult` on the user
  record answering the tool call, never from the result text, which varies
  (a `Shell cwd was reset` prefix, timeouts, moves to deliver a message) and
  can be quoted by any other tool. Measured read-only over 2,545 transcripts
  (2.1.266 to 2.1.296), with no user record holding more than one tool_result
  (0 of 85,224):
  - Bash: `backgroundTaskId`, on 2,357 of 2,357 launches; never on another tool.
  - Monitor: `taskId`, on 137 of 137 launches.
  - Workflow: `taskId` with status "async_launched", on 29 of 29 launches.
  - Agent: `agentId` with status "async_launched", on 589 of 589 launches, 418
    of them without run_in_background. A `teammate_spawned` result instead
    carries snake-case `agent_id` / `teammate_id`; it is an in-session teammate.
- A task closes on a notification: a `user` record whose origin.kind is
  "task-notification", or a `queue-operation` record, whose text starts with
  <task-notification>. Only its header is read (the tags before the first
  <summary>, <result>, <event>, <note>, <diagnostics> or the closing tag): it
  closes the one <task-id> there when the header's <status> is terminal.
  Payloads quote other tasks' tags, and monitor events carry no <status>. A
  task also closes on a TaskStop result `Successfully stopped task: <id>`.
  `attachment` records are never read for a close: prompt snapshots quote
  notifications verbatim.
- What became of a hook's output for one tool call is read from the
  `attachment` object naming that call's `toolUseID` (2.1.296, 2026-10-13):
  type `hook_additional_context` (delivered; `content` a list of strings) or
  `hook_cancelled` (Claude Code killed the hook past its timeout and dropped
  its output).
- Typed prompts (by the owner, or by herdr into the pane) are `user` records
  whose origin.kind is "human", or `queue-operation` enqueues while busy.
- A cron is read from the structured `toolUseResult.id`, never from the result
  text: a recurring create reads `Scheduled recurring job <id>` and a one-shot
  `Scheduled one-shot task <id>`, so a text pattern missed every recurring cron.
  Measured 2026-10-13 over every local transcript (2.1.273 to 2.1.296): `id` on
  58 of 58 CronCreate and 52 of 52 CronDelete successes; the one failed delete
  carries an error string instead.
- Context fill is read from the newest main-thread assistant record's last
  `usage.iterations` entry of type `message`: input + cache_read +
  cache_creation. The top-level usage sums every iteration, so an advisor turn
  counts the context twice (57.9% shown for 29.2% real, 2026-10-12).
"""
import datetime
import glob
import json
import os
import re

PROJECTS = os.path.expanduser('~/.claude/projects')

# tool name -> (kind, toolUseResult field holding the task id, status the result must carry or None)
LAUNCHES = {
    'Bash': ('shell', 'backgroundTaskId', None),
    'Monitor': ('monitor', 'taskId', None),
    'Workflow': ('workflow', 'taskId', 'async_launched'),
    'Agent': ('agent', 'agentId', 'async_launched'),
}
NOTICE_START = '<task-notification>'
HEADER_END = re.compile(r'<(?:summary|result|event|note|diagnostics)>|</task-notification>')
TASK_ID = re.compile(r'<task-id>(\w+)</task-id>')
STATUS = re.compile(r'<status>(\w+)</status>')
STOPPED = re.compile(r'Successfully stopped task: (\w+)')
TERMINAL = frozenset({'completed', 'failed', 'killed', 'stopped'})
# Context window per model id, in tokens: only measured ones. An unknown model has no fill.
WINDOWS = {'claude-opus-5-5': 1_000_000}
FILL_KEYS = ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')


def find_transcript(session_id, projects=PROJECTS):
    hits = glob.glob(os.path.join(glob.escape(projects), '*', session_id + '.jsonl'))
    if len(hits) != 1:
        raise LookupError('expected one transcript for session %s under %s, found %d'
                          % (session_id, projects, len(hits)))
    return hits[0]


def records(path, until_line=None):
    """Yield (line_index, record) for each parseable line; a torn last write is skipped."""
    with open(path, encoding='utf-8', errors='replace') as fh:
        for i, line in enumerate(fh):
            if until_line is not None and i > until_line:
                return
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict):
                yield i, rec


def epoch(timestamp):
    try:
        return datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()
    except (AttributeError, ValueError):
        return None


def _blocks(rec):
    content = (rec.get('message') or {}).get('content')
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ' '.join(b.get('text', '') for b in value if isinstance(b, dict))
    return ''


def _user_text(rec):
    content = (rec.get('message') or {}).get('content')
    if isinstance(content, str):
        return content
    return _text([b for b in _blocks(rec) if b.get('type') == 'text'])


def _launch(name, rec):
    """(kind, task id) when the record answering a `name` call says it started a background task."""
    kind, field, status = LAUNCHES.get(name, (None, None, None))
    result = rec.get('toolUseResult')
    if name == 'Agent' and isinstance(result, dict) and result.get('status') == 'teammate_spawned':
        task_id = result.get('agent_id') or result.get('teammate_id')
        return ('teammate', task_id) if isinstance(task_id, str) and task_id else None
    if kind is None or not isinstance(result, dict) or (status and result.get('status') != status):
        return None
    task_id = result.get(field)
    return (kind, task_id) if isinstance(task_id, str) and task_id else None


def _events(paths, until_line=None):
    """Yield (path, line, record, call) per record, then per answered tool call.

    call is None for the record itself, or (tool name, tool input, result text)
    for each tool_result whose tool_use was seen earlier in the same file.
    Paths are read in order; until_line applies to the last one.
    """
    for n, path in enumerate(paths):
        limit = until_line if n == len(paths) - 1 else None
        calls = {}
        for i, rec in records(path, limit):
            if rec.get('type') == 'assistant':
                for b in _blocks(rec):
                    if b.get('type') == 'tool_use':
                        calls[b.get('id')] = (b.get('name'), b.get('input') or {})
            yield path, i, rec, None
            if rec.get('type') == 'user':
                for b in _blocks(rec):
                    if b.get('type') == 'tool_result' and b.get('tool_use_id') in calls:
                        name, args = calls[b['tool_use_id']]
                        yield path, i, rec, (name, args, _text(b.get('content')))


def _is_notice(text):
    return text.lstrip().startswith(NOTICE_START)


def _closed_by_notice(rec):
    """The task id a notification record closes, read from its header only; else None."""
    if rec.get('type') == 'user' and (rec.get('origin') or {}).get('kind') == 'task-notification':
        text = _user_text(rec)
    elif rec.get('type') == 'queue-operation':
        text = str(rec.get('content', ''))
    else:
        return None
    if not _is_notice(text):
        return None
    end = HEADER_END.search(text)
    header = text[:end.start()] if end else text
    task, status = TASK_ID.search(header), STATUS.search(header)
    return task.group(1) if task and status and status.group(1) in TERMINAL else None


def open_tasks(paths, until_line=None):
    """Background tasks launched in these transcripts and not closed in them.

    paths: oldest first (a pre-/clear transcript, then the session's own).
    """
    launched, closed = {}, set()
    for path, line, rec, call in _events(paths, until_line):
        if call is None:
            closed.update(filter(None, [_closed_by_notice(rec)]))
            continue
        name, args, result = call
        if name == 'TaskStop':
            closed.update(STOPPED.findall(result))
            continue
        launch = _launch(name, rec)
        if launch:
            kind, task_id = launch
            launched[task_id] = {
                'id': task_id, 'kind': kind, 'description': args.get('description', ''),
                'command': args.get('command', ''), 'started_at': rec.get('timestamp', ''),
                'transcript': path, 'line': line}
    return [task for tid, task in launched.items() if tid not in closed]


def open_crons(paths, until_line=None):
    """Session crons created and not deleted in these transcripts (a fired one-shot is still listed)."""
    made, gone = {}, set()
    for _, _, rec, call in _events(paths, until_line):
        if call is None or call[0] not in ('CronCreate', 'CronDelete'):
            continue
        name, args, _ = call
        result = rec.get('toolUseResult')
        cron_id = result.get('id') if isinstance(result, dict) else None
        if not isinstance(cron_id, str) or not cron_id:
            continue
        if name == 'CronCreate':
            made[cron_id] = {'id': cron_id, 'cron': args.get('cron', ''), 'prompt': args.get('prompt', ''),
                             'recurring': args.get('recurring', True) is not False}
        else:
            gone.add(cron_id)
    return [cron for cid, cron in made.items() if cid not in gone]


def prompts(path):
    """Prompts typed into the session (by the owner, or by herdr into its pane), oldest first."""
    out = []
    for i, rec in records(path):
        kind = rec.get('type')
        if kind == 'user' and (rec.get('origin') or {}).get('kind') == 'human':
            out.append({'line': i, 'timestamp': rec.get('timestamp', ''), 'text': _user_text(rec)})
        elif kind == 'queue-operation' and rec.get('operation') == 'enqueue':
            text = str(rec.get('content', ''))
            if not _is_notice(text):
                out.append({'line': i, 'timestamp': rec.get('timestamp', ''), 'text': text})
    return out


def hook_outcome(path, tool_use_id, marker):
    """What became of a hook's output after the tool call tool_use_id: 'delivered', 'cancelled' or None (neither yet).

    Delivered: a hook_additional_context attachment whose content contains marker (another hook's context for the
    same call is not ours). Cancelled: a hook_cancelled attachment. Delivered wins over cancelled."""
    outcome = None
    for _, rec in records(path):
        att = rec.get('attachment')
        if not isinstance(att, dict) or att.get('toolUseID') != tool_use_id:
            continue
        if att.get('type') == 'hook_additional_context':
            content = att.get('content')
            parts = [content] if isinstance(content, str) else content if isinstance(content, list) else []
            if any(isinstance(p, str) and marker in p for p in parts):
                return 'delivered'
        elif att.get('type') == 'hook_cancelled':
            outcome = 'cancelled'
    return outcome


def last_model(path):
    model = None
    for _, rec in records(path):
        if rec.get('type') == 'assistant' and not rec.get('isSidechain'):
            value = (rec.get('message') or {}).get('model')
            if value and not value.startswith('<'):
                model = value
    return model


def context_fill(path, window=None):
    """How full the session's context is: {'pct', 'tokens', 'model'}, or None.

    None when no main-thread assistant record carries usage, or the window is unknown. window (tokens)
    overrides WINDOWS; the relay gate passes RELAY_GATE_WINDOW."""
    last = None
    for _, rec in records(path):
        if rec.get('type') == 'assistant' and not rec.get('isSidechain'):
            msg = rec.get('message') or {}
            model = msg.get('model')
            if isinstance(msg.get('usage'), dict) and isinstance(model, str) and model and not model.startswith('<'):
                last = msg
    if last is None:
        return None
    usage = last['usage']
    steps = [i for i in usage.get('iterations') or [] if isinstance(i, dict) and i.get('type') == 'message']
    source = steps[-1] if steps else usage
    tokens = sum(v for v in (source.get(k) for k in FILL_KEYS) if isinstance(v, int) and not isinstance(v, bool))
    size = window or WINDOWS.get(last['model'])
    if not size:
        return None
    return {'pct': 100.0 * tokens / size, 'tokens': tokens, 'model': last['model']}


def permission_mode(path):
    mode = None
    for _, rec in records(path):
        if rec.get('type') == 'permission-mode' and rec.get('permissionMode'):
            mode = rec['permissionMode']
    return mode


def first_timestamp(path):
    for _, rec in records(path):
        if rec.get('timestamp'):
            return rec['timestamp']
    return None
