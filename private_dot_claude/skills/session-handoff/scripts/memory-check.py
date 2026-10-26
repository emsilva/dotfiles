#!/usr/bin/env python3
"""Check a project memory dir before a handoff; optionally apply the safe fixes.

Usage: python3 -I memory-check.py <memory-dir> [--since ISO | --session ID] [--fix] [--json]

Measures MEMORY.md the way Claude Code 2.1.296 loads it: trimmed, at most 200
lines and 25,000 UTF-16 units, cut at the last newline before the cap. Reports
headroom, memory files missing from the index (written since --since, and
older), and index lines whose links point at missing files. Only pointers to
memory files are checked: without <...> and #fragment, the target must have no
URL scheme, not start with ~ or /, end in .md and stay inside the memory dir;
links in `code spans` are not pointers. --since defaults to the first record of
$CLAUDE_CODE_SESSION_ID's transcript (or --session's). --fix adds an index line
for each missing file written since --since (only a pointer this check reads
back), removes index lines whose every pointer is dead, and removes index lines
whose every pointer is into handoffs/ (a note is task-state, not a memory). It
edits the index text the check read and replaces MEMORY.md in one step, then
measures again. Exit 0 prints `clean (checked)`. Exit 1's last line is
`debt: N unindexed_older, N unindexed_recent, N dead link, N lines lost at load, N handoff pointer`;
those counts match the lines printed above it, and `--json` carries them under
`counts`. Exit 2 is a usage error.
"""
import argparse
import contextlib
import datetime
import json
import os
import re
import stat
import sys
import tempfile
import urllib.parse

# In development this dir is chezmoi source: bytecode written beside the script would be deployed.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcript  # noqa: E402

CAP_LINES, CAP_UNITS = 200, 25000
# Claude Code 2.1.296 reads index pointers as \]\(([^()\n]+?\.md)\): spaces are allowed, parentheses are not.
LINK = re.compile(r'\]\(([^()\n]+?)\)')
SCHEME = re.compile(r'[A-Za-z][A-Za-z0-9+.-]*:')
CODE_SPAN = re.compile(r'(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)')


def under_handoffs(name):
    """True when name points into a handoffs/ directory. Notes are task-state, not memories, so an index
    pointer there is a finding even when the file exists."""
    return 'handoffs' in name.split('/')[:-1]


def pointers(mem, line):
    """The memory files the line's links point at, as names relative to mem.

    A link counts only when its target, without <...> and #fragment, has no scheme, does not
    start with ~ or /, ends in .md and stays inside mem; links in code spans never count.
    A %-escaped target names the unescaped file when only that one exists.
    """
    root = os.path.abspath(mem)  # normpath('.') would put every pointer outside it
    names = []
    for target in LINK.findall(CODE_SPAN.sub('', line)):
        t = target.strip()
        if t.startswith('<') and t.endswith('>'):
            t = t[1:-1].strip()
        t = t.split('#', 1)[0]
        if SCHEME.match(t) or t.startswith(('~', '/')) or not t.endswith('.md'):
            continue
        inside = []
        for form in dict.fromkeys((t, urllib.parse.unquote(t))):
            full = os.path.normpath(os.path.join(root, form))
            if full.startswith(root + os.sep):
                inside.append(full[len(root) + 1:])
        if inside:
            names.append(next((n for n in inside if os.path.exists(os.path.join(root, n))), inside[0]))
    return names


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
    if not os.path.exists(path):
        return '', False
    with open(path, encoding='utf-8') as fh:
        return fh.read(), True


