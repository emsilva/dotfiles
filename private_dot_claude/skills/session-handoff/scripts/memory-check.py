#!/usr/bin/env python3
"""Check a project memory dir before a handoff; optionally apply the two safe fixes.

Usage: python3 -I memory-check.py <memory-dir> [--since ISO | --session ID] [--fix] [--json]

Measures MEMORY.md the way Claude Code 2.1.296 loads it: trimmed, at most 200
lines and 25,000 UTF-16 units, cut at the last newline before the cap. Reports
headroom, memory files missing from the index (written since --since, and
older), and index lines whose links point at missing files. Only links to
memory files are checked: a target with a URL scheme (https:, mailto:) is
skipped, and a #fragment is dropped (file.md#part checks file.md). --since
defaults to the first record of $CLAUDE_CODE_SESSION_ID's transcript (or
--session's). --fix adds an index line for each missing file written since
--since and removes index lines whose every checked link is dead, then
measures again. Exit 0 when no debt remains, 1 when it does, 2 on a usage error.
"""
import argparse
import datetime
import json
import os
import re
import sys

# In development this dir is chezmoi source: bytecode written beside the script would be deployed.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcript  # noqa: E402

CAP_LINES, CAP_UNITS = 200, 25000
LINK = re.compile(r'\]\(([^)\s]+)\)')
SCHEME = re.compile(r'[A-Za-z][A-Za-z0-9+.-]*:')


def file_links(line):
    """The line's link targets that name a file in the memory dir, without any #fragment."""
    paths = (target.split('#', 1)[0] for target in LINK.findall(line) if not SCHEME.match(target))
    return [path for path in paths if path]


class UsageError(Exception):
    """A bad argument: main reports it on one line and exits 2."""


def units(text):
    return len(text.encode('utf-16-le')) // 2


def measure(text):
    body = text.strip()
    lines = body.split('\n') if body else []
    kept = total = 0
    for n, line in enumerate(lines[:CAP_LINES]):
        cost = units(line) + (1 if n else 0)
        if total + cost > CAP_UNITS:
            break
        total += cost
        kept += 1
    return {'lines': len(lines), 'units': units(body), 'lost_lines': len(lines) - kept,
            'headroom': CAP_UNITS - units(body)}


def frontmatter(path):
    text = open(path, encoding='utf-8', errors='replace').read()
    if not text.startswith('---\n'):
        return {}
    end = text.find('\n---', 4)
    block = text[4:end] if end > 0 else ''
    out = {}
    for key in ('name', 'description'):
        m = re.search(r'^%s:\s*(.+)$' % key, block, re.M)
        if m:
            out[key] = m.group(1).strip().strip('"\'')
    return out


def read_index(mem):
    path = os.path.join(mem, 'MEMORY.md')
    return (open(path, encoding='utf-8').read(), True) if os.path.exists(path) else ('', False)


def check(mem, since):
    text, exists = read_index(mem)
    lines = text.split('\n')
    linked = {target for line in lines for target in file_links(line)}
    files = sorted(f for f in os.listdir(mem) if f.endswith('.md') and f != 'MEMORY.md')
    missing = [f for f in files if f not in linked]
    recent = [f for f in missing if since is not None and os.path.getmtime(os.path.join(mem, f)) >= since]
    dead = []
    for n, line in enumerate(lines, 1):
        targets = file_links(line)
        gone = [t for t in targets if not os.path.exists(os.path.join(mem, t))]
        if gone:
            dead.append({'line': n, 'targets': gone, 'removable': len(gone) == len(targets)})
    return {'index_exists': exists, 'index': measure(text), 'unindexed_recent': recent,
            'unindexed_older': [f for f in missing if f not in recent], 'dead_links': dead}


def fix(mem, report):
    text, _ = read_index(mem)
    lines = text.split('\n')
    drop = {d['line'] for d in report['dead_links'] if d['removable']}
    removed = [lines[n - 1] for n in sorted(drop)]
    kept = [line for n, line in enumerate(lines, 1) if n not in drop]
    added = []
    for f in report['unindexed_recent']:
        fm = frontmatter(os.path.join(mem, f))
        added.append('- [%s](%s) — %s' % (fm.get('name', f[:-3]), f, fm.get('description', '(no description)')))
    body = '\n'.join(kept).rstrip('\n')
    body = (body + '\n' if body else '') + ''.join(line + '\n' for line in added)
    with open(os.path.join(mem, 'MEMORY.md'), 'w', encoding='utf-8') as fh:
        fh.write(body)
    return {'added': added, 'removed': removed}


def since_from(args):
    if args.since is not None:
        try:
            return datetime.datetime.fromisoformat(args.since.replace('Z', '+00:00')).timestamp()
        except (ValueError, OverflowError):
            raise UsageError('invalid --since %r: expected an ISO 8601 time such as 2026-10-12T00:00:00Z'
                             % args.since) from None
    session = args.session or os.environ.get('CLAUDE_CODE_SESSION_ID')
    if not session:
        return None
    try:
        first = transcript.first_timestamp(transcript.find_transcript(session, args.projects))
    except LookupError:
        return None
    return transcript.epoch(first) if first else None


def has_debt(report):
    return bool(report['index']['lost_lines'] or report['unindexed_recent'] or report['unindexed_older']
                or report['dead_links'])


def main(argv=None):
    p = argparse.ArgumentParser(description='Check a project memory dir before a handoff.')
    p.add_argument('memory_dir')
    p.add_argument('--since')
    p.add_argument('--session')
    p.add_argument('--fix', action='store_true')
    p.add_argument('--json', action='store_true')
    p.add_argument('--projects', default=transcript.PROJECTS, help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    if not os.path.isdir(args.memory_dir):
        print('memory-check: no such directory: %s' % args.memory_dir, file=sys.stderr)
        return 2
    try:
        since = since_from(args)
    except UsageError as e:
        print('memory-check: %s' % e, file=sys.stderr)
        return 2
    report = check(args.memory_dir, since)
    if args.fix:
        fixed = fix(args.memory_dir, report)
        report = check(args.memory_dir, since)
        report['fixed'] = fixed
    report['debt'] = has_debt(report)
    if args.json:
        print(json.dumps(report, indent=1, ensure_ascii=False))
    else:
        i = report['index']
        print('MEMORY.md: %d lines, %d UTF-16 units, headroom %d, %d line(s) lost at load'
              % (i['lines'], i['units'], i['headroom'], i['lost_lines']))
        for key in ('unindexed_recent', 'unindexed_older'):
            for f in report[key]:
                print('%s: %s' % (key, f))
        for d in report['dead_links']:
            print('dead link, line %d: %s%s' % (d['line'], ', '.join(d['targets']),
                                                '' if d['removable'] else ' (the line has live links too)'))
        for line in report.get('fixed', {}).get('added', []):
            print('added: %s' % line)
        for line in report.get('fixed', {}).get('removed', []):
            print('removed: %s' % line)
        print('debt' if report['debt'] else 'clean (checked)')
    return 1 if report['debt'] else 0


if __name__ == '__main__':
    sys.exit(main())
