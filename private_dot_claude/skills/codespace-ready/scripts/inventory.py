#!/usr/bin/env python3
"""Read-only inventory of what a Codespace move must carry.

Usage: python3 -I inventory.py [--repo PATH]

Never writes, fetches or pushes. Every subprocess has a timeout. A check that
cannot be made becomes a "could not check" line, not a traceback.
"""
import sys

# Chezmoi deploys this directory. Bytecode written beside the script would be deployed.
sys.dont_write_bytecode = True

import argparse
import json
import os
import re
import shutil
import stat
import subprocess

GIT_TIMEOUT = 20
DOCKER_TIMEOUT = 15
READ_CAP = 1_000_000
REBUILDABLE = {'node_modules', '.venv', '__pycache__', 'dist', 'build', '.task', 'target'}
TASKFILES = ('Taskfile.yml', 'Taskfile.yaml', 'taskfile.yml', 'taskfile.yaml')
SCRIPT_EXT = {
    '.sh', '.bash', '.zsh', '.py', '.rb', '.pl', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx',
    '.yml', '.yaml', '.json', '.toml', '.ini', '.cfg', '.conf', '.mk', '.tf', '.ps1',
}
SCRIPT_NAMES = {
    'Makefile', 'GNUmakefile', 'Taskfile.yml', 'Taskfile.yaml', 'Dockerfile', 'Containerfile',
    'Justfile', 'justfile', 'Procfile',
}
SECTIONS = (
    'branches', 'worktrees', 'stashes', 'untracked and ignored files', 'paths outside the repo',
    'env files', 'branch-only tasks', 'docker',
)


class CheckError(Exception):
    """A check that could not be made. The section degrades; the process does not."""


def run(cmd, cwd=None, timeout=GIT_TIMEOUT):
    env = os.environ.copy()
    env['GIT_OPTIONAL_LOCKS'] = '0'
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, errors='replace', timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return None, '', 'timed out'
    except OSError as exc:
        return None, '', str(exc)
    return proc.returncode, proc.stdout, proc.stderr


def git_cmd(repo, *args):
    return ['git', '--no-optional-locks', '-C', str(repo), '-c', 'core.quotePath=false', *args]


def git(repo, *args, timeout=GIT_TIMEOUT):
    code, out, err = run(git_cmd(repo, *args), timeout=timeout)
    if code is None:
        raise CheckError(err or 'timed out')
    if code != 0:
        detail = err.strip().splitlines()[-1] if err.strip() else f'exit {code}'
        raise CheckError(detail)
    return out


def try_git(repo, *args):
    """(ok, stdout). A failure is not a section failure: the caller decides."""
    code, out, err = run(git_cmd(repo, *args))
    if code == 0:
        return True, out
    return False, err


def classify(path):
    if not os.path.isdir(path):
        return 'missing'
    if shutil.which('git') is None:
        return 'no-git'
    code, out, _ = run(git_cmd(path, 'rev-parse', '--is-inside-work-tree'))
    if code == 0 and out.strip() == 'true':
        return 'worktree'
    code, out, _ = run(git_cmd(path, 'rev-parse', '--is-bare-repository'))
    if code == 0 and out.strip() == 'true':
        return 'bare'
    return 'not-a-repo'


def default_repo():
    if shutil.which('git') is None:
        return os.getcwd()
    code, out, _ = run(['git', '--no-optional-locks', 'rev-parse', '--show-toplevel'], cwd=os.getcwd())
    if code == 0 and out.strip():
        return out.strip()
    return os.getcwd()


def inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root + os.sep)


def common_dir(path):
    ok, out = try_git(path, 'rev-parse', '--path-format=absolute', '--git-common-dir')
    if not ok:
        ok, out = try_git(path, 'rev-parse', '--git-common-dir')
        if not ok:
            return None
        found = out.strip()
        if not os.path.isabs(found):
            found = os.path.join(path, found)
        return os.path.realpath(found)
    return os.path.realpath(out.strip())


def repo_name(repo):
    common = common_dir(repo)
    if common and os.path.basename(common) == '.git':
        return os.path.basename(os.path.dirname(common))
    return os.path.basename(os.path.realpath(repo))


def local_branches(repo):
    out = git(repo, 'for-each-ref', '--format=%(refname:short)', 'refs/heads')
    return [line for line in out.splitlines() if line]


def remote_branches(repo):
    out = git(repo, 'for-each-ref', '--format=%(refname:short)', 'refs/remotes')
    return [line for line in out.splitlines() if line and not line.endswith('/HEAD')]


