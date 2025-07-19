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

@test "detect_os function works" {
    # Source the install script to access functions
    source install.sh
    
    # Test macOS detection
    export OSTYPE="darwin20"
    run detect_os
    [ "$status" -eq 0 ]
    [ "$output" = "macos" ]
    
    # Test Ubuntu detection (mock apt command)
    export OSTYPE="linux-gnu"
    export BASH_ENV="$TEST_TEMP_DIR/stub_apt.sh"
    echo 'command() { [ "$2" = "apt" ] && return 0 || return 1; }' > "$BASH_ENV"
    run detect_os
    [ "$status" -eq 0 ]
    [ "$output" = "ubuntu" ]
}

@test "create_symlinks function creates proper symlinks" {
    # Override HOME before sourcing
    export HOME="$TEST_HOME"
    source install.sh
    
    # Create some test dotfiles
    mkdir -p dotfiles
    echo "test content" > dotfiles/.testfile
    mkdir -p dotfiles/.config
    echo "config content" > dotfiles/.config/testconfig
    
    # Run the function
    run create_symlinks
    [ "$status" -eq 0 ]
    
    # Check that symlinks were created
    [ -L "$TEST_HOME/.testfile" ]
    [ -L "$TEST_HOME/.config" ]
    
    # Check that symlinks point to correct files
    [ "$(readlink "$TEST_HOME/.testfile")" = "$TEST_TEMP_DIR/dotfiles/.testfile" ]
    [ "$(readlink "$TEST_HOME/.config")" = "$TEST_TEMP_DIR/dotfiles/.config" ]
}

@test "setup_git_config substitutes environment variables" {
    # Override HOME before sourcing
    export HOME="$TEST_HOME"
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
    run setup_git_config
    [ "$status" -eq 0 ]
    
    # Check that environment variables were substituted
    grep "personal@test.com" "$TEST_HOME/.gitconfig"
    grep "work@test.com" "$TEST_HOME/.gitconfig-work"
}

@test "create_folders creates required directories" {
    # Override HOME before sourcing
    export HOME="$TEST_HOME"
    source install.sh
    
    run create_folders
    [ "$status" -eq 0 ]
    
    # Check that directories were created
    [ -d "$TEST_HOME/org" ]
    [ -d "$TEST_HOME/code/work" ]
}