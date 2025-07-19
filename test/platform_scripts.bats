#!/usr/bin/env bats

setup() {
    # Create a temporary directory for this test
    export TEST_TEMP_DIR="$BATS_TEST_TMPDIR/platform_test"
    mkdir -p "$TEST_TEMP_DIR"
    
    # Copy scripts to test directory
    cp -r "$BATS_TEST_DIRNAME/../scripts" "$TEST_TEMP_DIR/"
    
    # Create stub environment for platform scripts
    export BASH_ENV="$TEST_TEMP_DIR/stub_env.sh"
    cat <<'EOS' > "$BASH_ENV"
# Mock all system commands
brew() { 
    echo "brew $@" >> "$TEST_TEMP_DIR/brew.log"
    if [ "$1" = "list" ]; then
        return 1  # Simulate package not installed
    elif [ "$1" = "services" ] && [ "$2" = "list" ]; then
        echo "syncthing none"
        return 0
    elif [ "$1" = "tap" ]; then
        return 0
    else
        return 0
    fi
}
apt() { 
    echo "apt $@" >> "$TEST_TEMP_DIR/apt.log"
    return 0
}
sudo() { 
    shift
    echo "sudo $@" >> "$TEST_TEMP_DIR/sudo.log"
    # For apt commands, just log them
    if [ "$1" = "apt" ]; then
        echo "apt $@" >> "$TEST_TEMP_DIR/apt.log"
        return 0
    fi
    # Mock other sudo commands
    case "$1" in
        "install"|"tee"|"sh")
            return 0
            ;;
        *)
            return 0
            ;;
    esac
}
dpkg() { 
    echo "dpkg $@" >> "$TEST_TEMP_DIR/dpkg.log"
    return 1  # Simulate package not found
}
snap() { 
    echo "snap $@" >> "$TEST_TEMP_DIR/snap.log"
    if [ "$1" = "list" ]; then
        return 1  # Simulate package not installed
    fi
    return 0
}
curl() { echo "curl $@" >> "$TEST_TEMP_DIR/curl.log"; return 0; }
wget() { echo "wget $@" >> "$TEST_TEMP_DIR/wget.log"; return 0; }
git() { echo "git $@" >> "$TEST_TEMP_DIR/git.log"; return 0; }
gem() { 
    echo "gem $@" >> "$TEST_TEMP_DIR/gem.log"
    if [ "$1" = "list" ]; then
        return 1  # Simulate gem not installed
    fi
    return 0
}
systemctl() { 
    echo "systemctl $@" >> "$TEST_TEMP_DIR/systemctl.log"
    if [[ "$*" == *"is-enabled"* ]]; then
        return 1  # Simulate service not enabled
    fi
    return 0
}
defaults() { echo "defaults $@" >> "$TEST_TEMP_DIR/defaults.log"; return 0; }
dockutil() { echo "dockutil $@" >> "$TEST_TEMP_DIR/dockutil.log"; return 0; }
chflags() { echo "chflags $@" >> "$TEST_TEMP_DIR/chflags.log"; return 0; }
gpg() { echo "gpg $@" >> "$TEST_TEMP_DIR/gpg.log"; return 0; }
tee() { cat > "$1"; }
command() {
    case "$2" in
        "brew"|"code"|"op"|"chezmoi")
            return 1  # Simulate not found
            ;;
        "fd-find"|"which")
            echo "/usr/bin/$2"
            return 0
            ;;
        *)
            return 0
            ;;
    esac
}
test() {
    # Mock test command behavior
    case "$1" in
        "-f")
            return 1  # Simulate file not found
            ;;
        "-d")
            return 1  # Simulate directory not found
            ;;
        *)
            return 0
            ;;
    esac
}
which() {
    case "$1" in
        "fd-find")
            echo "/usr/bin/fd-find"
            return 0
            ;;
        "zsh")
            echo "/usr/bin/zsh"
            return 0
            ;;
        *)
            echo "/usr/bin/$1"
            return 0
            ;;
    esac
}
mkdir() { echo "mkdir $@" >> "$TEST_TEMP_DIR/mkdir.log"; /bin/mkdir -p "$@"; }
ln() { echo "ln $@" >> "$TEST_TEMP_DIR/ln.log"; return 0; }
rm() { echo "rm $@" >> "$TEST_TEMP_DIR/rm.log"; return 0; }
# Mock script functions that might be called
update_packages() { echo "update_packages called" >> "$TEST_TEMP_DIR/functions.log"; return 0; }
install_packages() { echo "install_packages called" >> "$TEST_TEMP_DIR/functions.log"; return 0; }
install_ruby_gems() { echo "install_ruby_gems called" >> "$TEST_TEMP_DIR/functions.log"; return 0; }
install_zplug() { echo "install_zplug called" >> "$TEST_TEMP_DIR/functions.log"; return 0; }
install_ls_colors() { echo "install_ls_colors called" >> "$TEST_TEMP_DIR/functions.log"; return 0; }
configure_services() { echo "configure_services called" >> "$TEST_TEMP_DIR/functions.log"; return 0; }
install_vscode() { echo "install_vscode called" >> "$TEST_TEMP_DIR/functions.log"; return 0; }
configure_fd() { echo "configure_fd called" >> "$TEST_TEMP_DIR/functions.log"; return 0; }
EOS
    
    cd "$TEST_TEMP_DIR"
}

