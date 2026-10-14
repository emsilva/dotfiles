#!/usr/bin/env python3
"""Launch, dispatch, track and wait on herdr workers. The record is herdlib's (<project>/herd.jsonl).

  launch   ROLE [--kind codex|claude] [--builder --base REF [--type T] | --readonly] [--model M] [--effort E]
           [--repo R] [--pane P]
  dispatch NAME --brief B --deliverable D [--blocked P] [--reset new|clear]
  status   [--all] [--repo R] [--extra-root DIR ...] [ROOT ...]
  wait     [--marker M] [--fired-dir DIR] [--names N ...] [--interval S]
  adopt    PANE --role R [--model M] [--effort E] [--rename] [--brief B --deliverable D [--blocked P]]
  close    NAME [--reason TEXT]

Run as python3 -I inside the lead's Claude session ($CLAUDE_CODE_SESSION_ID locates the record) and inside herdr.
Exit 0 done; 1 refused or failed (the reason on stderr, nothing recorded); 2 a usage error, an unreadable record
or a failed herdr read.
"""
import argparse
import importlib
import os
import sys

# In development this dir is chezmoi source: bytecode written beside the script would be deployed.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import herdlib  # noqa: E402
import relaylib  # noqa: E402
import transcript  # noqa: E402

# Each command is the module herd_<command>.py, with add_arguments(parser) and run(args) -> exit code.
COMMANDS = ('launch', 'dispatch')


def main(argv=None):
    p = argparse.ArgumentParser(prog='herd.py', description='Launch, dispatch, track and wait on herdr workers.')
    sub = p.add_subparsers(dest='cmd', required=True)
    modules = {}
    for name in COMMANDS:
        module = importlib.import_module('herd_' + name)
        parser = sub.add_parser(name, help=module.__doc__.splitlines()[0])
        module.add_arguments(parser)
        parser.add_argument('--projects', default=transcript.PROJECTS, help=argparse.SUPPRESS)
        parser.add_argument('--record-dir', help=argparse.SUPPRESS)
        modules[name] = module
    a = p.parse_args(argv)
    try:
        return modules[a.cmd].run(a)
    except herdlib.Refusal as e:
        print('herd %s: %s' % (a.cmd, e), file=sys.stderr)
        return 1
    except (herdlib.RecordError, relaylib.HerdrError) as e:
        print('herd %s: %s' % (a.cmd, e), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
