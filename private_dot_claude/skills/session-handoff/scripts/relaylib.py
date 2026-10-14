"""Relay facts shared by relay-check.py and relay-gate.py: the safe-point blockers and this session's relays.

Stdlib only. The CLIs run under `python3 -I` and put this directory on sys.path before importing it.
"""
import glob
import json
import os
import subprocess
import time

GIT_BUSY = ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply')
# Piece 1 waits at most 20 minutes for a receipt and 15 per fix round, and each wait starts from a fresh file
# (launch.json, fix-<round>): a relay dir with no activity for longer is abandoned.
ABANDONED_AFTER = 25 * 60
ACTIVITY = ('checklist.json', 'launch.json', 'receipt.json', 'fix-*', 'fired/*')
GIT_BOUND = 2   # seconds: the gate runs git on the Stop path, inside its 7 s budget


def run(cmd, timeout=GIT_BOUND):
    """(exit code, stripped stdout); (None, '') when cmd does not finish within timeout seconds."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, ''
    return r.returncode, r.stdout.strip()


def blockers(repo, tasks):
    """Why a relay may not start now: an agent or workflow running inside this session (tasks are
    transcript.open_tasks records), or the repo mid-merge, rebase, cherry-pick or revert.

    A git that fails or does not answer within GIT_BOUND cannot tell: it adds no line."""
    out = ['%s %s is running inside this session (%s)' % (t['kind'], t['id'], t['description'] or t['command'][:60])
           for t in tasks if t['kind'] in ('agent', 'workflow')]
    code, gitdir = run(['git', '-C', repo, 'rev-parse', '--absolute-git-dir'])
    if code == 0:
        out += ['git is mid-operation (%s present)' % name for name in GIT_BUSY
                if os.path.exists(os.path.join(gitdir, name))]
    return out


def read_json(path):
    with open(path) as fh:
        return json.load(fh)


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _failure(path):
    """stage and reason of a failed.json; an unreadable one is a failure with neither."""
    try:
        data = read_json(path)
    except (OSError, ValueError):
        data = None
    data = data if isinstance(data, dict) else {}
    stage, reason = data.get('stage'), data.get('reason')
    return (stage if isinstance(stage, str) else None), (reason if isinstance(reason, str) else None)


def classify(rdir, now):
    """One relay dir, by fact: closed, failed, abandoned, frozen or in_progress.

    A later closed.json supersedes a failed.json. A failed.json beside handover.md is a hand-over failure whatever
    stage it names (the stage is written free-form). The failure time is failed.json's mtime (both writers make one;
    its `at` field is free-form and never parsed), or the last activity of an abandoned dir."""
    entry = {'id': os.path.basename(rdir), 'dir': rdir, 'state': None, 'stage': None, 'reason': None,
             'failed_at': None, 'handover_at': None}
    failed = os.path.join(rdir, 'failed.json')
    handover = os.path.join(rdir, 'handover.md')
    if os.path.exists(os.path.join(rdir, 'closed.json')):
        entry['state'] = 'closed'
    elif os.path.exists(failed):
        entry['state'], entry['failed_at'] = 'failed', _mtime(failed)
        entry['stage'], entry['reason'] = _failure(failed)
        if os.path.exists(handover):
            entry['stage'] = 'handover'
    elif os.path.exists(handover):
        entry['state'], entry['handover_at'] = 'frozen', _mtime(handover)
    else:
        times = [t for pattern in ACTIVITY for path in glob.glob(os.path.join(glob.escape(rdir), pattern))
                 if (t := _mtime(path)) is not None]
        newest = max(times) if times else None
        if newest is None or now - newest >= ABANDONED_AFTER:
            entry['state'], entry['failed_at'] = 'abandoned', newest if newest is not None else now
        else:
            entry['state'] = 'in_progress'
    return entry


def relays_of(project_dir, session_id, now=None):
    """The relay dirs under <project_dir>/relay/ whose checklist names this session as the predecessor."""
    now = time.time() if now is None else now
    out = []
    for path in sorted(glob.glob(os.path.join(glob.escape(project_dir), 'relay', '*', 'checklist.json'))):
        try:
            chk = read_json(path)
        except (OSError, ValueError):
            continue
        pred = chk.get('predecessor') if isinstance(chk, dict) else None
        if isinstance(pred, dict) and pred.get('session_id') == session_id:
            out.append(classify(os.path.dirname(path), now))
    return out


def will_repeat(entry):
    """A failure an automatic retry would meet again: an identity mismatch at the check, or a taken agent name."""
    reason = entry.get('reason') or ''
    return 'agent_name_taken' in reason or (entry.get('stage') == 'check' and 'identity:' in reason)
