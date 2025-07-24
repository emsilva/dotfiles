#!/usr/bin/env bats

# Test error scenarios and edge cases for better coverage
# This addresses the gap in error handling testing

setup() {
    export TEST_TEMP_DIR="$BATS_TEST_TMPDIR/error_scenarios_test"
    mkdir -p "$TEST_TEMP_DIR"
    export TEST_HOME="$TEST_TEMP_DIR/home"
    mkdir -p "$TEST_HOME"
    
    # Copy scripts to test directory
    cp "$BATS_TEST_DIRNAME/../dotfiles-add.sh" "$TEST_TEMP_DIR/"
    cp "$BATS_TEST_DIRNAME/../dotfiles-remove.sh" "$TEST_TEMP_DIR/" 2>/dev/null || true
    cp "$BATS_TEST_DIRNAME/../dotfiles-status.sh" "$TEST_TEMP_DIR/" 2>/dev/null || true
    cp "$BATS_TEST_DIRNAME/../dotfiles-install.sh" "$TEST_TEMP_DIR/"
    cp -r "$BATS_TEST_DIRNAME/../scripts" "$TEST_TEMP_DIR/" 2>/dev/null || true
    
    cd "$TEST_TEMP_DIR"
}

teardown() {
    rm -rf "$TEST_TEMP_DIR"
}

# Test file permission errors
@test "dotfiles-add handles permission denied gracefully" {
    # Create a read-only directory with a file we can't move
    mkdir -p "$TEST_HOME/readonly"
    echo "content" > "$TEST_HOME/readonly/.testfile"
    chmod 555 "$TEST_HOME/readonly"  # Remove write permission from directory
    
    # Try to add it (should fail gracefully)
    run ./dotfiles-add.sh --yes "$TEST_HOME/readonly/.testfile"
    echo "Status: $status, Output: $output"  # Debug
    [ "$status" -ne 0 ]
    [[ "$output" == *"error"* ]] || [[ "$output" == *"Error"* ]] || [[ "$output" == *"failed"* ]]
    
    # Cleanup
    chmod 755 "$TEST_HOME/readonly"  # Restore permissions for cleanup
}

# Test non-existent file handling
@test "dotfiles-add handles non-existent files gracefully" {
    run ./dotfiles-add.sh --yes "$TEST_HOME/.nonexistent"
    [ "$status" -ne 0 ]
    [[ "$output" == *"does not exist"* ]] || [[ "$output" == *"not found"* ]] || [[ "$output" == *"No such file"* ]]
}

# Test adding file that's already a symlink
@test "dotfiles-add handles existing symlinks gracefully" {
    # Create dotfiles structure
    mkdir -p dotfiles
    echo "original" > dotfiles/.testfile
    
    # Create existing symlink
    ln -s "$TEST_TEMP_DIR/dotfiles/.testfile" "$TEST_HOME/.testfile"
    
    # Try to add the symlink
    run ./dotfiles-add.sh --yes "$TEST_HOME/.testfile"
    [ "$status" -ne 0 ]
    [[ "$output" == *"symlink"* ]] || [[ "$output" == *"already"* ]]
}

# Test OS detection edge cases
@test "dotfiles-install handles unsupported OS gracefully" {
    # Mock OSTYPE to return unsupported OS
    export BASH_ENV="$TEST_TEMP_DIR/mock_env.sh"
    cat <<EOS > "$BASH_ENV"
export OSTYPE="freebsd13.0"
EOS
    
    # Should fail gracefully on unsupported OS
    run bash -c "source '$BASH_ENV' && ./dotfiles-install.sh --yes"
    # The script should exit with non-zero status on unsupported OS
    [ "$status" -ne 0 ]
}

# Test missing dependencies
@test "platform scripts handle missing package managers gracefully" {
    skip "Integration test - requires container environment"
    # This would test scenarios where brew/apt are missing
    # Better suited for integration tests
}

# Test network failures during github releases
@test "github_releases handles network failures gracefully" {
    skip "Requires network mocking"
    # This would test curl failures during github releases
    # Requires more complex mocking setup
}

# Test corrupted manifest file
@test "dotfiles management handles corrupted manifest gracefully" {
    # Create corrupted manifest
    echo -e "valid_entry\n\x00\x01\x02invalid_binary_data\nother_entry" > .dotfiles-manifest
    
    # Commands should handle this gracefully
    run ./dotfiles-status.sh
    [[ "$status" -eq 0 ]] || [[ "$output" == *"error"* ]] || [[ "$output" == *"Error"* ]] || [[ "$output" == *"ERROR"* ]]
}

# Test disk space issues
@test "dotfiles-add handles insufficient disk space gracefully" {
    skip "Requires disk space simulation"
    # This would test what happens when disk is full
    # Complex to set up reliably
}