def is_ancestor(repo, ancestor, descendant):
    code, _, err = run(git_cmd(repo, 'merge-base', '--is-ancestor', ancestor, descendant))
    if code == 0:
        return True
    if code == 1:
        return False
    if code is None:
        raise CheckError(err or 'timed out')
    raise CheckError(err.strip().splitlines()[-1] if err.strip() else f'exit {code}')


def default_branch(repo, branches):
    ok, out = try_git(repo, 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD')
    if ok and out.strip():
        short = out.strip().split('/', 1)[-1]
        if short in branches:
            return short
    for candidate in ('main', 'master'):
        if candidate in branches:
            return candidate
    ok, out = try_git(repo, 'rev-parse', '--abbrev-ref', 'HEAD')
    if ok and out.strip() not in ('', 'HEAD') and out.strip() in branches:
        return out.strip()
    return branches[0] if branches else None


def tracking(repo, branch):
    ok, out = try_git(repo, 'rev-parse', '--abbrev-ref', f'{branch}@{{upstream}}')
    if not ok:
        return None
    upstream = out.strip()
    counts = git(repo, 'rev-list', '--left-right', '--count', f'{branch}...{upstream}')
    ahead, behind = (int(part) for part in counts.split())
    return upstream, ahead, behind


def fmt_tracking(info):
    if info is None:
        return 'none'
    upstream, ahead, behind = info
    if ahead and behind:
        return f'{upstream}, ahead {ahead}, behind {behind}'
    if ahead:
        return f'{upstream}, ahead {ahead}'
    if behind:
        return f'{upstream}, behind {behind}'
    return f'{upstream}, even'


def commits_not_on_remotes(repo, branch, has_remote):
    if has_remote:
        out = git(repo, 'log', '--oneline', branch, '--not', '--remotes')
    else:
        out = git(repo, 'log', '--oneline', branch)
    return [line for line in out.splitlines() if line.strip()]


def same_named_remotes(branch, remotes):
    suffix = '/' + branch
    return [remote for remote in remotes if remote.endswith(suffix)]


def branches_section(repo):
    branches = local_branches(repo)
    remotes = remote_branches(repo)
    has_remote = bool(git(repo, 'remote').strip())
    default = default_branch(repo, branches)
    lines = []
    if default:
        lines.append(f'Default branch: `{default}`.')
    else:
        lines.append('No local branch.')
    if not has_remote:
        lines.append('No remote is configured. Nothing has been pushed; every local commit exists only in this clone.')
    lines.append('')
    if not branches:
        lines.append('none')
        return lines
    lines.append(f'| Branch | Commits not on any remote | Upstream | Merged into {default or "default"} |')
    lines.append('| --- | --- | --- | --- |')
    commit_lines = []
    for branch in branches:
        commits = commits_not_on_remotes(repo, branch, has_remote)
        info = tracking(repo, branch)
        upstream = fmt_tracking(info)
        if info is None:
            named = same_named_remotes(branch, remotes)
            if named:
                upstream = 'none; tip is on ' + ', '.join(f'`{name}`' for name in named)
        merged = 'yes' if default and is_ancestor(repo, branch, default) else 'no'
        lines.append(f'| `{branch}` | {len(commits)} | {upstream} | {merged} |')
        if commits:
            shown = '; '.join(f'`{line.split(" ", 1)[0]}` {line.split(" ", 1)[1]}' if ' ' in line else f'`{line}`'
                               for line in commits[:8])
            if len(commits) > 8:
                shown += f'; and {len(commits) - 8} more'
            commit_lines.append(f'- `{branch}`: {shown}')
    lines.append('')
    lines.append('Commits not on any remote:')
    lines.append('')
    lines.extend(commit_lines or ['none'])
    lines.append('')
    lines.append('Unmerged branches pushed to a remote:')
    lines.append('')
    pushed = []
    if has_remote and default:
        for remote in remotes:
            if not is_ancestor(repo, remote, default):
                pushed.append(f'- `{remote}`')
    lines.extend(pushed or ['none'])
    return lines


def parse_worktrees(text):
    records, cur = [], {}
    for line in text.splitlines():
        if not line.strip():
            if cur:
                records.append(cur)
                cur = {}
            continue
        key, _, value = line.partition(' ')
        cur[key] = value
    if cur:
        records.append(cur)
    return records


def dirty_counts(path):
    code, out, err = run(git_cmd(path, 'status', '--porcelain=v1', '--untracked-files=all'))
    if code is None:
        raise CheckError(err or 'timed out')
    if code != 0:
        raise CheckError(err.strip().splitlines()[-1] if err.strip() else f'exit {code}')
    modified = untracked = 0
    for line in out.splitlines():
        if not line:
            continue
        if line.startswith('??'):
            untracked += 1
        else:
            modified += 1
    return modified, untracked


def codex_worktrees(repo):
    home = os.environ.get('HOME') or ''
    base = os.path.join(home, '.codex', 'worktrees') if home else ''
    if not base or not os.path.isdir(base):
        return []
    name = repo_name(repo)
    ours = common_dir(repo)
    if not ours:
        return []
    found = []
    try:
        children = sorted(os.listdir(base))
    except OSError as exc:
        raise CheckError(str(exc)) from exc
    for child in children:
        candidate = os.path.join(base, child, name)
        if not os.path.isdir(candidate) or os.path.islink(candidate):
            continue
        theirs = common_dir(candidate)
        if theirs and theirs == ours:
            found.append(os.path.realpath(candidate))
    return found


def worktrees_section(repo):
    text = git(repo, 'worktree', 'list', '--porcelain')
    rows = []
    seen = set()
    main = None
    for rec in parse_worktrees(text):
        path = rec.get('worktree')
        if not path:
            continue
        real = os.path.realpath(path)
        if main is None:
            main = real
        seen.add(real)
        branch = rec.get('branch', '')
        if branch.startswith('refs/heads/'):
            branch = branch[len('refs/heads/'):]
        elif 'detached' in rec:
            branch = 'detached'
        else:
            branch = branch or 'unknown'
        rows.append((real, branch, real == main))
    for path in codex_worktrees(repo):
        if path in seen:
            continue
        seen.add(path)
        ok, out = try_git(path, 'rev-parse', '--abbrev-ref', 'HEAD')
        branch = out.strip() if ok and out.strip() else 'unknown'
        if branch == 'HEAD':
            branch = 'detached'
        rows.append((path, branch, False))
    lines = ['| Path | Branch | Dirty |', '| --- | --- | --- |']
    if not rows:
        return ['none']
    for path, branch, is_main in rows:
        label = ' (main worktree)' if is_main else ''
        try:
            modified, untracked = dirty_counts(path)
        except CheckError as exc:
            dirty = f'could not check: {exc}'
        else:
            dirty = 'clean' if modified == untracked == 0 else f'dirty: {modified} modified, {untracked} untracked'
        lines.append(f'| `{path}` | `{branch}` | {dirty}{label} |')
    return lines


def stashes_section(repo):
    out = git(repo, 'stash', 'list')
    lines = [f'- `{line}`' for line in out.splitlines() if line.strip()]
    return lines or ['none']


def git_z(repo, *args):
    out = git(repo, *args)
    return [item for item in out.split('\0') if item]


def safe_size(path, repo_root):
    """Byte size of path. Symlinks are never followed, in or out of the repo."""
    try:
        st = os.lstat(path)
    except OSError:
        return 0
    if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
        return st.st_size
    total = 0
    root = os.path.realpath(repo_root)
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        kept = []
        for name in dirnames:
            child = os.path.join(dirpath, name)
            try:
                child_st = os.lstat(child)
            except OSError:
                continue
            if stat.S_ISLNK(child_st.st_mode):
                total += child_st.st_size
                continue
            real = os.path.realpath(child)
            if real != root and not real.startswith(root + os.sep):
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            child = os.path.join(dirpath, name)
            try:
                total += os.lstat(child).st_size
            except OSError:
                continue
    return total


def is_rebuildable(rel):
    return any(part in REBUILDABLE for part in rel.strip('/').split('/'))


def group_paths(paths, repo):
    groups = {}
    for rel in paths:
        rel = rel.strip()
        if not rel or rel == '.scratch' or rel.startswith('.scratch/'):
            continue
        top = rel.split('/', 1)[0].rstrip('/')
        path = os.path.join(repo, rel.rstrip('/'))
        bucket = groups.setdefault(top, {'size': 0, 'rebuildable': False})
        bucket['size'] += safe_size(path, repo)
        if is_rebuildable(rel):
            bucket['rebuildable'] = True
    return groups


def table_for(groups):
    if not groups:
        return ['none']
    lines = ['| Top-level | Size | Note |', '| --- | --- | --- |']
    for name in sorted(groups):
        note = 'rebuildable' if groups[name]['rebuildable'] else ''
        lines.append(f'| `{name}` | {groups[name]["size"]} bytes | {note} |')
    return lines


def files_section(repo):
    untracked = git_z(repo, 'ls-files', '-z', '--others', '--exclude-standard')
    ignored = git_z(repo, 'ls-files', '-z', '--others', '--ignored', '--exclude-standard', '--directory')
    lines = ['### untracked', '']
    lines.extend(table_for(group_paths(untracked, repo)))
    lines.append('')
    lines.append('### ignored')
    lines.append('')
    lines.extend(table_for(group_paths(ignored, repo)))
    lines.append('')
    lines.append('### .scratch')
    lines.append('')
    scratch = os.path.join(repo, '.scratch')
    if os.path.isdir(scratch) and not os.path.islink(scratch):
        size = safe_size(scratch, repo)
        lines.append(f'`.scratch/` is {size} bytes. The setup syncs this folder. '
                     'Do not edit `.scratch/README.md` or `.scratch/.gitignore`.')
    elif os.path.lexists(scratch):
        lines.append('`.scratch/` is a symlink. It was not followed. The setup syncs a real `.scratch/` folder. '
                     'Do not edit `.scratch/README.md` or `.scratch/.gitignore`.')
    else:
        lines.append('`.scratch/` is not present. The setup creates it and owns `.scratch/README.md` and '
                     '`.scratch/.gitignore`; do not edit those markers.')
    return lines


def is_script_or_config(rel, repo):
    name = os.path.basename(rel)
    if name in SCRIPT_NAMES or os.path.splitext(name)[1] in SCRIPT_EXT:
        return True
    if 'scripts' in rel.split('/') or 'bin' in rel.split('/'):
        return True
    path = os.path.join(repo, rel)
    try:
        with open(path, 'rb') as handle:
            return handle.read(2) == b'#!'
    except OSError:
        return False


def is_env_name(name):
    return name == '.env' or name.startswith('.env.')


def path_tokens(text, home):
    found = []
    found.extend(re.findall(r'(?:/Users|/home)/[^\s\'"`$\\;|&<>()]+', text))
    found.extend(re.findall(r'(?:\$HOME|~)/[^\s\'"`$\\;|&<>()]+', text))
    prefixes = []
    if home:
        prefixes.append(home.rstrip('/'))
        real = os.path.realpath(home)
        if real.rstrip('/') not in prefixes:
            prefixes.append(real.rstrip('/'))
    for prefix in prefixes:
        if len(prefix) < 2:
            continue
        found.extend(re.findall(re.escape(prefix) + r'(?:/[^\s\'"`$\\;|&<>()]+)+', text))
    return found


def resolve_token(token, home):
    home = (home or '').rstrip('/')
    if token.startswith('$HOME'):
        token = home + token[len('$HOME'):]
    elif token.startswith('~/'):
        token = os.path.join(home, token[2:])
    token = token.rstrip('.,:')
    if not token.startswith('/'):
        return None
    return token


def outside_paths_section(repo):
    home = os.environ.get('HOME', '')
    ok, listed = try_git(repo, 'ls-files', '-z')
    if not ok:
        raise CheckError(listed.strip().splitlines()[-1] if listed.strip() else 'git ls-files failed')
    named = {}
    for rel in listed.split('\0'):
        if not rel or is_env_name(os.path.basename(rel)):
            continue
        if not is_script_or_config(rel, repo):
            continue
        path = os.path.join(repo, rel)
        try:
            st = os.lstat(path)
        except OSError:
            continue
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode) or st.st_size > READ_CAP:
            if st.st_size > READ_CAP:
                named.setdefault(None, []).append(rel)
            continue
        try:
            text = open(path, 'r', encoding='utf-8', errors='replace').read(READ_CAP)
        except OSError:
            continue
        for token in path_tokens(text, home):
            resolved = resolve_token(token, home)
            if not resolved or not os.path.exists(resolved):
                continue
            if inside(resolved, repo):
                continue
            named.setdefault(os.path.abspath(resolved), []).append(rel)
    skipped = named.pop(None, [])
    if not named and not skipped:
        return ['none']
    lines = []
    if named:
        lines.extend(['| Path | Named in |', '| --- | --- |'])
        for path in sorted(named):
            files = ', '.join(f'`{name}`' for name in sorted(set(named[path])))
            lines.append(f'| `{path}` | {files} |')
    for rel in skipped:
        lines.append(f'could not check: `{rel}` is too large to scan')
    return lines or ['none']


