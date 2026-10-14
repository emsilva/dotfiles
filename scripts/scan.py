#!/usr/bin/env python3
"""Content scan before publication: a private deny-list plus gitleaks.

The deny-list lives outside the repository ($DOTFILES_DENYLIST, default
~/.config/dotfiles/denylist), one entry per line, '#' comments allowed:
`<literal term>` or `<literal term>==><replacement>`. Only the left side is
matched here, case-insensitively (casefold, non-ASCII included). A line that
`git filter-repo --replace-text` would read differently is refused; feed that
tool `scan.py replacements`, never the raw file, whose comments it would take
for rules.

History scans read commit messages, every commit header but tree and parent
(author and committer names and emails, mergetag, gpgsig, any extra header),
the lines each commit adds, the paths of the files it adds, every ref name and
every annotated tag (name, tagger, message). Removed lines are skipped: their
text was added by an earlier commit, which a full scan reports, and a scrub
commit must not block itself. Merge commits are diffed against their first
parent. Tree scans read tracked paths, every line of tracked files and symlink
targets. Replace refs are ignored everywhere: a push sends the real objects.
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
FILTER_REPO_PREFIXES = ('regex:', 'glob:', 'literal:')
ESCAPES = {b'a': b'\a', b'b': b'\b', b't': b'\t', b'n': b'\n', b'v': b'\v', b'f': b'\f', b'r': b'\r'}

def load_entries(path):
    """(term, replacement or None) per entry, in file order; refuses a line filter-repo would read differently."""
    path = Path(os.path.expanduser(path))
    if not path.is_file():
        raise SystemExit(f'Deny-list not found: {path} (set DOTFILES_DENYLIST); refusing to scan without it')
    entries = []
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').split('\n'), 1):
        line = line.removesuffix('\r')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        term, arrow, replacement = line.partition('==>')
        problem = ('empty term' if not term else
                   '"==>" more than once' if '==>' in replacement else
                   'whitespace around the term or "==>"' if term != term.strip() or replacement != replacement.strip()
                   else 'a filter-repo prefix (regex:, glob:, literal:)' if term.startswith(FILTER_REPO_PREFIXES)
                   else None)
        if problem:
            raise SystemExit(f'{path}:{number}: {problem}; scan.py and git filter-repo would read this line differently')
        entries.append((term, replacement if arrow else None))
    if not entries:
        raise SystemExit(f'Deny-list is empty: {path}; refusing a scan that cannot fail')
    return entries

def load_terms(path):
    terms = {}
    for term, _ in load_entries(path):
        terms.setdefault(term.casefold(), term)
    return terms

def matches(terms, text):
    folded = text.decode(errors='replace').casefold()
    return [term for term in terms if term in folded]

def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), '-c', 'core.quotePath=false', *args],
                          capture_output=True, check=True).stdout

def unquote(name):
    """A path as git prints it: C-quoted when it holds a quote, backslash or control character."""
    if not name.startswith(b'"'):
        return name
    return re.sub(rb'\\([0-7]{3}|.)', lambda m: bytes([int(m[1], 8)]) if len(m[1]) == 3 else ESCAPES.get(m[1], m[1]),
                  name[1:-1])

def scan_history(repo, revisions, terms):
    marker = ('\x1escan-' + uuid.uuid4().hex).encode()
    log = git(repo, 'log', '-p', '--text', '--no-textconv', '--no-color', '--no-ext-diff', '--no-renames',
              '--no-relative', '--no-show-signature', '--diff-merges=first-parent', '--src-prefix=a/', '--dst-prefix=b/',
              f'--format={marker.decode()}C %H%n%B{marker.decode()}E', *revisions, '--')
    hits, commits = [], []
    commit, state, path, name, number = '', 'patch', None, b'', 0
    for line in log.split(b'\n'):
        if line.startswith(marker + b'C '):
            commits.append(line[len(marker) + 2:].decode())
            commit, state, number = commits[-1][:12], 'message', 0
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
            # --no-renames: both sides name the same path, so the second half is the b/ side
            names = line[len(b'diff --git '):]
            name = unquote(names[(len(names) + 1) // 2:]).removeprefix(b'b/')
            state, path = 'header', name.decode(errors='replace')
        elif state == 'header':
            if line.startswith(b'new file mode '):  # an added or (with --no-renames) renamed file
                hits += [(f'{commit}:{path}', t) for t in matches(terms, name)]
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
    return hits + scan_headers(repo, commits, terms)

def scan_headers(repo, commits, terms):
    """Every raw commit header but tree and parent; author and committer without their timestamp."""
    hits = []
    batch = subprocess.run(['git', '-C', str(repo), 'cat-file', '--batch'], input=''.join(f'{c}\n' for c in commits).encode(),
                           capture_output=True, check=True).stdout
    for sha in commits:
        info, batch = batch.split(b'\n', 1)
        size = int(info.split()[2])
        raw, batch = batch[:size], batch[size + 1:]
        field = None
        for line in raw.split(b'\n\n', 1)[0].split(b'\n'):
            if not line.startswith(b' '):
                field, _, line = line.partition(b' ')
            if field in (b'tree', b'parent'):
                continue
            if field in (b'author', b'committer'):
                line = line[:line.rfind(b'>') + 1]
            label = f'<{field.decode(errors="replace")}>' if field in (b'author', b'committer') else \
                f'<header:{field.decode(errors="replace")}>'
            hits += [(f'{sha[:12]}:{label}', t) for t in matches(terms, line)]
    return hits

def scan_tag(repo, sha, terms):
    """An annotated tag's name, tagger and message, then the tag it points at, if any."""
    hits = []
    while git(repo, 'cat-file', '-t', sha).strip() == b'tag':
        raw = git(repo, 'cat-file', 'tag', sha)
        header = raw.split(b'\n\n', 1)[0].count(b'\n') + 1
        target = sha
        for number, line in enumerate(raw.split(b'\n'), 1):
            if number <= header and line.startswith((b'object ', b'type ')):
                target = line.split(b' ', 1)[1].decode() if line.startswith(b'object ') else target
                continue
            hits += [(f'{sha[:12]}:<tag>:{number}', t) for t in matches(terms, line)]
        sha = target
    return hits

