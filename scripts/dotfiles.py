#!/usr/bin/env python3
"""Private recovery snapshots and explicit, fast-forward-only synchronization."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

SOURCE = Path(__file__).resolve().parents[1]

def output(command):
    return subprocess.check_output(command, text=True).strip()

def backup(chezmoi, destination):
    os.umask(0o077)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    folder = destination / '.local/state/dotfiles/backups' / stamp
    if folder.is_relative_to(SOURCE):
        raise SystemExit('Backup directory must be outside the source checkout')
    folder.mkdir(parents=True, mode=0o700)
    managed = output(chezmoi + ['managed', '--include=files,symlinks', '--path-style=relative']).splitlines()
    paths = set(managed + ['.config/chezmoi'])
    selected = []
    for name in sorted(paths, key=lambda p: (len(Path(p).parts), p)):
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise SystemExit('Invalid relative backup path')
        if any(path.is_relative_to(Path(parent)) for parent in selected):
            continue
        if (destination / path).exists() or (destination / path).is_symlink():
            selected.append(name)
    with tarfile.open(folder / 'source.tar.gz', 'w:gz', dereference=False) as archive:
        archive.add(SOURCE, arcname='source')
    with tarfile.open(folder / 'installed.tar.gz', 'w:gz', dereference=False) as archive:
        for name in selected:
            archive.add(destination / name, arcname=name)
    subprocess.run(['git', '-C', str(SOURCE), 'bundle', 'create', str(folder / 'history.bundle'), '--all'], check=True)
    subprocess.run(['git', '-C', str(SOURCE), 'bundle', 'verify', str(folder / 'history.bundle')], check=True, stdout=subprocess.DEVNULL)
    # Preserve link topology above, and separately preserve the bytes behind
    # symlinked private preferences for recovery on a replacement machine.
    names = ['source.tar.gz', 'installed.tar.gz', 'history.bundle']
    preferences = destination / '.config/chezmoi'
    if preferences.exists():
        with tarfile.open(folder / 'machine-config.tar.gz', 'w:gz', dereference=True) as archive:
            archive.add(preferences, arcname='chezmoi')
        names.append('machine-config.tar.gz')
    checksums = {}
    for name in names:
        path = folder / name
        with path.open('rb') as stream:
            checksums[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
        if name.endswith('.tar.gz'):
            with tarfile.open(path) as archive:
                for member in archive:
                    if member.isfile():
                        with archive.extractfile(member) as stream:
                            while stream.read(1024 * 1024):
                                pass
    (folder / 'manifest.json').write_text(json.dumps({'source': str(SOURCE), 'destination': str(destination),
        'head': output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD']), 'installed_paths': selected,
        'sha256': checksums}, indent=2) + '\n')
    print(folder)

def sync(chezmoi):
    git = ['git', '-C', str(SOURCE)]
    if output(git + ['status', '--porcelain']):
        raise SystemExit('Source checkout has local changes; preserve and commit them before sync')
    if output(chezmoi + ['status']):
        raise SystemExit('Installed dotfiles differ; reconcile them before sync')
    if output(git + ['branch', '--show-current']) != 'main':
        raise SystemExit('Sync requires main; review and integrate feature branches explicitly')
    subprocess.run(git + ['fetch', 'origin', 'refs/heads/main:refs/remotes/origin/main'], check=True)
    ahead, behind = map(int, output(git + ['rev-list', '--left-right', '--count', 'HEAD...origin/main']).split())
    if ahead and behind:
        raise SystemExit(f'History diverged: {ahead} local-only and {behind} remote-only commits; ask the owner')
    if ahead:
        raise SystemExit(f'{ahead} local commits await explicit publication; no changes made')
    if behind:
        subprocess.run(git + ['merge', '--ff-only', 'origin/main'], check=True)
        print('Source updated. Run task preview, then task apply when reviewed.')
    else:
        print('Already current.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['backup', 'sync'])
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    chezmoi = ['chezmoi', '--source', str(SOURCE)]
    if args.config:
        chezmoi += ['--config', str(args.config)]
    if args.destination:
        chezmoi += ['--destination', str(args.destination)]
    destination = Path(output(chezmoi + ['execute-template', '{{ .chezmoi.destDir }}'])).resolve()
    if args.operation == 'backup':
        backup(chezmoi, destination)
    else:
        sync(chezmoi)