def env_files(repo):
    found = []
    for dirpath, dirnames, filenames in os.walk(repo, followlinks=False):
        kept = []
        for name in dirnames:
            child = os.path.join(dirpath, name)
            if name == '.git' or os.path.islink(child):
                continue
            real = os.path.realpath(child)
            if not inside(real, repo):
                continue
            kept.append(name)
        dirnames[:] = [name for name in kept if name not in REBUILDABLE]
        for name in filenames:
            if is_env_name(name) and not os.path.islink(os.path.join(dirpath, name)):
                found.append(os.path.relpath(os.path.join(dirpath, name), repo))
    return sorted(set(found))


def env_section(repo):
    lines = [
        'The setup copies gitignored `.env` files to the Codespace at `task work:cs` and never overwrites them. '
        'Do not copy them into `.scratch`. Names only:',
        '',
    ]
    names = env_files(repo)
    lines.extend(f'- `{name}`' for name in names)
    if not names:
        lines.append('none')
    return lines


def parse_tasks(text):
    names = set()
    in_tasks = False
    base = key_indent = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        indent = len(line) - len(line.lstrip(' \t'))
        stripped = line.strip()
        if re.match(r'^tasks:\s*(#.*)?$', stripped):
            in_tasks = True
            base = indent
            key_indent = None
            continue
        if not in_tasks:
            continue
        if indent <= base:
            in_tasks = False
            continue
        if key_indent is None:
            key_indent = indent
        if indent != key_indent:
            continue
        match = re.match(r'^["\']?([A-Za-z0-9_.:-]+)["\']?\s*:', stripped)
        if match:
            names.add(match.group(1))
    return names


