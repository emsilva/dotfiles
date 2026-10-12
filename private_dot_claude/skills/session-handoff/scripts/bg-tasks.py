#!/usr/bin/env python3
"""List this session's open background tasks (shell, monitor, workflow, agent).

Usage: python3 -I bg-tasks.py [--session ID] [--transcript PATH ...] [--until-line N] [--json]

The session defaults to $CLAUDE_CODE_SESSION_ID. --transcript adds earlier
transcripts, read before the session's own: a task started before a /clear
lives in the previous session's file. Exit 0, or 2 when the transcript is not found.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcript  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description="List this session's open background tasks.")
    p.add_argument('--session', default=os.environ.get('CLAUDE_CODE_SESSION_ID'))
    p.add_argument('--transcript', action='append', default=[])
    p.add_argument('--until-line', type=int)
    p.add_argument('--json', action='store_true')
    p.add_argument('--projects', default=transcript.PROJECTS, help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    if not a.session:
        p.error('no session: pass --session or run inside Claude Code (CLAUDE_CODE_SESSION_ID)')
    try:
        own = transcript.find_transcript(a.session, a.projects)
    except LookupError as e:
        print('bg-tasks: %s' % e, file=sys.stderr)
        return 2
    tasks = transcript.open_tasks(a.transcript + [own], a.until_line)
    if a.json:
        print(json.dumps(tasks, indent=1))
    else:
        print('%d open background task(s)' % len(tasks))
        for t in tasks:
            print('%s  %-8s %s  %s :: %s' % (t['id'], t['kind'], t['started_at'], t['description'],
                                              t['command'][:160]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
