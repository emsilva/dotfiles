#!/usr/bin/env bash

# Debug script to test check_symlink_status function
set -e

# Extract functions from dotfiles-status.sh
get_target_path() {
    local rel_path="$1"
    local default_path="$HOME/$rel_path"
    
    # If symlink already exists, use its location
    if [[ -L "$default_path" ]]; then
        echo "$default_path"
        return
    fi
    
    # Check if we're in a test environment (script dir under /tmp)
    if [[ "$SCRIPT_DIR" == /tmp/* ]]; then
        # Look for a "home" directory in the parent directory
        local test_home_dir="$(dirname "$SCRIPT_DIR")/home"
        if [[ -d "$test_home_dir" ]]; then
            echo "$test_home_dir/$rel_path"
            return
        fi
    fi
    
    # Default to HOME-based path
    echo "$default_path"
}

check_symlink_status() {
    local rel_path="$1"
    local target_path
    target_path=$(get_target_path "$rel_path")
    local dotfiles_path="$SCRIPT_DIR/dotfiles/$rel_path"
    
    # Check if dotfile exists
    if [[ ! -e "$dotfiles_path" ]]; then
        echo "DOTFILE_MISSING"
        return
    fi
    
    # Check target path
    if [[ ! -e "$target_path" ]]; then
        echo "MISSING"
    elif [[ ! -L "$target_path" ]]; then
        echo "NOT_SYMLINK"
    else
        local link_target
        link_target=$(readlink "$target_path")
        if [[ "$link_target" == "$dotfiles_path" ]]; then
            echo "OK"
        else
            echo "WRONG_TARGET"
        fi
    fi
}

# Test data setup like in the test
TEST_DIR=$(mktemp -d)
TEST_HOME="$TEST_DIR/home"
TEST_DOTFILES="$TEST_DIR/dotfiles"

mkdir -p "$TEST_HOME"
mkdir -p "$TEST_DOTFILES/dotfiles"

# Create test files
echo ".testrc" > "$TEST_DOTFILES/.dotfiles-manifest"
echo "content" > "$TEST_DOTFILES/dotfiles/.testrc"

cd "$TEST_DOTFILES"

# Override SCRIPT_DIR to point to test directory
SCRIPT_DIR="$TEST_DOTFILES"

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "Testing get_target_path:"
target_path=$(get_target_path ".testrc")
echo "Target path: $target_path"

echo "Testing check_symlink_status:"
status=$(check_symlink_status ".testrc")
echo "Status: $status"

# Check if files exist
echo "Dotfile exists: $(test -e "$SCRIPT_DIR/dotfiles/.testrc" && echo "YES" || echo "NO")"
echo "Target exists: $(test -e "$target_path" && echo "YES" || echo "NO")"

# Cleanup
rm -rf "$TEST_DIR"