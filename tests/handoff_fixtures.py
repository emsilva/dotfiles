"""Shared fixtures for the session-handoff script tests: transcript records and a fake herdr."""
import json
import os
from pathlib import Path
import stat
import sys

# Test modules import the scripts in-process; bytecode beside them in the chezmoi source would be deployed.
sys.dont_write_bytecode = True

SOURCE = Path(__file__).resolve().parents[1]
SCRIPTS = SOURCE / 'private_dot_claude/skills/session-handoff/scripts'


def ts(second):
    return '2026-10-12T20:%02d:%02d.000Z' % (second // 60, second % 60)


def tool_use(tid, name, args, second=0):
    return {'type': 'assistant', 'timestamp': ts(second), 'isSidechain': False,
            'message': {'model': 'claude-opus-5-5', 'content': [
                {'type': 'tool_use', 'id': tid, 'name': name, 'input': args}]}}


def tool_result(tid, text, second=0, tool_use_result=None):
    """tool_use_result: the record's structured `toolUseResult` (e.g. {'backgroundTaskId': id})."""
    rec = {'type': 'user', 'timestamp': ts(second),
           'message': {'content': [{'type': 'tool_result', 'tool_use_id': tid, 'content': text}]}}
    if tool_use_result is not None:
        rec['toolUseResult'] = tool_use_result
    return rec


def cron_create(tid, cron_id, cron, prompt_text, recurring=True, second=0):
    """A CronCreate call and its result as Claude Code 2.1.296 writes them: the text says `job` for a
    recurring cron and `task` for a one-shot, so only toolUseResult.id names the cron reliably."""
    text = ('Scheduled recurring job %s (%s). Session-only (not written to disk, dies when Claude exits). '
            'Auto-expires after 7 days. Use CronDelete to cancel sooner.' % (cron_id, cron) if recurring else
            'Scheduled one-shot task %s (%s). Session-only (not written to disk, dies when Claude exits). '
            'It will fire once then auto-delete.' % (cron_id, cron))
    return [tool_use(tid, 'CronCreate', {'cron': cron, 'prompt': prompt_text, 'recurring': recurring}, second),
            tool_result(tid, text, second, tool_use_result={'id': cron_id, 'humanSchedule': cron,
                                                            'recurring': recurring, 'durable': False})]


def cron_delete(tid, cron_id, second=0, found=True):
    """A CronDelete call and its result; a delete of an unknown id carries an error string, not an id."""
    if found:
        result = tool_result(tid, 'Cancelled job %s.' % cron_id, second, tool_use_result={'id': cron_id})
    else:
        result = tool_result(tid, "<tool_use_error>No scheduled job with id '%s'</tool_use_error>" % cron_id,
                             second, tool_use_result="Error: No scheduled job with id '%s'" % cron_id)
    return [tool_use(tid, 'CronDelete', {'id': cron_id}, second), result]


def cron_fire(cron_id, prompt_text, second=0, head=None, origin_null=False):
    """An enqueued cron delivery: enqueue, dequeue, scheduled_task_fire, system-sourced user.

    The fire can store only the prompt's 200-character head. Its timestamp precedes the enqueue's even though
    it is written afterward; association must use record order. Old deliveries omit origin; newer ones set null.
    """
    delivered = {'type': 'user', 'timestamp': ts(second + 2), 'promptSource': 'system', 'isMeta': True,
                 'scheduledTaskId': cron_id, 'scheduledFireId': 'fire-' + cron_id,
                 'message': {'content': prompt_text}}
    if origin_null:
        delivered['origin'] = None
    return [{'type': 'queue-operation', 'operation': 'enqueue', 'timestamp': ts(second + 1),
             'content': prompt_text},
            {'type': 'queue-operation', 'operation': 'dequeue', 'timestamp': ts(second + 1)},
            {'type': 'system', 'subtype': 'scheduled_task_fire', 'timestamp': ts(second),
             'cron': '*/20 * * * *', 'taskId': cron_id,
             'prompt': prompt_text if head is None else prompt_text[:head]}, delivered]


def usage(message_tokens, second=0, model='claude-opus-5-5', advisor=False, sidechain=False):
    """A main-thread assistant record carrying usage as Claude Code 2.1.296 writes it.

    message_tokens: the context of the final API call (input + cache_read + cache_creation of the last
    `message` iteration). advisor=True adds an earlier `message` iteration and an `advisor_message` one, as an
    advisor turn does, so the top-level usage (the sum of the message iterations) reads about twice the context."""
    last = {'type': 'message', 'input_tokens': 2, 'cache_read_input_tokens': message_tokens - 1002,
            'cache_creation_input_tokens': 1000, 'output_tokens': 50}
    steps = [last]
    if advisor:
        steps = [dict(last, cache_read_input_tokens=message_tokens - 3002),
                 {'type': 'advisor_message', 'input_tokens': 91782, 'cache_read_input_tokens': 0,
                  'cache_creation_input_tokens': 0, 'output_tokens': 4394}, last]
    top = {k: sum(s[k] for s in steps if s['type'] == 'message')
           for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens')}
    return {'type': 'assistant', 'timestamp': ts(second), 'isSidechain': sidechain,
            'message': {'model': model, 'content': [], 'usage': dict(top, iterations=steps)}}


def _notice_text(task_id, status, payload=None):
    """A terminal notice as Claude Code 2.1.296 writes it: header tags, then the payload."""
    if payload is None:
        payload = '<summary>Background task "%s" %s</summary>\n<event>exit 0</event>' % (task_id, status)
    return ('<task-notification>\n<task-id>%s</task-id>\n<tool-use-id>toolu_%s</tool-use-id>\n'
            '<output-file>/tmp/x/%s.output</output-file>\n<status>%s</status>\n%s\n</task-notification>'
            % (task_id, task_id, task_id, status, payload))


def notice(task_id, status, second=0, payload=None):
    return {'type': 'user', 'timestamp': ts(second), 'origin': {'kind': 'task-notification'},
            'message': {'content': _notice_text(task_id, status, payload)}}


def queued_notice(task_id, status, second=0, payload=None):
    return {'type': 'queue-operation', 'operation': 'enqueue', 'timestamp': ts(second),
            'content': _notice_text(task_id, status, payload)}


def monitor_event(task_id, event_text, second=0):
    """A monitor's event notice: no <status> in the header, the event text is the payload."""
    return {'type': 'user', 'timestamp': ts(second), 'origin': {'kind': 'task-notification'},
            'message': {'content': '<task-notification>\n<task-id>%s</task-id>\n<summary>Monitor event: '
                        '"watch"</summary>\n<event>%s</event>\n</task-notification>' % (task_id, event_text)}}


def hook_context(tool_use_id, content, hook='PostToolUse:Bash'):
    """A PostToolUse hook's additionalContext as Claude Code 2.1.296 records its delivery: content is a list of
    strings, and the attachment names the tool call it followed."""
    return {'type': 'attachment', 'attachment': {'type': 'hook_additional_context', 'hookName': hook,
                                                 'hookEvent': 'PostToolUse', 'toolUseID': tool_use_id,
                                                 'content': content}}


def hook_cancelled(tool_use_id, hook='PostToolUse:Bash'):
    """A PostToolUse hook Claude Code killed past its timeout: its output was discarded, never delivered."""
    return {'type': 'attachment', 'attachment': {'type': 'hook_cancelled', 'hookName': hook,
                                                 'hookEvent': 'PostToolUse', 'toolUseID': tool_use_id}}


def prompt(text, second=0, source='typed'):
    return {'type': 'user', 'timestamp': ts(second), 'origin': {'kind': 'human'},
            'promptSource': source, 'message': {'content': text}}


def write_transcript(projects, session_id, recs, torn_tail=False, project='-tmp-repo'):
    path = Path(projects) / project / (session_id + '.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as fh:
        for rec in recs:
            fh.write(json.dumps(rec) + '\n')
        if torn_tail:
            fh.write('{"type": "assistant", "message": {"content": [')
    return path


STUB = r'''#!/usr/bin/env python3
"""Fake herdr for tests. Answers from $HERDR_STUB_STATE and logs argv to $HERDR_STUB_LOG.
State maps "<arg1> <arg2>" (e.g. "agent get") to a list of {"out", "code", "sleep", "write"}; entries
are used in order and the last one repeats. Like real herdr, "out" goes to stdout on code 0 and to
stderr otherwise (its errors are JSON on stderr with exit 1). "sleep" (seconds, default none)
delays the answer after the call is logged, so a test can act while the call is in flight.
"write" ([[path, text], ...]) appends text to each file as the call is answered: what the agent
behind a pane would write when it receives a prompt (a transcript line, a session file)."""
import json, os, sys, time
key = ' '.join(sys.argv[1:3])
with open(os.environ['HERDR_STUB_LOG'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\n')
path = os.environ['HERDR_STUB_STATE']
state = json.load(open(path))
queue = state.get(key) or [{'out': '{"result": {}}', 'code': 0}]
resp = queue.pop(0) if len(queue) > 1 else queue[0]
state[key] = queue
json.dump(state, open(path, 'w'))
time.sleep(resp.get('sleep', 0))
for target, text in resp.get('write', []):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, 'a') as fh:
        fh.write(text)
code = resp.get('code', 0)
(sys.stderr if code else sys.stdout).write(resp.get('out', ''))
sys.exit(code)
'''


def herdr_stub(tmp, responses):
    """Put a fake herdr first on PATH. Returns (env, log_path)."""
    bindir = Path(tmp) / 'bin'
    bindir.mkdir(exist_ok=True)
    exe = bindir / 'herdr'
    exe.write_text(STUB)
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    state = Path(tmp) / 'herdr-state.json'
    state.write_text(json.dumps(responses))
    log = Path(tmp) / 'herdr-log.jsonl'
    log.write_text('')
    # RELAYLIB_HERDR_BOUND: a test is about its herdr answers, not the machine's speed; the tests of the bound pass
    # their own timeout. RELAYLIB_BANNER_SECONDS=0: a banner is read once, so a wrong one fails at once; a test that
    # waits for a late banner sets a long bound itself (HerdCase sets 120).
    env = dict(os.environ, PATH='%s:%s' % (bindir, os.environ['PATH']), HERDR_STUB_STATE=str(state),
               HERDR_STUB_LOG=str(log), HERDR_ENV='1', HERDR_PANE_ID='wT:p1', RELAYLIB_HERDR_BOUND='120',
               RELAYLIB_BANNER_SECONDS='0')
    return env, log


def herdr_calls(log):
    return [json.loads(line) for line in Path(log).read_text().splitlines() if line.strip()]


def agent_json(status, session=None, pane='wT:p0', name=None):
    agent = {'agent': 'claude', 'agent_status': status, 'pane_id': pane}
    if session:
        agent['agent_session'] = {'kind': 'id', 'value': session}
    if name:
        agent['name'] = name
    return json.dumps({'result': {'agent': agent, 'type': 'agent_info'}})


NOT_FOUND = {'out': json.dumps({'error': {'code': 'agent_not_found', 'message': 'not found'}}), 'code': 1}
