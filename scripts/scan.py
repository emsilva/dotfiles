#!/usr/bin/env python3
"""Content scan before publication: a private deny-list plus gitleaks.

The deny-list lives outside the repository ($DOTFILES_DENYLIST, default
~/.config/dotfiles/denylist), one entry per line, '#' comments allowed:
`<literal term>` or `<literal term>==><replacement>`. Only the left side is
read here and it matches case-insensitively; the same file feeds
`git filter-repo --replace-text`, which is why the replacement syntax exists.

History scans read commit messages and the lines each commit adds, never the
author or committer headers (the public author alias may itself be
deny-listed). Removed lines are skipped: their text was added by an earlier
commit, which a full scan reports, and a scrub commit must not block itself.
Merge commits are diffed against their first parent.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

DEFAULT_DENYLIST = '~/.config/dotfiles/denylist'
HUNK = re.compile(rb'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@')

def load_terms(path):
    path = Path(os.path.expanduser(path))
    if not path.is_file():
        raise SystemExit(f'Deny-list not found: {path} (set DOTFILES_DENYLIST); refusing to scan without it')
    terms = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        term = line.split('==>', 1)[0]
        if not term:
            raise SystemExit(f'{path}:{number}: empty term')
        terms.setdefault(term.lower(), term)
    if not terms:
        raise SystemExit(f'Deny-list is empty: {path}; refusing a scan that cannot fail')
    return terms

def matches(terms, line):
    lowered = line.lower()
    return [term for term in terms if term.encode() in lowered]

def scan_history(repo, revisions, terms):
    marker = ('\x1escan-' + uuid.uuid4().hex).encode()
    log = subprocess.run(['git', '-C', str(repo), '-c', 'core.quotePath=false', 'log', '-p', '--text',
                          '--no-color', '--no-ext-diff', '--no-renames', '--diff-merges=first-parent',
                          f'--format={marker.decode()}C %H%n%B{marker.decode()}E', *revisions, '--'],
                         capture_output=True, check=True).stdout
    hits = []
    commit, state, path, number = '', 'patch', None, 0
    for line in log.split(b'\n'):
        if line.startswith(marker + b'C '):
            commit, state, number = line[len(marker) + 2:].decode()[:12], 'message', 0
            continue
        if state == 'message':
            end = line.find(marker + b'E')
            text = line if end < 0 else line[:end]
            if end < 0 or text:
                number += 1
                hits += [(f'{commit}:<message>:{number}', t) for t in matches(terms, text)]
            if end >= 0:
                state, path = 'header', None
            continue
        if line.startswith(b'diff --git '):
            state, path = 'header', None
        elif state == 'header':
            if line.startswith(b'+++ '):
                name = line[4:].decode(errors='replace').strip('"')
                path = None if name == '/dev/null' else name.removeprefix('b/')
            elif (hunk := HUNK.match(line)):
                state, number = 'hunk', int(hunk.group(1))
        elif state == 'hunk':
            if (hunk := HUNK.match(line)):
                number = int(hunk.group(1))
            elif line.startswith(b'+'):
                hits += [(f'{commit}:{path}:{number}', t) for t in matches(terms, line[1:])]
                number += 1
            elif line.startswith(b' '):
                number += 1
    return hits

def scan_tree(repo, revision, terms):
    hits = []
    for term in terms:
        command = ['git', '-C', str(repo), '-c', 'core.quotePath=false', 'grep', '-z', '-n', '-i', '-F', '--text',
                   '-e', term] + ([revision] if revision else []) + ['--']
        result = subprocess.run(command, capture_output=True)
        if result.returncode not in (0, 1):
            raise SystemExit(result.stderr.decode(errors='replace').strip() or 'git grep failed')
        for line in result.stdout.splitlines():
            path, number = line.split(b'\0')[:2]
            hits.append((f'{path.decode(errors="replace")}:{number.decode()}', term))
    return hits

def gitleaks(repo, log_opts):
    if not shutil.which('gitleaks'):
        if os.environ.get('DOTFILES_SCAN_ALLOW_NO_GITLEAKS') == '1':
            print('WARNING: gitleaks is not installed; DOTFILES_SCAN_ALLOW_NO_GITLEAKS=1, so only the '
                  'deny-list ran. Secrets are NOT scanned. Install it: brew install gitleaks', file=sys.stderr)
            return True
        raise SystemExit('gitleaks is not installed: install gitleaks (brew install gitleaks), or set '
                         'DOTFILES_SCAN_ALLOW_NO_GITLEAKS=1 to scan with the deny-list only')
    result = subprocess.run(['gitleaks', 'git', '--no-banner', '--redact', f'--log-opts={log_opts}', str(repo)])
    if result.returncode != 0:
        print(f'gitleaks reported findings or failed (exit {result.returncode})', file=sys.stderr)
    return result.returncode == 0

def report(hits, terms, zeros=False):
    for where, term in hits:
        print(f'{where}: {terms[term]}')
    counts = {term: 0 for term in terms}
    for _, term in hits:
        counts[term] += 1
    print(f'-- {len(hits)} deny-list hit(s)')
    for term, count in counts.items():
        if count or zeros:
            print(f'   {count:5}  {terms[term]}')
    return not hits

def main():
    parser = argparse.ArgumentParser(description='Scan for deny-listed terms and secrets before publication.')
    parser.add_argument('--repo', default='.', help='repository to scan (default: current directory)')
    parser.add_argument('--counts', action='store_true', help='also list deny-list terms with zero hits')
    modes = parser.add_subparsers(dest='mode', required=True)
    modes.add_parser('history', help='every commit reachable from any ref except refs/stash')
    outgoing = modes.add_parser('range', help='commits selected by git rev-list arguments, '
                                'e.g. A..B or -- SHA --not --remotes')
    outgoing.add_argument('revisions', nargs='+')
    tree = modes.add_parser('tree', help='tracked files in the working tree, or in REV')
    tree.add_argument('rev', nargs='?')
    args = parser.parse_args()
    terms = load_terms(os.environ.get('DOTFILES_DENYLIST') or DEFAULT_DENYLIST)
    repo = Path(args.repo)
    if args.mode == 'tree':
        hits, clean = scan_tree(repo, args.rev, terms), True
    else:
        revisions = ['--exclude=refs/stash', '--all'] if args.mode == 'history' else args.revisions
        hits = scan_history(repo, revisions, terms)
        clean = gitleaks(repo, ' '.join(revisions))
    clean = report(hits, terms, args.counts) and clean
    raise SystemExit(0 if clean else 1)

if __name__ == '__main__':
    main()
