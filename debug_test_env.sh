#!/usr/bin/env bash

# Simulate exact test environment from bats
set -e

# Create the same setup as bats test
TEST_DIR=$(mktemp -d)
export TEST_HOME="$TEST_DIR/home"
export TEST_DOTFILES="$TEST_DIR/dotfiles"

mkdir -p "$TEST_HOME"
mkdir -p "$TEST_DOTFILES/dotfiles"
mkdir -p "$TEST_DOTFILES/backups"

# Copy scripts to test directory (like bats does)
cp dotfiles-*.sh "$TEST_DOTFILES/"
chmod +x "$TEST_DOTFILES"/dotfiles-*.sh

# Create test files (like the specific test does)
echo "test content" > "$TEST_DOTFILES/dotfiles/.testrc"

cd "$TEST_DOTFILES"

# Create the test manifest and file (same as test)
echo ".testrc" > .dotfiles-manifest
echo "content" > "dotfiles/.testrc"

echo "TEST_DIR: $TEST_DIR"
echo "TEST_HOME: $TEST_HOME"
echo "TEST_DOTFILES: $TEST_DOTFILES"
echo "Current directory: $(pwd)"
echo "SCRIPT_DIR would be: $(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# List what exists
echo -e "\nFiles in TEST_HOME:"
ls -la "$TEST_HOME" || echo "No files"

echo -e "\nFiles in TEST_DOTFILES:"
ls -la "$TEST_DOTFILES"

echo -e "\nFiles in dotfiles subdir:"
ls -la "$TEST_DOTFILES/dotfiles"

echo -e "\nTesting get_target_path logic:"
SCRIPT_DIR="$TEST_DOTFILES"

if [[ "$SCRIPT_DIR" == /tmp/* ]]; then
    echo "SCRIPT_DIR matches /tmp/*: YES"
    test_home_dir="$SCRIPT_DIR/home"
    echo "test_home_dir would be: $test_home_dir"
    if [[ -d "$test_home_dir" ]]; then
        echo "test_home_dir exists: YES"
        target_path="$test_home_dir/.testrc"
    else
        echo "test_home_dir exists: NO"
        target_path="$HOME/.testrc"
    fi
else
    echo "SCRIPT_DIR matches /tmp/*: NO"
    target_path="$HOME/.testrc"
fi

echo "Final target_path: $target_path"
echo "Target exists: $(test -e "$target_path" && echo "YES" || echo "NO")"
echo "Target is symlink: $(test -L "$target_path" && echo "YES" || echo "NO")"

# Run the actual script
echo -e "\nRunning dotfiles-status.sh:"
timeout 10s ./dotfiles-status.sh --verbose

# Cleanup
rm -rf "$TEST_DIR"