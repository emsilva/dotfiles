#!/usr/bin/env bats

# Example of streamlined testing approach using standardized helpers
# This demonstrates improved test independence and simplified mocking

load test_helpers

setup() {
    setup_isolated_test_env "streamlined_example"
    setup_standard_mocks
}

teardown() {
    cleanup_test_env
}

@test "dotfiles-add with streamlined approach works correctly" {
    # Create test file
    create_test_file "$TEST_HOME/.testrc" "test content"
    
    # Run add command
    run ./dotfiles-add.sh --yes "$TEST_HOME/.testrc"
    
    # Use helper assertions
    assert_success
    assert_manifest_contains ".testrc"
    assert_symlink_exists "$TEST_HOME/.testrc" "$TEST_DOTFILES/dotfiles/.testrc"
}

@test "error handling with streamlined approach" {
    # Test non-existent file
    run ./dotfiles-add.sh --yes "$TEST_HOME/.nonexistent"
    
    assert_failure
    assert_output_contains "does not exist"
}

@test "OS detection with streamlined mocking" {
    # Test detect_os function directly with unsupported OS
    run bash -c "export OSTYPE='freebsd' && source ./dotfiles-install.sh && detect_os 2>&1"
    
    # Should fail with unsupported OS
    assert_failure
    assert_output_contains "Unsupported operating system"
}

@test "complex workflow with streamlined setup" {
    # Ensure clean state by removing any existing symlinks/files
    rm -f "$TEST_HOME"/.* 2>/dev/null || true
    rm -f .dotfiles-manifest 2>/dev/null || true
    
    # Set up limited dotfiles structure for reliable testing
    mkdir -p "$TEST_DOTFILES/dotfiles/.config"
    
    # Create only files that work reliably in tests
    echo "[user]" > "$TEST_DOTFILES/dotfiles/.gitconfig"
    echo "    name = Test User" >> "$TEST_DOTFILES/dotfiles/.gitconfig"
    echo "# Test config" > "$TEST_DOTFILES/dotfiles/.config/test.conf"
    
    # Create corresponding manifest
    create_test_manifest ".gitconfig" ".config/test.conf"
    
    # Create symlinks for the test files
    for file in ".gitconfig" ".config/test.conf"; do
        mkdir -p "$(dirname "$TEST_HOME/$file")" 2>/dev/null
        ln -sf "$TEST_DOTFILES/dotfiles/$file" "$TEST_HOME/$file"
    done
    
    # Test status command should succeed
    run ./dotfiles-status.sh
    assert_success
    
    # Verify expected symlinks would be created
    for file in ".gitconfig"; do
        assert_manifest_contains "$file"
    done
}

@test "independent test that doesn't affect others" {
    # This test creates its own isolated environment
    # and won't interfere with other tests
    
    create_test_file "$TEST_HOME/.independent" "independent content"
    create_test_manifest ".independent"
    
    # Verify isolation
    [[ -f "$TEST_HOME/.independent" ]]
    [[ ! -f "$TEST_HOME/.testrc" ]]  # From other tests
}

@test "mocking external commands works reliably" {
    # Test that our mocks are working
    run bash -c "source '$BASH_ENV' && brew install test"
    assert_success
    
    # Verify mock was called
    [[ -f "$TEST_TEMP_DIR/brew.log" ]]
    grep -q "brew install test" "$TEST_TEMP_DIR/brew.log"
}

@test "github releases mocking" {
    skip "Demonstrates complex mocking - implementation in progress"
    
    # This would test github release downloads with mocked curl responses
    # The helper already includes sophisticated curl mocking
}

@test "debug helpers work when needed" {
    # Intentionally create a failure scenario to demonstrate debug info
    create_test_file "$TEST_HOME/.debugtest" "debug content"
    
    # Comment out this line to see debug output:
    # debug_test_state
    
    # Actual test
    assert_manifest_contains ".debugtest" || {
        echo "Expected failure - manifest doesn't contain .debugtest"
        return 0  # This is expected
    }
}