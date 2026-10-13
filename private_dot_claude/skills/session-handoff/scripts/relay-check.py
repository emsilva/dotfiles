#!/usr/bin/env python3
"""Relay checklist, receipt comparison, quiet check and lead names.

  name      [--repo DIR] [--suffix S] [--slug SLUG]   print lead-<slug>[-<S>]
  identity                                          this session's identity, as JSON
  checklist --note PATH [--extra-root DIR ...] [--transcript PATH ...]
                                                    write <enc>/relay/<id>/checklist.json; print the dir
  compare   <relay-dir>                             receipt.json vs checklist.json: PASS or one FAIL per line
  quiet     <relay-dir>                             exit 1 if a prompt reached the predecessor after handover.md

Run as python3 -I. checklist and identity read $CLAUDE_CODE_SESSION_ID, $CLAUDE_EFFORT,
$CLAUDE_PID and $HERDR_PANE_ID of the session that runs them.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

# In development this dir is chezmoi source: bytecode written beside the script would be deployed.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcript  # noqa: E402

NAME_ROOM = 32 - len('lead-') - len('-next')   # herdr names are at most 32 characters
GIT_BUSY = ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply')


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def slug(repo, override=None):
    text = override or os.path.basename(os.path.abspath(repo).rstrip('/'))
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-') or 'project'


def lead_name(repo, suffix=None, override=None):
    base = 'lead-' + slug(repo, override)[:NAME_ROOM].rstrip('-')
    return base + ('-' + suffix if suffix else '')


def sha256(path):
    with open(path, 'rb') as fh:
        return hashlib.file_digest(fh, 'sha256').hexdigest()


def settings_mode(repo):
    for path in (os.path.join(repo, '.claude', 'settings.local.json'), os.path.join(repo, '.claude', 'settings.json'),
                 os.path.expanduser('~/.claude/settings.json')):
        try:
            mode = json.load(open(path)).get('permissions', {}).get('defaultMode')
        except (OSError, ValueError, AttributeError):
            continue
        if mode:
            return mode
    return 'default'


def herdr_json(*args):
    code, out = run(['herdr', *args])
    if code != 0:
        return {}
    try:
        return json.loads(out)
    except ValueError:
        return {}


def repo_root():
    code, top = run(['git', 'rev-parse', '--show-toplevel'])
    return top if code == 0 and top else os.getcwd()


def git_state(repo):
    _, head = run(['git', '-C', repo, 'rev-parse', '--short', 'HEAD'])
    _, branch = run(['git', '-C', repo, 'rev-parse', '--abbrev-ref', 'HEAD'])
    # Not run(): its strip() would eat the leading space of " M path" and line[3:] would cut the path.
    porcelain = subprocess.run(['git', '-C', repo, 'status', '--porcelain'], capture_output=True, text=True).stdout
    return {'head': head, 'branch': branch, 'dirty': [line[3:] for line in porcelain.splitlines() if line]}


def blockers(repo, tasks):
    out = ['%s %s is running inside this session (%s)' % (t['kind'], t['id'], t['description'] or t['command'][:60])
           for t in tasks if t['kind'] in ('agent', 'workflow')]
    code, gitdir = run(['git', '-C', repo, 'rev-parse', '--absolute-git-dir'])
    if code == 0:
        out += ['git is mid-operation (%s present)' % name for name in GIT_BUSY
                if os.path.exists(os.path.join(gitdir, name))]
    return out


def workers(repo, extra_roots, self_pane):
    _, listing = run(['git', '-C', repo, 'worktree', 'list', '--porcelain'])
    roots = [line[len('worktree '):] for line in listing.splitlines() if line.startswith('worktree ')] or [repo]
    roots = [os.path.realpath(r).rstrip('/') for r in roots + list(extra_roots)]
    names = {a.get('pane_id'): a.get('name') for a in herdr_json('agent', 'list').get('result', {}).get('agents', [])}
    out = []
    for p in herdr_json('pane', 'list').get('result', {}).get('panes', []):
        cwd = os.path.realpath(p.get('cwd') or '/').rstrip('/')
        if p.get('pane_id') == self_pane or not any(cwd == r or cwd.startswith(r + '/') for r in roots):
            continue
        out.append({'pane_id': p['pane_id'], 'name': names.get(p['pane_id']), 'kind': p.get('agent', 'shell'),
                    'status': p.get('agent_status'), 'session_id': (p.get('agent_session') or {}).get('value'),
                    'cwd': p.get('cwd')})
    return out


def new_relay_dir(project_dir, now):
    base = os.path.join(project_dir, 'relay', now.strftime('%Y%m%dT%H%M%SZ'))
    path, n = base, 1
    while True:
        try:
            os.makedirs(path)
            return path
        except FileExistsError:
            n += 1
            path = '%s-%d' % (base, n)


def own_transcript(a):
    session = os.environ.get('CLAUDE_CODE_SESSION_ID')
    if not session:
        sys.exit('relay-check: CLAUDE_CODE_SESSION_ID is not set; run this inside the Claude session')
    return session, transcript.find_transcript(session, a.projects)


def cmd_name(a):
    print(lead_name(a.repo, a.suffix, a.slug))
    return 0


def cmd_identity(a):
    session, tpath = own_transcript(a)
    print(json.dumps({'session_id': session, 'pane_id': os.environ.get('HERDR_PANE_ID'),
                      'model': transcript.last_model(tpath), 'effort': os.environ.get('CLAUDE_EFFORT'),
                      'permission_mode': transcript.permission_mode(tpath) or settings_mode(repo_root())}))
    return 0


def cmd_checklist(a):
    session, tpath = own_transcript(a)
    repo = os.path.realpath(repo_root())
    paths = a.transcript + [tpath]
    tasks = transcript.open_tasks(paths)
    blocked = blockers(repo, tasks)
    if blocked:
        for line in blocked:
            print('relay-check: not yet: %s' % line, file=sys.stderr)
        return 3
    self_pane = os.environ.get('HERDR_PANE_ID')
    me = herdr_json('agent', 'get', self_pane).get('result', {}).get('agent', {}) if self_pane else {}
    now = datetime.datetime.now(datetime.timezone.utc)
    rdir = new_relay_dir(os.path.dirname(tpath), now)
    pid = os.environ.get('CLAUDE_PID', '')
    data = {
        'relay_id': os.path.basename(rdir),
        'created_at': now.isoformat().replace('+00:00', 'Z'),
        'repo': repo,
        'predecessor': {
            'session_id': session, 'transcript': tpath, 'pane_id': self_pane, 'herdr_name': me.get('name'),
            'herdr_session': (me.get('agent_session') or {}).get('value'),
            'model': transcript.last_model(tpath), 'effort': os.environ.get('CLAUDE_EFFORT'),
            'permission_mode': transcript.permission_mode(tpath) or settings_mode(repo),
            'pid': int(pid) if pid.isdigit() else None},
        'git': git_state(repo),
        'note': {'path': os.path.abspath(a.note), 'sha256': sha256(a.note)},
        'background_tasks': tasks,
        'crons': transcript.open_crons(paths),
        'workers': workers(repo, a.extra_root, self_pane),
        'recent_prompts': transcript.prompts(tpath)[-3:],
    }
    with open(os.path.join(rdir, 'checklist.json'), 'w') as fh:
        json.dump(data, fh, indent=1)
    print(rdir)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description='Relay checklist, receipt comparison, quiet check and lead names.')
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('name')
    s.add_argument('--repo', default='.')
    s.add_argument('--suffix')
    s.add_argument('--slug')
    sub.add_parser('identity')
    s = sub.add_parser('checklist')
    s.add_argument('--note', required=True)
    s.add_argument('--extra-root', action='append', default=[])
    s.add_argument('--transcript', action='append', default=[])
    for parser in sub.choices.values():
        parser.add_argument('--projects', default=transcript.PROJECTS, help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    return {'name': cmd_name, 'identity': cmd_identity, 'checklist': cmd_checklist}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