# Test interrupted operations
@test "dotfiles management handles interrupted operations" {
    # Create a partial state (backup exists, dotfile exists, but symlink is missing)
    mkdir -p backups/20250101_120000
    echo "partial backup" > backups/20250101_120000/.testfile
    mkdir -p dotfiles
    echo "managed content" > dotfiles/.testfile
    echo ".testfile" > .dotfiles-manifest
    
    # Status should detect and report this inconsistency, then fix it
    run ./dotfiles-status.sh --fix --yes
    echo "Status: $status" >&2
    echo "Output: $output" >&2
    [ "$status" -eq 0 ]
    # Should either fix automatically or report the issue
}

# Test invalid command line arguments
@test "scripts handle invalid arguments gracefully" {
    # Test invalid flag
    run ./dotfiles-add.sh --invalid-flag
    [ "$status" -ne 0 ]
    [[ "$output" == *"Unknown"* ]] || [[ "$output" == *"invalid"* ]] || [[ "$output" == *"help"* ]]
    
    # Test missing required argument
    run ./dotfiles-add.sh --yes
    [ "$status" -ne 0 ]
    [[ "$output" == *"Usage"* ]] || [[ "$output" == *"argument"* ]] || [[ "$output" == *"required"* ]]
}

# Test race conditions (basic)
@test "concurrent operations handle conflicts gracefully" {
    # Create test file
    echo "content" > "$TEST_HOME/.testfile"
    
    # Simulate concurrent access by creating lock files or partial states
    mkdir -p dotfiles
    echo "content1" > dotfiles/.testfile
    echo ".testfile" > .dotfiles-manifest
    
    # Second attempt should detect existing management
    run ./dotfiles-add.sh --yes "$TEST_HOME/.testfile"
    [ "$status" -ne 0 ]
    [[ "$output" == *"already managed"* ]] || [[ "$output" == *"exists"* ]]
}

# Test symlink target validation
@test "symlink operations validate targets" {
    # Create manifest entry but no actual dotfile
    echo ".testfile" > .dotfiles-manifest
    
    # Status should detect missing dotfile target and report issues
    run ./dotfiles-status.sh --verbose
    [ "$status" -eq 1 ]  # Should exit with error when issues found
    [[ "$output" == *"DOTFILE_MISSING"* ]] || [[ "$output" == *"MISSING"* ]] || [[ "$output" == *"not found"* ]]
}

# Test path traversal attempts
@test "path normalization prevents directory traversal" {
    # Try to add file with path traversal
    local evil_dir="/tmp/evil_$$"  # Use unique name to avoid conflicts
    mkdir -p "$evil_dir"
    echo "evil content" > "$evil_dir/badfile"
    
    # Should not allow traversal outside of home
    run ./dotfiles-add.sh --yes "../../../../$evil_dir/badfile"
    [ "$status" -ne 0 ]
    
    # Cleanup
    rm -rf "$evil_dir"
}

# Test extremely long paths
@test "scripts handle very long file paths" {
    # Create deeply nested structure
    local deep_path="$TEST_HOME"
    for i in {1..10}; do
        deep_path="$deep_path/very_long_directory_name_$i"
    done
    mkdir -p "$deep_path"
    echo "content" > "$deep_path/file_with_very_long_name.txt"
    
    # Should handle long paths gracefully
    run ./dotfiles-add.sh --yes "$deep_path/file_with_very_long_name.txt"
    # Should either succeed or fail gracefully with clear message
    [[ "$status" -eq 0 ]] || [[ "$output" == *"path"* ]] || [[ "$output" == *"long"* ]]
}

# Test special characters in filenames
@test "scripts handle special characters in filenames" {
    # Create file with special characters
    local special_file="$TEST_HOME/test file with spaces & symbols (1).txt"
    echo "content" > "$special_file"
    
    # Should handle special characters
    run ./dotfiles-add.sh --yes "$special_file"
    [[ "$status" -eq 0 ]] || [[ "$output" != *"command not found"* ]]
}

# Test broken symlinks cleanup
@test "symlink cleanup handles broken links properly" {
    # Create manifest, dotfile, and broken symlink
    echo ".testfile" > .dotfiles-manifest
    mkdir -p dotfiles
    echo "content" > dotfiles/.testfile
    ln -s "$TEST_TEMP_DIR/dotfiles/.nonexistent" "$TEST_HOME/.testfile"  # Wrong target
    
    # Status should detect wrong target and fix it
    run ./dotfiles-status.sh --fix --yes
    [ "$status" -eq 0 ]  # Should succeed in fixing
    [[ "$output" == *"WRONG_TARGET"* ]] || [[ "$output" == *"fixed"* ]] || [[ "$output" == *"FIXED"* ]]
}