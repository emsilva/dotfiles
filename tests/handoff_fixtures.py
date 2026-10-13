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
State maps "<arg1> <arg2>" (e.g. "agent get") to a list of {"out", "code"}; entries are used
in order and the last one repeats. Like real herdr, "out" goes to stdout on code 0 and to
stderr otherwise (its errors are JSON on stderr with exit 1)."""
import json, os, sys
key = ' '.join(sys.argv[1:3])
with open(os.environ['HERDR_STUB_LOG'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\n')
path = os.environ['HERDR_STUB_STATE']
state = json.load(open(path))
queue = state.get(key) or [{'out': '{"result": {}}', 'code': 0}]
resp = queue.pop(0) if len(queue) > 1 else queue[0]
state[key] = queue
json.dump(state, open(path, 'w'))
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
    env = dict(os.environ, PATH='%s:%s' % (bindir, os.environ['PATH']), HERDR_STUB_STATE=str(state),
               HERDR_STUB_LOG=str(log), HERDR_ENV='1', HERDR_PANE_ID='wT:p1')
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