def tasks_at(repo, rev):
    names = set()
    for name in TASKFILES:
        ok, out = try_git(repo, 'show', f'{rev}:{name}')
        if ok:
            names |= parse_tasks(out)
    return names


def find_named(repo, names):
    found = []
    for dirpath, dirnames, filenames in os.walk(repo, followlinks=False):
        kept = []
        for name in dirnames:
            child = os.path.join(dirpath, name)
            if name == '.git' or name in REBUILDABLE or os.path.islink(child):
                continue
            if not inside(os.path.realpath(child), repo):
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            if name in names and not os.path.islink(os.path.join(dirpath, name)):
                found.append(os.path.join(dirpath, name))
    return found


def mention_places(repo, task):
    files = []
    memory = os.path.join(repo, '.scratch', 'memory')
    if os.path.isdir(memory) and not os.path.islink(memory):
        for dirpath, dirnames, filenames in os.walk(memory, followlinks=False):
            dirnames[:] = [name for name in dirnames
                           if not os.path.islink(os.path.join(dirpath, name))]
            files.extend(os.path.join(dirpath, name) for name in filenames
                         if not os.path.islink(os.path.join(dirpath, name)))
    files.extend(find_named(repo, {'CLAUDE.md', 'AGENTS.md'}))
    token = re.compile(r'(?<![A-Za-z0-9_.:-])' + re.escape(task) + r'(?![A-Za-z0-9_.:-])')
    places = []
    seen = set()
    for path in files:
        if path in seen:
            continue
        seen.add(path)
        try:
            with open(path, 'rb') as handle:
                data = handle.read(READ_CAP)
        except OSError:
            continue
        if b'\0' in data[:8192]:
            continue
        rel = os.path.relpath(path, repo)
        for number, line in enumerate(data.decode('utf-8', 'replace').splitlines(), 1):
            if token.search(line):
                places.append(f'{rel}:{number}')
    return places


