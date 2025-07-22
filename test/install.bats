#!/usr/bin/env bats

setup() {
    # Create a temporary directory for this test
    export TEST_TEMP_DIR="$BATS_TEST_TMPDIR/dotfiles_test"
    mkdir -p "$TEST_TEMP_DIR"
    
    # Create a mock home directory
    export TEST_HOME="$TEST_TEMP_DIR/home"
    mkdir -p "$TEST_HOME"
    
    # Copy our dotfiles to test directory
    cp -r "$BATS_TEST_DIRNAME/../dotfiles" "$TEST_TEMP_DIR/"
    cp "$BATS_TEST_DIRNAME/../install.sh" "$TEST_TEMP_DIR/"
    cp -r "$BATS_TEST_DIRNAME/../scripts" "$TEST_TEMP_DIR/"
    
    # Create stub environment
    export BASH_ENV="$TEST_TEMP_DIR/stub_env.sh"
    cat <<EOS > "$BASH_ENV"
# Mock commands to avoid actual system changes
brew() { echo "brew \$@" >> "$TEST_TEMP_DIR/brew.log"; return 0; }
apt() { echo "apt \$@" >> "$TEST_TEMP_DIR/apt.log"; return 0; }
sudo() { 
    shift; # Remove 'sudo' from arguments
    echo "sudo \$@" >> "$TEST_TEMP_DIR/sudo.log"
    # Execute the command without sudo for testing
    "\$@"
}
curl() { echo "curl \$@" >> "$TEST_TEMP_DIR/curl.log"; return 0; }
git() { echo "git \$@" >> "$TEST_TEMP_DIR/git.log"; return 0; }
chsh() { echo "chsh \$@" >> "$TEST_TEMP_DIR/chsh.log"; return 0; }
systemctl() { echo "systemctl \$@" >> "$TEST_TEMP_DIR/systemctl.log"; return 0; }
defaults() { echo "defaults \$@" >> "$TEST_TEMP_DIR/defaults.log"; return 0; }
gem() { echo "gem \$@" >> "$TEST_TEMP_DIR/gem.log"; return 0; }
dpkg() { echo "dpkg \$@" >> "$TEST_TEMP_DIR/dpkg.log"; return 1; } # Simulate package not installed
command() {
    if [ "\$1" = "-v" ] && [ "\$2" = "brew" ]; then
        return 1  # Simulate brew not found initially
    elif [ "\$1" = "-v" ] && [ "\$2" = "code" ]; then
        return 1  # Simulate code not found initially
    else
        echo "command \$@" >> "$TEST_TEMP_DIR/command.log"
        return 0
    fi
}
# Override HOME for testing
HOME="$TEST_HOME"
EOS
    
    # Make install script use our test directory
    cd "$TEST_TEMP_DIR"
}

teardown() {
    # Clean up test directory
    rm -rf "$TEST_TEMP_DIR"
}

@test "install.sh exists and is executable" {
    [ -f install.sh ]
    [ -x install.sh ]
}

@test "detect_os function detects macOS" {
    source install.sh
    export OSTYPE="darwin20"
    run detect_os
    [ "$status" -eq 0 ]
    [ "$output" = "macos" ]
}

@test "detect_os function detects Ubuntu" {
    source install.sh
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
        source install.sh
        
        # Create some test dotfiles
        mkdir -p dotfiles
        echo "test content" > dotfiles/.testfile
        mkdir -p dotfiles/.config
        echo "config content" > dotfiles/.config/testconfig
        
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
        source install.sh
        
        # Create test dotfiles directory
        mkdir -p dotfiles
        echo "test content" > dotfiles/.testfile
        
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
        source install.sh
        
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
        source install.sh
        
        create_folders
    )
    
    # Check that directories were created
    [ -d "$TEST_HOME/org" ]
    [ -d "$TEST_HOME/code/work" ]
}

@test "install.sh has confirmation functionality" {
    grep -q "confirm_action()" install.sh
    grep -q "show_installation_preview()" install.sh
    grep -q "skip_confirmation" install.sh
}

@test "install.sh supports bypass flags" {
    grep -q "\-y.*skip.confirmation" install.sh
    grep -q "\-\-yes.*skip.confirmation" install.sh
    grep -q "\-\-skip.confirmation" install.sh
}

@test "install.sh has help functionality" {
    grep -q "\-h.*help" install.sh
    grep -q "Usage:" install.sh
}