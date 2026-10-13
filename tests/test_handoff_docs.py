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

    def test_no_pgrep_check_of_the_successors_waiters(self):
        # A fired waiter is legitimately dead: the compare PASS, not pgrep, proves coverage.
        for name in ('SKILL.md', 'references/relay.md'):
            self.assertNotIn('pgrep -f relay-', (SKILL / name).read_text(), name)


if __name__ == '__main__':
    unittest.main()
