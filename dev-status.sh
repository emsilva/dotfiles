#!/usr/bin/env bash

# Development Status Checker
# Quick way to see current development state after power outage/session restart

set -e

echo "🔍 DOTFILES DEVELOPMENT STATUS CHECK"
echo "======================================="

echo -e "\n📊 TEST STATUS:"
total_tests=$(make test 2>&1 | grep -E "^(ok|not ok)" | wc -l)
passing_tests=$(make test 2>&1 | grep -E "^ok" | wc -l)
failing_tests=$(make test 2>&1 | grep -E "^not ok" | wc -l)

echo "  Total Tests: $total_tests"
echo "  Passing: $passing_tests"
echo "  Failing: $failing_tests"
echo "  Pass Rate: $(( passing_tests * 100 / total_tests ))%"

echo -e "\n❌ CURRENT FAILURES:"
make test 2>&1 | grep -E "^not ok" | head -10

echo -e "\n🎯 HIGH PRIORITY TODOS (from CLAUDE.md):"
echo "  1. Fix dotfiles-status command hanging issue"
echo "  2. Fix test setup CD failures in install.bats"
echo "  3. Complete error handling for permission denied"

echo -e "\n🔧 QUICK TEST COMMANDS:"
echo "  # Test specific failure:"
echo "  bats test/dotfiles_management.bats -f \"dotfiles-status detects missing symlinks\""
echo ""
echo "  # Test infrastructure fix:"
echo "  bats test/install.bats -f \"create_symlinks function creates proper symlinks\""
echo ""
echo "  # Check if progress made:"
echo "  make test 2>&1 | grep -E \"^not ok\" | wc -l"

echo -e "\n📝 LAST COMMIT:"
git log --oneline -1

echo -e "\n📋 RECOVERY STRATEGY:"
echo "  1. Work through HIGH priority todos in CLAUDE.md"
echo "  2. Fix one test at a time with targeted bats commands"
echo "  3. Commit progress frequently with descriptive messages"
echo "  4. Update CLAUDE.md development state section when major progress made"

echo -e "\n✅ RECENT ACHIEVEMENTS:"
echo "  - Fixed dotfiles-remove functionality (1+ tests)"
echo "  - Enhanced dotfiles-status path detection"
echo "  - Added comprehensive testing documentation"
echo "  - Improved from ~79% to ~84% test pass rate"

echo -e "\n🎯 TARGET: 107/107 tests passing (100%) for full TDD compliance"