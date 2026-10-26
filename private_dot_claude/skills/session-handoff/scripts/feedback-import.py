#!/usr/bin/env python3
"""Merge a project's Codespace feedback into the Mac store, idempotently.

Usage: python3 -I feedback-import.py <project> [--dest DIR]

Reads <project>/.scratch/handoff-feedback/ and merges it into
~/.claude/handoff-feedback/ (or --dest). Gap rows come from gaps.jsonl and from
gaps.jsonl.codespace-<n> (n a positive integer, the copy a Codespace parked
beside a file it would not overwrite). They are appended, never rewritten,
deduped on (successor_session, missing) across every source file and the store.
Proposals are copied by filename, including <name>.md.codespace-<n>. One that
already exists and differs is left in place and named on stderr. Each proposal
copied by this run is printed as one TODO line in the shape the open proposal
lines in ~/TODO.md already use. This script does not write ~/TODO.md; the skill
step does. A missing scratch dir is a no-op. Exit 0 done, 1 when a gaps file
has a line that is not a gap row (nothing written), 2 on a usage error.
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


def parked_n(name):
    """The positive integer of a `.codespace-<n>` suffix, or None. Zero and a leading zero are not that suffix."""
    head, sep, tail = name.rpartition('.codespace-')
    if not sep or not tail.isdigit() or tail[0] == '0':
        return None
    return int(tail)


def gap_paths(src):
    """gaps.jsonl, then gaps.jsonl.codespace-<n> in numeric order. Other names are ignored."""
    paths = []
    primary = os.path.join(src, 'gaps.jsonl')
    if os.path.isfile(primary):
        paths.append(primary)
    parked = []
    for name in os.listdir(src):
        n = parked_n(name)
        if n is not None and name == 'gaps.jsonl.codespace-%d' % n:
            parked.append((n, os.path.join(src, name)))
    parked.sort()
    paths.extend(path for _, path in parked)
    return paths


def proposal_names(src_dir):
    """`.md` files and `<name>.md.codespace-<n>`, sorted. Anything else is ignored."""
    names = []
    for name in os.listdir(src_dir):
        if name.startswith('.'):
            continue
        if name.endswith('.md'):
            names.append(name)
            continue
        n = parked_n(name)
        if n is None:
            continue
        base = name[:-len('.codespace-%d' % n)]
        if base.endswith('.md'):
            names.append(name)
    return sorted(names)


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
    """One ready-to-add TODO line, the shape the open proposal lines in ~/TODO.md already use."""
    return ('- [ ] **session-handoff proposal: %s** — owner review, then apply with '
            'superpowers:writing-skills in the dotfiles repo; `%s` #session-handoff %s  '
            % (title, display_path(path), today))


def import_proposals(src_dir, dest_dir, today):
    """Copy new proposals. Returns (todo lines, names that differed)."""
    if not os.path.isdir(src_dir):
        return [], []
    todos, differs = [], []
    for name in proposal_names(src_dir):
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


def append_gaps(path, lines):
    """Append new JSON lines with O_APPEND. Existing bytes are never rewritten.

    A non-empty file whose last byte is not a newline gets a newline first, in the same write as the new
    rows, so a row another session appended with >> is not lost to a read-then-replace.
    """
    if not lines:
        return
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        prefix = b''
        if os.fstat(fd).st_size:
            os.lseek(fd, -1, os.SEEK_END)
            if os.read(fd, 1) != b'\n':
                prefix = b'\n'
        payload = prefix + ''.join(line + '\n' for line in lines).encode('utf-8')
        while payload:
            payload = payload[os.write(fd, payload):]
    finally:
        os.close(fd)


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
    src_rows, errors = [], []
    for path in gap_paths(src):
        rows, bad = load_gaps(path)
        src_rows.extend(rows)
        errors.extend(bad)
    dest_gaps = os.path.join(args.dest, 'gaps.jsonl')
    dest_rows, dest_errors = load_gaps(dest_gaps)
    errors.extend(dest_errors)
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
    append_gaps(dest_gaps, added)
    todos, differs = import_proposals(os.path.join(src, 'proposals'), os.path.join(args.dest, 'proposals'),
                                      datetime.date.today().isoformat())
    for name in differs:
        print('feedback-import: not overwritten (differs): %s' % name, file=sys.stderr)
    for line in todos:
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
