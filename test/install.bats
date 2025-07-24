#!/usr/bin/env bats

# No setup function - let tests create what they need

@test "dotfiles-install.sh exists and is executable" {
    [ -f dotfiles-install.sh ]
    [ -x dotfiles-install.sh ]
}

@test "detect_os function detects macOS" {
    source "${BATS_TEST_DIRNAME}/../dotfiles-install.sh"
    export OSTYPE="darwin20"
    run detect_os
    [ "$status" -eq 0 ]
    [ "$output" = "macos" ]
}

@test "detect_os function detects Ubuntu" {
    source "${BATS_TEST_DIRNAME}/../dotfiles-install.sh"
    export OSTYPE="linux-gnu"
    # Mock command function
    command() { 
        if [ "$1" = "-v" ] && [ "$2" = "apt" ]; then
            return 0
        fi
        builtin command "$@"
    }
    run detect_os
    [ "$status" -eq 0 ]
    [ "$output" = "ubuntu" ]
}

@test "create_symlinks function creates proper symlinks" {
    # Create test environment - use simple paths
    local TEST_TEMP_DIR="/tmp/bats_test_$(date +%s)_$$"
    local TEST_HOME="$TEST_TEMP_DIR/home"
    ( mkdir -p "$TEST_TEMP_DIR" && mkdir -p "$TEST_HOME" ) || true
    
    # Source the script with overridden HOME
    (
        export HOME="$TEST_HOME"
        cd "$TEST_TEMP_DIR"
        source "${BATS_TEST_DIRNAME}/../dotfiles-install.sh"
        
        # Create some test dotfiles in the expected location
        mkdir -p "${BATS_TEST_DIRNAME}/../dotfiles"
        echo "test content" > "${BATS_TEST_DIRNAME}/../dotfiles/.testfile"
        mkdir -p "${BATS_TEST_DIRNAME}/../dotfiles/.config"
        echo "config content" > "${BATS_TEST_DIRNAME}/../dotfiles/.config/testconfig"
        
        # Create manifest for managed files in test directory
        echo ".testfile" > .dotfiles-manifest
        echo ".config" >> .dotfiles-manifest
        
        # Also create manifest in the script directory (where create_symlinks expects it)
        echo ".testfile" > "${BATS_TEST_DIRNAME}/../.dotfiles-manifest"
        echo ".config" >> "${BATS_TEST_DIRNAME}/../.dotfiles-manifest"
        
        # Run the function in subshell to contain HOME override
        create_symlinks
        
        # Clean up the script directory files
        rm -f "${BATS_TEST_DIRNAME}/../.dotfiles-manifest"
        rm -f "${BATS_TEST_DIRNAME}/../dotfiles/.testfile"
        rm -rf "${BATS_TEST_DIRNAME}/../dotfiles/.config"
    )
    
    # Check that symlinks were created in test home (ignore mkdir failures)
    [ -L "$TEST_HOME/.testfile" ] || { echo "ERROR: .testfile symlink not created" >&2; ls -la "$TEST_HOME" >&2; exit 1; }
    [ -L "$TEST_HOME/.config" ] || { echo "ERROR: .config symlink not created" >&2; ls -la "$TEST_HOME" >&2; exit 1; }
    
    # Check that symlinks point to correct files (they point to main dotfiles dir now)
    [ "$(readlink "$TEST_HOME/.testfile")" = "${BATS_TEST_DIRNAME}/../dotfiles/.testfile" ]
    [ "$(readlink "$TEST_HOME/.config")" = "${BATS_TEST_DIRNAME}/../dotfiles/.config" ]
    
    # Cleanup
    rm -rf "$TEST_TEMP_DIR"
}