def scan_refs(repo, refs, objects, terms):
    hits = []
    for ref in refs:
        hits += [(f'<ref>:{ref}', t) for t in matches(terms, ref.encode())]
    for sha in objects:
        hits += scan_tag(repo, sha, terms)
    return hits

def scan_all_refs(repo, terms):
    refs, tags = [], []
    for line in git(repo, 'for-each-ref', '--format=%(objectname) %(objecttype) %(refname)').decode().splitlines():
        sha, kind, ref = line.split(' ', 2)
        if ref != 'refs/stash':
            refs.append(ref)
            tags += [sha] if kind == 'tag' else []
    return scan_refs(repo, refs, tags, terms)

def scan_tree(repo, revision, terms):
    hits = []
    prefix = f'{revision}:' if revision else ''
    names = git(repo, *(['ls-tree', '-r', '-z', '--name-only', revision] if revision else ['ls-files', '-z']))
    for name in filter(None, names.split(b'\0')):
        hits += [(f'{prefix}{name.decode(errors="replace")}', t) for t in matches(terms, name)]
    # git grep skips symlinks; their target is pushed as a blob
    entries = git(repo, *(['ls-tree', '-r', '-z', revision] if revision else ['ls-files', '-s', '-z']))
    for entry in filter(None, entries.split(b'\0')):
        info, name = entry.split(b'\t', 1)
        fields = info.split(b' ')  # ls-tree: mode type sha; ls-files -s: mode sha stage
        if fields[0] == b'120000':
            target = git(repo, 'cat-file', 'blob', (fields[2] if revision else fields[1]).decode())
            hits += [(f'{prefix}{name.decode(errors="replace")}:1', t) for t in matches(terms, target)]
    # every line of every tracked file, matched here so that every mode folds case the same way
    command = ['git', '-C', str(repo), '-c', 'core.quotePath=false', 'grep', '-z', '-n', '--text', '--no-textconv',
               '--no-color', '--basic-regexp', '-e', '^'] + ([revision] if revision else []) + ['--']
    result = subprocess.run(command, capture_output=True)
    if result.returncode not in (0, 1):
        raise SystemExit(result.stderr.decode(errors='replace').strip() or 'git grep failed')
    for line in filter(None, result.stdout.split(b'\n')):
        path, number, text = line.split(b'\0', 2)
        hits += [(f'{path.decode(errors="replace")}:{number.decode()}', t) for t in matches(terms, text)]
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
    modes.add_parser('history', help='every commit, ref name and annotated tag, except refs/stash')
    outgoing = modes.add_parser('range', help='commits selected by git rev-list arguments, '
                                'e.g. A..B or -- SHA --not --remotes=origin')
    outgoing.add_argument('--ref', action='append', default=[], help='a pushed ref name, matched against the terms')
    outgoing.add_argument('--object', action='append', default=[],
                          help='a pushed object; when it is an annotated tag, its name, tagger and message are scanned')
    outgoing.add_argument('revisions', nargs='+')
    tree = modes.add_parser('tree', help='tracked paths and files in the working tree, or in REV')
    tree.add_argument('rev', nargs='?')
    modes.add_parser('replacements', help='the deny-list in git filter-repo --replace-text syntax: '
                     'feed this to filter-repo, never the raw file')
    args = parser.parse_args()
    os.environ['GIT_NO_REPLACE_OBJECTS'] = '1'  # for every git below and for gitleaks: a push sends the real objects
    denylist = os.environ.get('DOTFILES_DENYLIST') or DEFAULT_DENYLIST
    if args.mode == 'replacements':
        for term, replacement in load_entries(denylist):
            sys.stdout.buffer.write((term if replacement is None else f'{term}==>{replacement}').encode() + b'\n')
        return
    terms = load_terms(denylist)
    repo = Path(args.repo)
    if args.mode == 'tree':
        hits, clean = scan_tree(repo, args.rev, terms), True
    else:
        revisions = ['--exclude=refs/stash', '--all'] if args.mode == 'history' else args.revisions
        hits = scan_history(repo, revisions, terms)
        hits += scan_all_refs(repo, terms) if args.mode == 'history' else scan_refs(repo, args.ref, args.object, terms)
        clean = gitleaks(repo, ' '.join(revisions))
    clean = report(hits, terms, args.counts) and clean
    raise SystemExit(0 if clean else 1)

if __name__ == '__main__':
    main()
