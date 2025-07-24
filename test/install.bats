#!/usr/bin/env bats

setup() {
    # Create temporary directory for testing
    TEST_TEMP_DIR=$(mktemp -d)
    export TEST_TEMP_DIR
    export TEST_HOME="$TEST_TEMP_DIR/home"
    
    # Create the required directories and files
    mkdir -p "$TEST_HOME"
    cp "${BATS_TEST_DIRNAME}/../dotfiles-install.sh" "$TEST_TEMP_DIR/" 2>/dev/null || echo "Warning: Could not copy dotfiles-install.sh" >&2
}

teardown() {
    # Clean up test directory
    rm -rf "$TEST_TEMP_DIR"
}

@test "dotfiles-install.sh exists and is executable" {
    [ -f dotfiles-install.sh ]
    [ -x dotfiles-install.sh ]
}

@test "detect_os function detects macOS" {
    source dotfiles-install.sh
    export OSTYPE="darwin20"
    run detect_os
    [ "$status" -eq 0 ]
    [ "$output" = "macos" ]
}

@test "detect_os function detects Ubuntu" {
    source dotfiles-install.sh
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
    # Source the script with overridden HOME
    (
        export HOME="$TEST_HOME"
        cd "$TEST_TEMP_DIR"
        source dotfiles-install.sh
        
        # Create some test dotfiles
        mkdir -p dotfiles
        echo "test content" > dotfiles/.testfile
        mkdir -p dotfiles/.config
        echo "config content" > dotfiles/.config/testconfig
        
        # Create manifest for managed files
        echo ".testfile" > .dotfiles-manifest
        echo ".config" >> .dotfiles-manifest
        
        # Run the function in subshell to contain HOME override
        create_symlinks
    )
    
    # Check that symlinks were created in test home
    [ -L "$TEST_HOME/.testfile" ]
    [ -L "$TEST_HOME/.config" ]
    
    # Check that symlinks point to correct files
    [ "$(readlink "$TEST_HOME/.testfile")" = "$TEST_TEMP_DIR/dotfiles/.testfile" ]
    [ "$(readlink "$TEST_HOME/.config")" = "$TEST_TEMP_DIR/dotfiles/.config" ]
}

@test "create_symlinks function cleans up orphaned symlinks" {
    # Source the script with overridden HOME
    (
        export HOME="$TEST_HOME"
        cd "$TEST_TEMP_DIR"
        source dotfiles-install.sh
        
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
}

@test "setup_git_config substitutes environment variables" {
    # Run in subshell to contain HOME override
    (
        export HOME="$TEST_HOME"
        cd "$TEST_TEMP_DIR"
        source dotfiles-install.sh
        
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
        source dotfiles-install.sh
        
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