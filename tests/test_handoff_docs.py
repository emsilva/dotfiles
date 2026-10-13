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
        # relay-launch needs a Bash timeout above its two 90 s start attempts.
        text = (SKILL / 'references/relay.md').read_text()
        for needle in ('fired/', 'relay-<relay-id>-w', '300000'):
            self.assertIn(needle, text)

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

    def test_no_pgrep_check_of_the_successors_waiters(self):
        # A fired waiter is legitimately dead: the compare PASS, not pgrep, proves coverage.
        for name in ('SKILL.md', 'references/relay.md'):
            self.assertNotIn('pgrep -f relay-', (SKILL / name).read_text(), name)


if __name__ == '__main__':
    unittest.main()
