#!/usr/bin/env python3
"""Merge a project's Codespace feedback into the Mac store, idempotently.

Usage: python3 -I feedback-import.py <project> [--dest DIR]

Reads <project>/.scratch/handoff-feedback/ and merges it into
~/.claude/handoff-feedback/ (or --dest). Gap rows are appended, deduped on
(successor_session, missing); an existing row is never rewritten. Proposals are
copied by filename. One that already exists and differs is left in place and
named on stderr. Each proposal copied by this run is printed as one TODO line
in the todo skill's format, tagged #session-handoff. This script does not write
~/TODO.md; the skill step does. A missing scratch dir is a no-op. Exit 0 done,
1 when a gaps file has a line that is not a gap row (nothing written), 2 on a
usage error.
"""
import argparse
import contextlib
import datetime
import json
import os
import sys
import tempfile

sys.dont_write_bytecode = True


def load_gaps(path):
    """[(raw line, row)] and a list of error strings. A missing file is no rows."""
    if not os.path.isfile(path):
        return [], []
    rows, errors = [], []
    with open(path, encoding='utf-8') as fh:
        for n, raw in enumerate(fh, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except ValueError as e:
                errors.append('%s:%d does not parse: %s' % (path, n, e))
                continue
            if not isinstance(row, dict) or not isinstance(row.get('missing'), str):
                errors.append('%s:%d is not a gap row' % (path, n))
                continue
            rows.append((raw.strip(), row))
    return rows, errors


def gap_key(row):
    return (row.get('successor_session'), row.get('missing'))


def replace(path, text):
    """Write text to path in one step. A crash leaves the old file or the new one."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.feedback-import.', suffix='.tmp', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def display_path(path):
    home = os.path.expanduser('~')
    path = os.path.abspath(path)
    if path == home or path.startswith(home + os.sep):
        return '~' + path[len(home):]
    return path


def proposal_title(text, filename):
    for line in text.splitlines():
        if line.startswith('# '):
            title = line[2:].strip()
            if title.lower().startswith('proposal:'):
                title = title.split(':', 1)[1].strip()
            return title or filename
    return filename


def todo_line(title, path, today):
    """One ready-to-add TODO line: the todo skill's shape, tagged #session-handoff, two trailing spaces."""
    return '- [ ] Review session-handoff proposal: %s (`%s`) #session-handoff %s  ' % (
        title, display_path(path), today)


def import_proposals(src_dir, dest_dir, today):
    """Copy new proposals. Returns (todo lines, names that differed)."""
    if not os.path.isdir(src_dir):
        return [], []
    todos, differs = [], []
    for name in sorted(os.listdir(src_dir)):
        if name.startswith('.') or not name.endswith('.md'):
            continue
        src, dest = os.path.join(src_dir, name), os.path.join(dest_dir, name)
        data = open(src, 'rb').read()
        if os.path.exists(dest):
            if open(dest, 'rb').read() != data:
                differs.append(name)
            continue
        os.makedirs(dest_dir, exist_ok=True)
        replace(dest, data.decode('utf-8'))
        title = proposal_title(data.decode('utf-8', errors='replace'), name)
        todos.append(todo_line(title, dest, today))
    return todos, differs


def main(argv=None):
    p = argparse.ArgumentParser(description="Merge a project's scratch handoff-feedback into the Mac store.")
    p.add_argument('project', help='the project directory; its .scratch/handoff-feedback/ is the source')
    p.add_argument('--dest', default=os.path.expanduser('~/.claude/handoff-feedback'),
                   help='the store to merge into (default: ~/.claude/handoff-feedback)')
    args = p.parse_args(argv)
    if not os.path.isdir(args.project):
        print('feedback-import: no such directory: %s' % args.project, file=sys.stderr)
        return 2
    src = os.path.join(args.project, '.scratch', 'handoff-feedback')
    if not os.path.isdir(src):
        return 0
    src_rows, src_errors = load_gaps(os.path.join(src, 'gaps.jsonl'))
    dest_gaps = os.path.join(args.dest, 'gaps.jsonl')
    dest_rows, dest_errors = load_gaps(dest_gaps)
    errors = src_errors + dest_errors
    if errors:
        for error in errors:
            print('feedback-import: %s' % error, file=sys.stderr)
        return 1
    seen = {gap_key(row) for _, row in dest_rows}
    added = []
    for raw, row in src_rows:
        key = gap_key(row)
        if key in seen:
            continue
        seen.add(key)
        added.append(raw)
    if added:
        replace(dest_gaps, ''.join(line + '\n' for line in [raw for raw, _ in dest_rows] + added))
    todos, differs = import_proposals(os.path.join(src, 'proposals'), os.path.join(args.dest, 'proposals'),
                                      datetime.date.today().isoformat())
    for name in differs:
        print('feedback-import: not overwritten (differs): %s' % name, file=sys.stderr)
    for line in todos:
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