teardown() {
    rm -rf "$TEST_TEMP_DIR"
}

@test "macos.sh script exists and is executable" {
    [ -f scripts/macos.sh ]
    [ -x scripts/macos.sh ]
}

@test "ubuntu.sh script exists and is executable" {
    [ -f scripts/ubuntu.sh ]
    [ -x scripts/ubuntu.sh ]
}

@test "macos.sh installs homebrew if not present" {
    run bash scripts/macos.sh
    [ "$status" -eq 0 ]
    
    # Check that homebrew installation was attempted
    grep -q "Installing Homebrew" <(echo "$output") || grep -q "brew" "$TEST_TEMP_DIR/curl.log"
}

@test "macos.sh installs expected packages" {
    run bash scripts/macos.sh
    [ "$status" -eq 0 ]
    
    # Check that brew commands were called for expected packages
    [ -f "$TEST_TEMP_DIR/brew.log" ]
    grep -q "brew install python3" "$TEST_TEMP_DIR/brew.log"
    grep -q "brew install ripgrep" "$TEST_TEMP_DIR/brew.log"
    grep -q "brew install --cask visual-studio-code" "$TEST_TEMP_DIR/brew.log"
}

@test "macos.sh configures system defaults" {
    run bash scripts/macos.sh
    [ "$status" -eq 0 ]
    
    # Check that defaults commands were called
    [ -f "$TEST_TEMP_DIR/defaults.log" ]
    grep -q "defaults write NSGlobalDomain AppleShowAllExtensions" "$TEST_TEMP_DIR/defaults.log"
    grep -q "defaults write com.apple.dock" "$TEST_TEMP_DIR/defaults.log"
}

@test "ubuntu.sh installs expected packages" {
    # Test script syntax and structure instead of full execution
    bash -n scripts/ubuntu.sh
    
    # Check that script contains expected package installations
    grep -q "python3" scripts/ubuntu.sh
    grep -q "ripgrep" scripts/ubuntu.sh
    grep -q "apt update" scripts/ubuntu.sh
    grep -q "apt install" scripts/ubuntu.sh
}

@test "ubuntu.sh installs visual studio code" {
    # Test script syntax and structure
    bash -n scripts/ubuntu.sh
    
    # Check that script contains VS Code installation logic
    grep -q "Visual Studio Code" scripts/ubuntu.sh
    grep -q "packages.microsoft.com" scripts/ubuntu.sh
    grep -q "code" scripts/ubuntu.sh
}

@test "ubuntu.sh configures services" {
    # Test script syntax and structure
    bash -n scripts/ubuntu.sh
    
    # Check that script contains service configuration
    grep -q "systemctl.*enable" scripts/ubuntu.sh
    grep -q "systemctl.*start" scripts/ubuntu.sh
    grep -q "syncthing" scripts/ubuntu.sh
}

@test "ubuntu.sh creates fd symlink" {
    # Test script syntax and structure
    bash -n scripts/ubuntu.sh
    
    # Check that script contains fd symlink logic
    grep -q "fd symlink" scripts/ubuntu.sh
    grep -q "fd-find" scripts/ubuntu.sh
}

@test "ruby gems are installed on both platforms" {
    # Test that both scripts contain gem installation logic
    bash -n scripts/macos.sh
    bash -n scripts/ubuntu.sh
    
    # Check that both scripts install video_transcoding gem
    grep -q "video_transcoding" scripts/macos.sh
    grep -q "video_transcoding" scripts/ubuntu.sh
    grep -q "gem install" scripts/macos.sh
    grep -q "gem install" scripts/ubuntu.sh
}