def tasks_section(repo):
    branches = local_branches(repo)
    default = default_branch(repo, branches)
    if not default:
        return ['could not check: no default branch']
    base = tasks_at(repo, default)
    defined = {}
    revs = list(branches)
    revs.extend(remote_branches(repo))
    for rev in revs:
        if rev == default:
            continue
        try:
            unmerged = not is_ancestor(repo, rev, default)
        except CheckError:
            continue
        if not unmerged:
            continue
        for task in tasks_at(repo, rev) - base:
            defined.setdefault(task, []).append(rev)
    if not defined:
        return ['none']
    lines = ['| Task | Defined on | Mentioned in |', '| --- | --- | --- |']
    for task in sorted(defined):
        where = ', '.join(f'`{rev}`' for rev in defined[task])
        places = mention_places(repo, task)
        mentioned = ', '.join(f'`{place}`' for place in places) if places else 'nowhere'
        lines.append(f'| `{task}` | {where} | {mentioned} |')
    return lines


def locally_built(data):
    if (data.get('Comment') or '') == 'buildkit.dockerfile.v0':
        return True
    identity = data.get('Identity') or {}
    if identity.get('Build'):
        return True
    return not data.get('RepoDigests')


def docker_section(repo):
    if shutil.which('docker') is None:
        return None
    code, out, err = run(['docker', 'image', 'ls', '--format', '{{.Repository}}\t{{.Tag}}\t{{.ID}}'],
                         timeout=DOCKER_TIMEOUT)
    if code is None:
        raise CheckError(err or 'timed out')
    if code != 0:
        raise CheckError(err.strip().splitlines()[-1] if err.strip() else f'docker image ls exited {code}')
    needle = repo_name(repo).casefold()
    matches = []
    for line in out.splitlines():
        parts = line.split('\t')
        if len(parts) < 3:
            continue
        repository, tag, image_id = parts[0], parts[1], parts[2]
        if not repository or repository == '<none>':
            continue
        if needle and needle in repository.casefold():
            matches.append((repository, tag, image_id))
    rows = []
    for repository, tag, image_id in matches:
        code, out, err = run(['docker', 'image', 'inspect', image_id], timeout=DOCKER_TIMEOUT)
        if code != 0 or not out.strip():
            rows.append((f'{repository}:{tag}', 'could not check'))
            continue
        try:
            data = json.loads(out)[0]
        except (json.JSONDecodeError, IndexError, TypeError) as exc:
            raise CheckError(f'docker image inspect: {exc}') from exc
        if not locally_built(data):
            continue
        ref = repository if not tag or tag == '<none>' else f'{repository}:{tag}'
        arch = f"{data.get('Os') or '?'}/{data.get('Architecture') or '?'}"
        rows.append((ref, arch))
    if not rows:
        return ['none']
    lines = ['| Image | Architecture |', '| --- | --- |']
    lines.extend(f'| `{ref}` | {arch} |' for ref, arch in rows)
    return lines


