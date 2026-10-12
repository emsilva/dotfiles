"""Read a Claude Code session transcript (JSONL) the way the relay scripts need it.

Stdlib only. The CLIs run under `python3 -I`, which leaves the script's own
directory off sys.path, so each CLI inserts it before importing this module.

Record formats, verified on Claude Code 2.1.296 (2026-10-12):
- Background launches are tool results of specific tools: Bash with
  run_in_background (`Command running in background with ID: <id>`), Monitor
  (`Monitor started (task <id>`), Workflow (`Workflow launched in background.
  Task ID: <id>`), Agent with run_in_background (`Async agent launched
  successfully. ... agentId: <id>`).
- A task closes on a `user` record whose origin.kind is "task-notification", or
  a `queue-operation` record, carrying a terminal <status>; or on a TaskStop
  result `Successfully stopped task: <id>`. `attachment` records are never read:
  prompt snapshots quote notifications verbatim.
- Typed prompts (by the owner, or by herdr into the pane) are `user` records
  whose origin.kind is "human", or `queue-operation` enqueues while busy.
- CronCreate results read `Scheduled <one-shot|recurring> task <id>`; CronDelete
  results read `Cancelled job <id>`.
"""
import datetime
import glob
import json
import os
import re

PROJECTS = os.path.expanduser('~/.claude/projects')

# (kind, tool name, requires run_in_background, result pattern matched at the start)
LAUNCHES = (
    ('shell', 'Bash', True, re.compile(r'Command running in background with ID: (\w+)')),
    ('monitor', 'Monitor', False, re.compile(r'Monitor started \(task (\w+)')),
    ('workflow', 'Workflow', False, re.compile(r'Workflow launched in background\. Task ID: (\w+)')),
    ('agent', 'Agent', True, re.compile(r'Async agent launched successfully\..*?agentId: (\w+)', re.S)),
)
NOTICE = re.compile(r'<task-id>(\w+)</task-id>.*?<status>(\w+)</status>', re.S)
STOPPED = re.compile(r'Successfully stopped task: (\w+)')
TERMINAL = frozenset({'completed', 'failed', 'killed', 'stopped'})
CRON_MADE = re.compile(r'Scheduled [\w-]+ task (\w+)')
CRON_GONE = re.compile(r'Cancelled job (\w+)')


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


def _in_background(args):
    return str(args.get('run_in_background')).lower() == 'true'


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


def _closed_by_notice(rec):
    if rec.get('type') == 'user' and (rec.get('origin') or {}).get('kind') == 'task-notification':
        text = _user_text(rec)
    elif rec.get('type') == 'queue-operation':
        text = str(rec.get('content', ''))
    else:
        return []
    return [tid for tid, status in NOTICE.findall(text) if status in TERMINAL]


def open_tasks(paths, until_line=None):
    """Background tasks launched in these transcripts and not closed in them.

    paths: oldest first (a pre-/clear transcript, then the session's own).
    """
    launched, closed = {}, set()
    for path, line, rec, call in _events(paths, until_line):
        if call is None:
            closed.update(_closed_by_notice(rec))
            continue
        name, args, result = call
        if name == 'TaskStop':
            closed.update(STOPPED.findall(result))
            continue
        for kind, tool, needs_background, pattern in LAUNCHES:
            if name != tool or (needs_background and not _in_background(args)):
                continue
            m = pattern.match(result.lstrip())
            if m:
                launched[m.group(1)] = {
                    'id': m.group(1), 'kind': kind, 'description': args.get('description', ''),
                    'command': args.get('command', ''), 'started_at': rec.get('timestamp', ''),
                    'transcript': path, 'line': line}
            break
    return [task for tid, task in launched.items() if tid not in closed]


def open_crons(paths, until_line=None):
    """Session crons created and not deleted in these transcripts (a fired one-shot is still listed)."""
    made, gone = {}, set()
    for _, _, _, call in _events(paths, until_line):
        if call is None:
            continue
        name, args, result = call
        if name == 'CronCreate':
            m = CRON_MADE.match(result.lstrip())
            if m:
                made[m.group(1)] = {'id': m.group(1), 'cron': args.get('cron', ''),
                                    'prompt': args.get('prompt', ''),
                                    'recurring': args.get('recurring', True) is not False}
        elif name == 'CronDelete':
            gone.update(CRON_GONE.findall(result))
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
            if not text.lstrip().startswith('<task-notification>'):
                out.append({'line': i, 'timestamp': rec.get('timestamp', ''), 'text': text})
    return out


def last_model(path):
    model = None
    for _, rec in records(path):
        if rec.get('type') == 'assistant' and not rec.get('isSidechain'):
            value = (rec.get('message') or {}).get('model')
            if value and not value.startswith('<'):
                model = value
    return model


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