@test "create_symlinks function cleans up orphaned symlinks" {
    # Create test environment - use simple paths
    local TEST_TEMP_DIR="/tmp/bats_test_$(date +%s)_$$"
    local TEST_HOME="$TEST_TEMP_DIR/home"
    ( mkdir -p "$TEST_TEMP_DIR" && mkdir -p "$TEST_HOME" ) || true
    
    # Source the script with overridden HOME
    (
        export HOME="$TEST_HOME"
        cd "$TEST_TEMP_DIR"
        source "${BATS_TEST_DIRNAME}/../dotfiles-install.sh"
        
        # Create test dotfiles directory
        mkdir -p dotfiles
        echo "test content" > dotfiles/.testfile
        
        # Create manifest for the valid file
        echo ".testfile" > .dotfiles-manifest
        
        # Create an orphaned symlink that points to a non-existent file in dotfiles
        ln -s "$TEST_TEMP_DIR/dotfiles/.nonexistent" "$TEST_HOME/.orphaned"
        
        # Create a valid symlink to keep (not pointing to dotfiles)
        echo "external content" > "$TEST_TEMP_DIR/external"
        ln -s "$TEST_TEMP_DIR/external" "$TEST_HOME/.external"
        
        # Verify the orphaned symlink exists before cleanup
        [ -L "$TEST_HOME/.orphaned" ]
        [ -L "$TEST_HOME/.external" ]
        
        # Run the function which should clean up orphaned symlinks
        create_symlinks
    )
    
    # Check that orphaned symlink was removed
    [ ! -e "$TEST_HOME/.orphaned" ]
    
    # Check that external symlink (not pointing to dotfiles) was preserved
    [ -L "$TEST_HOME/.external" ]
    
    # Check that valid dotfiles symlink was created
    [ -L "$TEST_HOME/.testfile" ]
    
    # Cleanup
    rm -rf "$TEST_TEMP_DIR"
}

@test "setup_git_config substitutes environment variables" {
    # Run in subshell to contain HOME override
    (
        export HOME="$TEST_HOME"
        cd "$TEST_TEMP_DIR"
        source "${BATS_TEST_DIRNAME}/../dotfiles-install.sh"
        
        # Set environment variables
        export GIT_EMAIL_PERSONAL="personal@test.com"
        export GIT_EMAIL_WORK="work@test.com"
        
        # Create test git config files with environment variable syntax
        cat > "$TEST_HOME/.gitconfig" <<'EOF'
[user]
    name = Test User
    email = $GIT_EMAIL_PERSONAL
EOF
        
        cat > "$TEST_HOME/.gitconfig-work" <<'EOF'
[user]
    name = Test User
    email = $GIT_EMAIL_WORK
EOF
        
        # Run the function
        setup_git_config
    )
    
    # Check that environment variables were substituted
    grep "personal@test.com" "$TEST_HOME/.gitconfig"
    grep "work@test.com" "$TEST_HOME/.gitconfig-work"
}

@test "create_folders creates required directories" {
    # Run in subshell to contain HOME override
    (
        export HOME="$TEST_HOME"
        cd "$TEST_TEMP_DIR"
        source "${BATS_TEST_DIRNAME}/../dotfiles-install.sh"
        
        create_folders
    )
    
    # Check that directories were created
    [ -d "$TEST_HOME/org" ]
    [ -d "$TEST_HOME/code/work" ]
}

@test "dotfiles-install.sh has confirmation functionality" {
    grep -q "confirm_action()" dotfiles-install.sh
    grep -q "show_installation_preview()" dotfiles-install.sh
    grep -q "skip_confirmation" dotfiles-install.sh
}

@test "dotfiles-install.sh supports bypass flags" {
    grep -q "\-y.*skip.confirmation" dotfiles-install.sh
    grep -q "\-\-yes.*skip.confirmation" dotfiles-install.sh
    grep -q "\-\-skip.confirmation" dotfiles-install.sh
}

@test "dotfiles-install.sh has help functionality" {
    grep -q "\-h.*help" dotfiles-install.sh
    grep -q "Usage:" dotfiles-install.sh
}