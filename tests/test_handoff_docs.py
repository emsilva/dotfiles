import json
import os
import re
import subprocess
import tempfile
import unittest

from handoff_fixtures import SCRIPTS, SOURCE

SKILL = SOURCE / 'private_dot_claude/skills/session-handoff'


class HandoffDocsTests(unittest.TestCase):
    def test_both_checklist_tables_include_an_unreadable_herd_record(self):
        text = (SKILL / 'references/relay.md').read_text()
        failure = text[text.index('## Failure table'):text.index('## Script exit codes')]
        row = next(line for line in failure.splitlines() if '`checklist` exit 2' in line)
        self.assertIn('herd record', row)
        exits = text[text.index('## Script exit codes'):]
        row = next(line for line in exits.splitlines() if line.startswith('| `relay-check.py checklist`'))
        self.assertIn('herd record', row.split('|')[4])

    def test_the_pane_reuse_launch_example_supplies_the_role(self):
        text = (SOURCE / 'private_dot_claude/CLAUDE.md').read_text()
        row = next(line for line in text.splitlines() if line.startswith('- **Reuse panes, recycle context.**'))
        self.assertIn('`herd.py launch <role> --pane <id>`', row)

    def test_every_script_the_docs_name_exists(self):
        text = ''.join((SKILL / name).read_text() for name in ('SKILL.md', 'references/relay.md', 'references/feedback.md'))
        named = set(re.findall(r'scripts/([\w.-]+\.(?:py|sh))', text))
        self.assertTrue(named >= {'bg-tasks.py', 'memory-check.py', 'relay-check.py', 'relay-launch.sh',
                                  'relay-close.sh', 'herd.py'}, named)
        for name in named:
            self.assertTrue((SCRIPTS / name).exists(), name)

    def test_template_sections_and_the_compact_advice_is_gone(self):
        text = (SKILL / 'SKILL.md').read_text()
        for section in ('## Backlog', '## Memory', '## Relay Q&A', '## Pickup gaps', '## RELAY mode'):
            self.assertIn(section, text)
        self.assertNotIn('compact instead', text)

    def test_relay_command_routes_to_relay_mode(self):
        text = (SOURCE / 'private_dot_claude/commands/relay.md').read_text()
        self.assertIn('`session-handoff`', text)
        self.assertIn('RELAY mode', text)

    def test_claude_md_waits_on_a_fresh_report_and_routes_relay(self):
        text = (SOURCE / 'private_dot_claude/CLAUDE.md').read_text()
        self.assertNotIn('"report file exists AND', text)
        self.assertIn('written by this dispatch', text)
        self.assertIn('`/relay`', text)

    def test_claude_md_launches_dispatches_waits_and_closes_through_herd_py(self):
        text = ' '.join((SOURCE / 'private_dot_claude/CLAUDE.md').read_text().split())
        for needle in ('herd.py launch <role> [--builder --base <ref> | --readonly]',
                       '`herd.py dispatch <name> --brief <brief> --deliverable <report>`', '`herd.py wait`',
                       '`herd.py close <name>`', 'The worker table is `herd.py status`',
                       'Never launch a worker with raw `herdr agent start`',
                       'always `--builder`: Claude has no sandbox, so read-only work goes to Codex',
                       '**Review: the builder first, then the lead.**',
                       'The lead then reviews the actual diff, not just the results',
                       'or when the lead wrote the code itself'):
            self.assertIn(needle, text)
        self.assertNotIn('Implementer and reviewer are different workers', text)
        self.assertNotIn('herdr agent start <role>-xhigh --kind codex', text)

    def test_relay_md_states_the_waiter_rules_compare_enforces(self):
        # compare accepts only markers with this relay's prefix, live or with a fired/ file;
        # relay-launch needs a Bash timeout above its two 90 s start attempts and their busy-pane retries.
        text = (SKILL / 'references/relay.md').read_text()
        for needle in ('fired/', 'relay-<relay-id>-w', '300000', 'agent_pane_busy'):
            self.assertIn(needle, text)
        spec = (SOURCE / 'docs/superpowers/specs/2026-10-12-session-relay-design.md').read_text()
        self.assertIn('agent_pane_busy', spec)

    def test_receipt_waits_are_bounded(self):
        # A successor that dies or blocks before its receipt must not hold the predecessor's wait forever.
        text = (SKILL / 'references/relay.md').read_text()
        for needle in ('"stage": "receipt"', '+ 1200 ))', '+ 900', 'agent_status'):
            self.assertIn(needle, text)

    def test_receipt_wait_tolerates_a_brief_blocked_or_unknown_successor(self):
        # A successor waiting on an approval shows `blocked`; only a persistent block ends the wait,
        # and only idle or done with a fresh receipt counts as finished (never `unknown`).
        text = (SKILL / 'references/relay.md').read_text()
        for needle in ('blocked) [ "$n" -ge 8 ]', 'idle|done) [ "$receipt" -nt "$anchor" ]'):
            self.assertIn(needle, text)

    def test_every_documented_herdr_read_in_a_wait_loop_is_bounded(self):
        # A hung `herdr agent get` must not freeze a wait loop past its deadline: the read times out,
        # python exits non-zero and `|| echo unread` reports it. Both loops (the predecessor's receipt wait,
        # the successor's close retry) carry the same line.
        text = (SKILL / 'references/relay.md').read_text()
        reads = [line.strip() for line in text.splitlines() if line.strip().startswith('status_of() {')]
        self.assertEqual(len(reads), 2, reads)
        self.assertEqual(len(set(reads)), 1, reads)
        self.assertIn('timeout=10', reads[0])
        self.assertTrue(reads[0].endswith('2>/dev/null || echo unread; }'), reads[0])
        self.assertNotIn('subprocess.run(["herdr", "agent", "get", sys.argv[1]], capture_output=True, text=True)',
                         text)

    def test_disagreements_are_defined_answered_and_cleared(self):
        # compare fails on any open disagreement: the protocol must say what one is, who answers it and
        # when the successor removes it, or a relay can only fail on it.
        text = ' '.join((SKILL / 'references/relay.md').read_text().split())
        for needle in ('a **disagreement** says the note or `checklist.json` is wrong about reality',
                       'answer each disagreement',
                       'Remove each answered entry from `questions` and `disagreements`'):
            self.assertIn(needle, text)

    def test_the_failure_branch_checks_the_panes_session_before_closing_it(self):
        # Pane ids can change after a herdr restore: closing launch.json's pane_id unchecked could close a worker.
        text = ' '.join((SKILL / 'references/relay.md').read_text().split())
        check = text.index("Check the pane's session before closing it")
        identity = text.index("the answer's `agent_session.value` equals `launch.json`'s `session_id`, or its "
                              "`name` equals `launch.json`'s `name`")
        close = text.index('herdr pane close <pane>')
        self.assertLess(check, identity)
        self.assertLess(identity, close)
        for needle in ('do not close the pane', '"successor_close_reason"'):
            self.assertIn(needle, text[check:])

    def test_the_hand_over_send_is_confirmed_before_the_waiters_stop(self):
        # Crons go before handover.md (a later fire is a prompt after the hand-over); waiters stop only after a
        # confirmed send, so a failed send never leaves the lead with no session holding it.
        text = ' '.join((SKILL / 'references/relay.md').read_text().split())
        step = text[text.index('9. **Hand-over**'):text.index('10. **After the hand-over**')]
        order = [step.index(s) for s in ('`CronDelete` each', 'Write `<relay-dir>/handover.md`',
                                         'you have the lead.` with `herdr agent prompt',
                                         'check its exit status', 'send it once more', '`TaskStop` each')]
        self.assertEqual(order, sorted(order), order)
        self.assertIn('"stage": "handover"', step)
        self.assertIn('do not stop your waiters', step)
        outline = ' '.join((SKILL / 'SKILL.md').read_text().split())
        outline = outline[outline.index('7. Hand-over'):outline.index('## Red flags')]
        order = [outline.index(s) for s in ('delete your session crons', 'write `<relay-dir>/handover.md`',
                                            'check the send', 'stop your own waiters')]
        self.assertEqual(order, sorted(order), order)

    def test_the_spec_carries_the_protocol_relay_md_adds(self):
        # The spec binds piece 2: what relay.md adds to the protocol must be in it too.
        spec = ' '.join((SOURCE / 'docs/superpowers/specs/2026-10-12-session-relay-design.md').read_text().split())
        self.assertFalse('`relay-check.py checklist <relay-dir>`' in spec, 'the spec keeps the old checklist header')
        for needle in ('`relay-check.py checklist --note PATH [--git-repo DIR] [--extra-root DIR ...] [--transcript PATH ...]`',
                       '`<relay-dir>/fix-<round>`', '(`CronDelete`)', 'Resume the note `checklist.json` names',
                       'it never types into the old pane', '10-second timeout', '`agent_session.value` equal to',
                       '`successor_close_reason`', 'check its exit status; retry once', '"stage": "handover"',
                       'A **disagreement** says the note or `checklist.json` is wrong about reality'):
            self.assertIn(needle, spec)

    def test_waiters_stay_attached_to_the_session_they_wake(self):
        # A nohup/& waiter fires without waking anyone, and compare FAILs it unless it descends from the receipt's
        # successor pid: relay.md, the successor outline, CLAUDE.md and the spec must all say to keep waiters
        # run_in_background (CLAUDE.md's "detach long work" rule pulled a real successor the other way).
        relay = ' '.join((SKILL / 'references/relay.md').read_text().split())
        self.assertIn("Arm every waiter with the Bash tool's `run_in_background`, never `nohup` or `&`", relay)
        skill = ' '.join((SKILL / 'SKILL.md').read_text().split())
        self.assertIn('arm your own waiters with `run_in_background`', skill)
        claude = ' '.join((SOURCE / 'private_dot_claude/CLAUDE.md').read_text().split())
        self.assertIn('Waiters are not long work: keep them `run_in_background`', claude)
        self.assertNotIn('Short waiters may stay `run_in_background`', claude)
        # Long work is detached, but its .exit file is still waited on by a run_in_background waiter.
        self.assertIn('wait on the `.exit` file with a `run_in_background` waiter, not on the job\'s own task notice',
                      claude)
        self.assertNotIn('not on a task notification', claude)
        for name, text in (('CLAUDE.md', claude), ('SKILL.md', skill)):
            self.assertNotIn('background until-loop', text.replace('`run_in_background` until-loop', ''), name)
        spec = ' '.join((SOURCE / 'docs/superpowers/specs/2026-10-12-session-relay-design.md').read_text().split())
        self.assertIn("descends from the receipt's `successor.pid`", spec)
        self.assertNotIn('pgrep -f', spec)

    def test_automatic_relays_are_documented_where_a_lead_looks(self):
        # The gate is switched on by hand: relay.md must carry the exact registration the spec designs, and a
        # coordinator must learn to name itself lead-<project>, or the gate never sees it.
        relay = (SKILL / 'references/relay.md').read_text()
        spec = (SOURCE / 'docs/superpowers/specs/2026-10-13-relay-gate-design.md').read_text()
        registration = [line.strip() for line in relay.splitlines() if 'relay-gate.py' in line and '"command"' in line]
        self.assertEqual(len(registration), 2, registration)
        for line in registration:
            self.assertIn(line, spec)
        flat = ' '.join(relay.split())
        for needle in ('## Automatic relays (the relay gate)', 'Run /relay now, automatic relay attempt k of 2',
                       'retried once, after 30 minutes', '`select:PushNotification`', 'One lead per project'):
            self.assertIn(needle, flat)
        skill = ' '.join((SKILL / 'SKILL.md').read_text().split())
        self.assertIn('`references/relay.md` § Automatic relays', skill)
        claude = ' '.join((SOURCE / 'private_dot_claude/CLAUDE.md').read_text().split())
        self.assertIn('**Name the coordinator.**', claude)
        self.assertIn('relay-check.py name --repo <repo>', claude)

    def test_the_registration_exits_0_when_the_script_cannot_start(self):
        # A hook's exit 2 blocks: registered before the script is deployed, or after it moved, a Stop hook that
        # cannot start would block every turn end of every session (python3 exits 2 on a missing file).
        spec = (SOURCE / 'docs/superpowers/specs/2026-10-13-relay-gate-design.md').read_text()
        lines = [line.strip() for line in spec.splitlines() if 'relay-gate.py' in line and '"command"' in line]
        self.assertEqual(len(lines), 2, lines)
        with tempfile.TemporaryDirectory() as home:    # a ~ without ~/.claude/skills/session-handoff
            for line in lines:
                [(event, [entry])] = json.loads('{%s}' % line).items()
                command = entry['hooks'][0]['command']
                r = subprocess.run(['sh', '-c', command], input='{}', capture_output=True, text=True,
                                   env={'HOME': home, 'PATH': os.environ['PATH']}, timeout=30)
                self.assertEqual(r.returncode, 0, (event, command, r.stderr))

    def test_the_herd_is_driven_and_recorded_through_herd_py(self):
        # SAVE records `herd.py status` and classifies only unclassified panes; a raw herdr launch is a red flag;
        # the receipt answers a version-2 checklist by launch id, and one `herd.py wait` covers every worker.
        skill = ' '.join((SKILL / 'SKILL.md').read_text().split())
        for needle in ('scripts/herd.py status [extra-root …]', 'Classify only its **unclassified** panes',
                       '`herd.py adopt <pane> --role <role>`', 'raw `herdr agent start`'):
            self.assertIn(needle, skill)
        self.assertNotIn('herd-snapshot.sh [extra-root', skill)
        relay = ' '.join((SKILL / 'references/relay.md').read_text().split())
        for needle in ('"workers": [{"launch_id": "<checklist launch id>"', '"lost": [{"launch_id"',
                       '"unclassified": [{"pane_id"', 'matched by `launch_id`', '`"version": 2`',
                       'herd.py wait --marker relay-<relay-id>-w<k> --fired-dir <dir>/fired',
                       'flagged `looks_like_worker`',
                       'A worker with nothing to wait on (no dispatch yet, or its latest dispatch already reported) '
                       'gets a `reason` in the receipt, not a marker'):
            self.assertIn(needle, relay)

    def test_herd_py_documents_every_command_it_registers(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('herd', SCRIPTS / 'herd.py')
        herd = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(herd)
        self.assertEqual(herd.COMMANDS, ('launch', 'dispatch', 'status', 'wait', 'adopt', 'close'))
        for name in herd.COMMANDS:
            self.assertTrue((SCRIPTS / ('herd_%s.py' % name)).is_file(), name)
            self.assertRegex(herd.__doc__, r'\n  %s ' % name)

    def test_prose_rules_from_the_2026_10_26_review_stay_named(self):
        # These three rules have no script behind them. Dropping the phrase drops the rule.
        text = ' '.join((SKILL / 'SKILL.md').read_text().split())
        time_rule = text.index('read from `date -u` or the event\'s own record')
        self.assertIn('never estimated', text[time_rule:time_rule + 160])
        self.assertIn('absolute or `~/`', text)
        self.assertIn('every recorded check can fail', text.lower())

    def test_no_pgrep_check_of_the_successors_waiters(self):
        # A fired waiter is legitimately dead: the compare PASS, not pgrep, proves coverage.
        for name in ('SKILL.md', 'references/relay.md'):
            self.assertNotIn('pgrep -f relay-', (SKILL / name).read_text(), name)


if __name__ == '__main__':
    unittest.main()
