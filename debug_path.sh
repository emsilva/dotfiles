#!/usr/bin/env bash

# Debug get_target_path function specifically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

get_target_path() {
    local rel_path="$1"
    local default_path="$HOME/$rel_path"
    
    echo "DEBUG get_target_path: rel_path=$rel_path" >&2
    echo "DEBUG get_target_path: SCRIPT_DIR=$SCRIPT_DIR" >&2
    echo "DEBUG get_target_path: default_path=$default_path" >&2
    
    # If symlink already exists, use its location
    if [[ -L "$default_path" ]]; then
        echo "DEBUG: symlink exists at default path" >&2
        echo "$default_path"
        return
    fi
    
    # Check if we're in a test environment (script dir under /tmp)
    echo "DEBUG: checking if SCRIPT_DIR starts with /tmp" >&2
    if [[ "$SCRIPT_DIR" == /tmp/* ]]; then
        echo "DEBUG: SCRIPT_DIR matches /tmp/*" >&2
        # Look for a "home" directory in the parent directory
        local test_home_dir="$(dirname "$SCRIPT_DIR")/home"
        echo "DEBUG: test_home_dir=$test_home_dir" >&2
        if [[ -d "$test_home_dir" ]]; then
            echo "DEBUG: test_home_dir exists" >&2
            echo "$test_home_dir/$rel_path"
            return
        else
            echo "DEBUG: test_home_dir does not exist" >&2
        fi
    else 
        echo "DEBUG: SCRIPT_DIR does not match /tmp/*" >&2
    fi
    
    # Default to HOME-based path
    echo "DEBUG: returning default path" >&2
    echo "$default_path"
}

# Test in temp directory like bats
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"
mkdir -p home

# Override SCRIPT_DIR
SCRIPT_DIR="$TEST_DIR"

echo "Testing from: $TEST_DIR"
target_path=$(get_target_path ".testrc")
echo "Result: $target_path"

# Clean up
rm -rf "$TEST_DIR"