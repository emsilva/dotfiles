import re
import unittest

from handoff_fixtures import SCRIPTS, SOURCE

SKILL = SOURCE / 'private_dot_claude/skills/session-handoff'


class HandoffDocsTests(unittest.TestCase):
    def test_every_script_the_docs_name_exists(self):
        text = ''.join((SKILL / name).read_text() for name in ('SKILL.md', 'references/relay.md', 'references/feedback.md'))
        named = set(re.findall(r'scripts/([\w.-]+\.(?:py|sh))', text))
        self.assertTrue(named >= {'bg-tasks.py', 'memory-check.py', 'relay-check.py', 'relay-launch.sh',
                                  'relay-close.sh'}, named)
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
        for needle in ('`relay-check.py checklist --note PATH [--extra-root DIR ...] [--transcript PATH ...]`',
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
        spec = ' '.join((SOURCE / 'docs/superpowers/specs/2026-10-12-session-relay-design.md').read_text().split())
        self.assertIn("descends from the receipt's `successor.pid`", spec)
        self.assertNotIn('pgrep -f', spec)

    def test_no_pgrep_check_of_the_successors_waiters(self):
        # A fired waiter is legitimately dead: the compare PASS, not pgrep, proves coverage.
        for name in ('SKILL.md', 'references/relay.md'):
            self.assertNotIn('pgrep -f relay-', (SKILL / name).read_text(), name)


if __name__ == '__main__':
    unittest.main()