PRODUCERS = (
    ('branches', branches_section),
    ('worktrees', worktrees_section),
    ('stashes', stashes_section),
    ('untracked and ignored files', files_section),
    ('paths outside the repo', outside_paths_section),
    ('env files', env_section),
    ('branch-only tasks', tasks_section),
    ('docker', docker_section),
)


def section_block(title, producer, repo):
    lines = [f'## {title}', '']
    try:
        body = producer(repo)
    except CheckError as exc:
        body = [f'could not check: {exc}']
    except Exception as exc:
        body = [f'could not check: {type(exc).__name__}: {exc}']
    if body is None:
        return []
    lines.extend(body)
    lines.append('')
    return lines


def not_a_repo_report(path, kind):
    if kind == 'bare':
        reason = f'`{path}` is a bare repository, not a work tree.'
    elif kind == 'no-git':
        reason = 'git is not on PATH.'
    elif kind == 'missing':
        reason = f'`{path}` is not a git repository.'
    else:
        reason = f'`{path}` is not a git repository.'
    lines = ['# codespace-ready inventory', '', reason, '']
    for title in SECTIONS:
        if title == 'docker' and shutil.which('docker') is None:
            continue
        lines.extend([f'## {title}', '', 'could not check: not a git repository', ''])
    return '\n'.join(lines).rstrip() + '\n'


def render(path):
    path = os.path.abspath(path)
    kind = classify(path)
    if kind != 'worktree':
        return not_a_repo_report(path, kind)
    try:
        top = git(path, 'rev-parse', '--show-toplevel').strip()
    except CheckError as exc:
        return f'# codespace-ready inventory\n\ncould not check: {exc}\n'
    lines = ['# codespace-ready inventory', '', f'Repo: `{os.path.realpath(top)}`', '']
    for title, producer in PRODUCERS:
        lines.extend(section_block(title, producer, top))
    return '\n'.join(lines).rstrip() + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Read-only inventory of what a Codespace move must carry. Never writes, fetches or pushes.')
    parser.add_argument('--repo', help="Repository path (default: the current directory's Git top level).")
    args = parser.parse_args(argv)
    repo = args.repo or default_repo()
    try:
        sys.stdout.write(render(repo))
    except BrokenPipeError:
        return 0
    except Exception as exc:
        sys.stdout.write(f'could not check: {type(exc).__name__}: {exc}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