def check(mem, since, text, exists):
    lines = text.split('\n')
    links = [pointers(mem, line) for line in lines]
    linked = {name for names in links for name in names if not under_handoffs(name)}
    files = sorted(f for f in os.listdir(mem) if f.endswith('.md') and f != 'MEMORY.md')
    missing = [f for f in files if f not in linked]
    recent = [f for f in missing if since is not None and os.path.getmtime(os.path.join(mem, f)) >= since]
    dead, handoff = [], []
    for n, names in enumerate(links, 1):
        noted = [name for name in names if under_handoffs(name)]
        if noted:
            handoff.append({'line': n, 'targets': noted, 'removable': len(noted) == len(names)})
        gone = [name for name in names if name not in noted and not os.path.exists(os.path.join(mem, name))]
        if gone:
            dead.append({'line': n, 'targets': gone, 'removable': len(gone) == len(names)})
    return {'index_exists': exists, 'index': measure(text), 'unindexed_recent': recent,
            'unindexed_older': [f for f in missing if f not in recent], 'dead_links': dead,
            'handoff_pointers': handoff}


def fix(mem, text, report):
    """Apply the safe fixes to text, the index exactly as check() read it, and replace MEMORY.md.

    Line numbers in the report index that text: re-reading the file could shift them onto a
    line another worker wrote meanwhile.
    """
    lines = text.split('\n')
    drop = {d['line'] for d in report['dead_links'] if d['removable']}
    drop.update(d['line'] for d in report['handoff_pointers'] if d['removable'])
    removed = [lines[n - 1] for n in sorted(drop)]
    kept = [line for n, line in enumerate(lines, 1) if n not in drop]
    added = []
    for f in report['unindexed_recent']:
        fm = frontmatter(os.path.join(mem, f))
        line = '- [%s](%s) — %s' % (fm.get('name', f[:-3]), f, fm.get('description', '(no description)'))
        if f in pointers(mem, line):  # one the check cannot read back would be added again on every run
            added.append(line)
    body = '\n'.join(kept).rstrip('\n')
    body = (body + '\n' if body else '') + ''.join(line + '\n' for line in added)
    replace(os.path.join(mem, 'MEMORY.md'), body)
    return {'added': added, 'removed': removed}


def replace(path, text):
    """Write text to path in one step: a crash leaves the old file or the new one, never a torn one."""
    path = os.path.realpath(path)
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    fd, tmp = tempfile.mkstemp(prefix='.MEMORY.md.', suffix='.tmp', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


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


def counts(report):
    """The numbers the exit-1 summary quotes, one per finding kind."""
    return {'unindexed_older': len(report['unindexed_older']), 'unindexed_recent': len(report['unindexed_recent']),
            'dead_link': len(report['dead_links']), 'lost_lines': report['index']['lost_lines'],
            'handoff_pointer': len(report['handoff_pointers'])}


def debt_line(report):
    c = report['counts']
    return ('debt: %d unindexed_older, %d unindexed_recent, %d dead link, %d lines lost at load, '
            '%d handoff pointer' % (c['unindexed_older'], c['unindexed_recent'], c['dead_link'], c['lost_lines'],
                                    c['handoff_pointer']))


def has_debt(report):
    return bool(report['index']['lost_lines'] or report['unindexed_recent'] or report['unindexed_older']
                or report['dead_links'] or report['handoff_pointers'])


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
    text, exists = read_index(args.memory_dir)
    report = check(args.memory_dir, since, text, exists)
    if args.fix:
        fixed = fix(args.memory_dir, text, report)
        report = check(args.memory_dir, since, *read_index(args.memory_dir))
        report['fixed'] = fixed
    report['counts'] = counts(report)
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
        for h in report['handoff_pointers']:
            print('handoff pointer, line %d: %s%s' % (h['line'], ', '.join(h['targets']),
                                                      '' if h['removable'] else ' (the line has other links too)'))
        for line in report.get('fixed', {}).get('added', []):
            print('added: %s' % line)
        for line in report.get('fixed', {}).get('removed', []):
            print('removed: %s' % line)
        print(debt_line(report) if report['debt'] else 'clean (checked)')
    return 1 if report['debt'] else 0


if __name__ == '__main__':
    sys.exit(main())
