#!/bin/bash

# This script runs inside the container to validate the installation
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_pass() { echo -e "${GREEN}✅ PASS:${NC} $1"; }
print_fail() { echo -e "${RED}❌ FAIL:${NC} $1"; }
print_info() { echo -e "${YELLOW}ℹ️  INFO:${NC} $1"; }

FAILED_TESTS=0

# Test function
test_condition() {
    local description="$1"
    local condition="$2"
    
    if eval "$condition"; then
        print_pass "$description"
        return 0
    else
        print_fail "$description"
        ((FAILED_TESTS++))
        return 1
    fi
}

print_info "Starting post-installation validation..."

# Test 1: Check symlinks exist and point to correct locations
print_info "Testing symlinks..."
test_condition "vimrc symlink exists" "[ -L ~/.vimrc ]"
test_condition "zshrc symlink exists" "[ -L ~/.zshrc ]"
test_condition "gitconfig symlink exists" "[ -L ~/.gitconfig ]"
test_condition "gitconfig-work symlink exists" "[ -L ~/.gitconfig-work ]"
test_condition "p10k config symlink exists" "[ -L ~/.p10k.zsh ]"

# Test 2: Check symlinks point to dotfiles directory
test_condition "vimrc points to dotfiles" "readlink ~/.vimrc | grep -q 'dotfiles/.vimrc'"
test_condition "zshrc points to dotfiles" "readlink ~/.zshrc | grep -q 'dotfiles/.zshrc'"

# Test 3: Check git configuration substitution
print_info "Testing git configuration..."
test_condition "Personal email substituted in gitconfig" "grep -q 'test.personal@example.com' ~/.gitconfig"
test_condition "Work email substituted in gitconfig-work" "grep -q 'test.work@example.com' ~/.gitconfig-work"
test_condition "Git user name is set" "grep -q 'Mannu Silva' ~/.gitconfig"

# Test 4: Check directories were created
print_info "Testing directory creation..."
test_condition "org directory created" "[ -d ~/org ]"
test_condition "code/work directory created" "[ -d ~/code/work ]"

# Test 5: Check config directories
print_info "Testing config directories..."
test_condition ".config directory exists" "[ -d ~/.config ]"
test_condition ".local/share directory exists" "[ -d ~/.local/share ]"

# Test 6: Check shell environment
print_info "Testing shell environment..."
if [ "$OSTYPE" = "darwin21" ]; then
    # macOS simulation tests
    test_condition "Detected macOS environment" "[ '$OSTYPE' = 'darwin21' ]"
    test_condition "Mock brew command available" "command -v brew > /dev/null"
    test_condition "Mock defaults command available" "command -v defaults > /dev/null"
else
    # Ubuntu tests
    test_condition "Detected Linux environment" "echo '$OSTYPE' | grep -q 'linux'"
    test_condition "apt command available" "command -v apt > /dev/null"
fi

# Test 7: Check file contents
print_info "Testing file contents..."
test_condition "vimrc has content" "[ -s ~/.vimrc ]"
test_condition "zshrc has content" "[ -s ~/.zshrc ]"
test_condition "gitconfig has content" "[ -s ~/.gitconfig ]"

# Test 8: Check for oh-my-zsh installation attempt
print_info "Testing oh-my-zsh..."
if [ -d ~/.oh-my-zsh ]; then
    print_pass "oh-my-zsh directory exists"
else
    print_info "oh-my-zsh not installed (expected in container environment)"
fi

# Test 9: Environment variables
print_info "Testing environment variables..."
test_condition "GIT_EMAIL_PERSONAL is set" "[ -n '$GIT_EMAIL_PERSONAL' ]"
test_condition "GIT_EMAIL_WORK is set" "[ -n '$GIT_EMAIL_WORK' ]"

# Test 10: Basic command functionality
print_info "Testing basic commands..."
test_condition "git command works" "git --version > /dev/null"
test_condition "vim command works" "vim --version > /dev/null"

# Summary
print_info "Validation Summary"
TOTAL_TESTS=20  # Approximate count of tests above
PASSED_TESTS=$((TOTAL_TESTS - FAILED_TESTS))

if [ $FAILED_TESTS -eq 0 ]; then
    print_pass "All validation tests passed! ($PASSED_TESTS/$TOTAL_TESTS)"
    exit 0
else
    print_fail "$FAILED_TESTS out of $TOTAL_TESTS validation tests failed"
    exit 1
fi