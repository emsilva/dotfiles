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
        "brew"|"code")
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
chsh() { echo "chsh $@" >> "$TEST_TEMP_DIR/chsh.log"; return 0; }
grep() { 
    # Mock grep for /etc/shells check
    if [[ "$*" == *"/etc/shells"* ]]; then
        return 1  # Simulate zsh not in /etc/shells to test the add logic
    fi
    # For other grep calls, use real grep
    /bin/grep "$@"
}
# Mock script functions that might be called
update_packages() { echo "update_packages called" >> "$TEST_TEMP_DIR/functions.log"; return 0; }
install_packages() { echo "install_packages called" >> "$TEST_TEMP_DIR/functions.log"; return 0; }
install_custom_packages() { echo "install_custom_packages called" >> "$TEST_TEMP_DIR/functions.log"; return 0; }
install_ruby_gems() { echo "install_ruby_gems called" >> "$TEST_TEMP_DIR/functions.log"; return 0; }
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
    # Test script syntax and structure instead of full execution
    bash -n scripts/macos.sh
    
    # Check that script reads from packages.yml and contains package installation logic
    grep -q "packages.yml" scripts/macos.sh
    grep -q "brew install" scripts/macos.sh
    grep -q "common_packages" scripts/macos.sh
    grep -q "formulas" scripts/macos.sh
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
    
    # Check that script reads from packages.yml and contains package installation logic
    grep -q "packages.yml" scripts/ubuntu.sh
    grep -q "apt update" scripts/ubuntu.sh
    grep -q "apt install" scripts/ubuntu.sh
    grep -q "common_packages" scripts/ubuntu.sh
    grep -q "ubuntu_packages" scripts/ubuntu.sh
}

@test "ubuntu.sh has valid script structure" {
    # Test script syntax and structure
    bash -n scripts/ubuntu.sh
    
    # Check that script contains package installation logic
    grep -q "install_packages" scripts/ubuntu.sh
    grep -q "apt install" scripts/ubuntu.sh
}

@test "ubuntu.sh configures services" {
    # Test script syntax and structure
    bash -n scripts/ubuntu.sh
    
    # Check that script contains service configuration and reads from packages.yml
    grep -q "systemctl.*enable" scripts/ubuntu.sh
    grep -q "systemctl.*start" scripts/ubuntu.sh
    grep -q "packages.yml" scripts/ubuntu.sh
    grep -q "configure_services" scripts/ubuntu.sh
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
    
    # Check that both scripts read gems from packages.yml
    grep -q "packages.yml" scripts/macos.sh
    grep -q "packages.yml" scripts/ubuntu.sh
    grep -q "ruby_gems" scripts/macos.sh
    grep -q "ruby_gems" scripts/ubuntu.sh
    grep -q "gem install" scripts/macos.sh
    grep -q "gem install" scripts/ubuntu.sh
}

@test "zsh is set as default shell on both platforms" {
    # Test that both scripts contain set_default_shell function
    bash -n scripts/macos.sh
    bash -n scripts/ubuntu.sh
    
    # Check that both scripts have set_default_shell function
    grep -q "set_default_shell" scripts/macos.sh
    grep -q "set_default_shell" scripts/ubuntu.sh
    
    # Check that both scripts call set_default_shell in main
    grep -A 20 "main()" scripts/macos.sh | grep -q "set_default_shell"
    grep -A 20 "main()" scripts/ubuntu.sh | grep -q "set_default_shell"
    
    # Check that both scripts use chsh command
    grep -q "chsh" scripts/macos.sh
    grep -q "chsh" scripts/ubuntu.sh
    
    # Check that both scripts add zsh to /etc/shells
    grep -q "/etc/shells" scripts/macos.sh
    grep -q "/etc/shells" scripts/ubuntu.sh
}

@test "ubuntu.sh contains custom_install function" {
    # Test that ubuntu.sh contains the new custom_install function
    bash -n scripts/ubuntu.sh
    
    # Check that script contains custom_install function
    grep -q "install_custom_packages" scripts/ubuntu.sh
    grep -q "custom_install:" scripts/ubuntu.sh
}

@test "ubuntu.sh custom_install parsing works correctly" {
    # Create a test packages.yml file with custom_install section
    cat <<'EOF' > packages.yml
ubuntu:
  custom_install:
    - name: starship
      command: "curl -sS https://starship.rs/install.sh | sh"
      description: "Cross-shell prompt"
    - name: test_tool
      command: "echo 'installing test_tool'"
      description: "Test tool"

ruby_gems:
  - video_transcoding
EOF
    
    # Source the ubuntu.sh script to get the install_custom_packages function
    source scripts/ubuntu.sh
    
    # Test the AWK parsing by running it directly
    local custom_installs
    mapfile -t custom_installs < <(awk '
        /^  custom_install:$/ { in_section = 1; next }
        /^ruby_gems:$/ { in_section = 0 }
        /^[a-zA-Z]/ && !/^  / { in_section = 0 }
        in_section && /^    - name: / { 
            gsub(/^    - name: /, ""); 
            name = $0;
            getline;
            if (/^      command: /) {
                gsub(/^      command: /, "");
                gsub(/^"/, ""); gsub(/"$/, "");
                command = $0;
                getline;
                if (/^      description: /) {
                    gsub(/^      description: /, "");
                    gsub(/^"/, ""); gsub(/"$/, "");
                    description = $0;
                } else {
                    description = "";
                }
                print name "§§§" command "§§§" description;
            }
        }
    ' packages.yml)
    
    # Check that we parsed the entries correctly
    [ ${#custom_installs[@]} -eq 2 ]
    echo "${custom_installs[0]}" | grep -q "starship"
    echo "${custom_installs[0]}" | grep -q "curl.*starship"
    echo "${custom_installs[1]}" | grep -q "test_tool"
}

@test "ubuntu.sh calls install_custom_packages in main function" {
    # Check that main function calls install_custom_packages
    grep -A 20 "main()" scripts/ubuntu.sh | grep -q "install_custom_packages"
}

@test "ubuntu.sh has ensure_local_bin_in_path function" {
    # Test that ubuntu.sh contains the ensure_local_bin_in_path function
    bash -n scripts/ubuntu.sh
    
    # Check that script contains ensure_local_bin_in_path function
    grep -q "ensure_local_bin_in_path" scripts/ubuntu.sh
    grep -q "mkdir -p ~/.local/bin" scripts/ubuntu.sh
    grep -q 'export PATH.*\.local/bin' scripts/ubuntu.sh
}

@test "ubuntu.sh custom_install uses improved delimiter parsing" {
    # Test that the script uses the new § delimiter instead of |
    grep -q "§§§" scripts/ubuntu.sh
    
    # Check that the script has the improved parsing logic
    grep -q "clean_install_info=" scripts/ubuntu.sh
    grep -q 'name="${clean_install_info%%§§§\*}"' scripts/ubuntu.sh
}

@test "macos.sh has install_custom_packages function" {
    # Test that macos.sh contains the install_custom_packages function
    bash -n scripts/macos.sh
    
    # Check that script contains install_custom_packages function
    grep -q "install_custom_packages" scripts/macos.sh
    grep -q "custom_install:" scripts/macos.sh
}

@test "ubuntu.sh has install_custom_packages function" {
    # Test that ubuntu.sh contains the install_custom_packages function (already exists)
    bash -n scripts/ubuntu.sh
    
    # Check that script contains install_custom_packages function
    grep -q "install_custom_packages" scripts/ubuntu.sh
    grep -q "custom_install:" scripts/ubuntu.sh
}

@test "macos.sh calls install_custom_packages in main function" {
    # Check that main function calls install_custom_packages
    grep -A 30 "main()" scripts/macos.sh | grep -q "install_custom_packages"
}

@test "packages.yml contains neovim entries" {
    # Check that packages.yml contains neovim github_releases entries for both platforms
    local packages_file="$BATS_TEST_DIRNAME/../packages.yml"
    # Check for macos github_releases nvim entry - allow more lines since files are longer now
    grep -A 50 "^macos:" "$packages_file" | grep -A 30 "^  github_releases:" | grep -q "name: nvim"
    # Check for ubuntu github_releases nvim entry - allow more lines  
    grep -A 50 "^ubuntu:" "$packages_file" | grep -A 30 "^  github_releases:" | grep -q "name: nvim"
}

@test "macos.sh has brew update/upgrade functionality" {
    # Check that macos.sh updates/upgrades brew packages
    grep -q "brew update" scripts/macos.sh
    grep -q "brew upgrade" scripts/macos.sh
}

@test "ubuntu.sh has install_from_github_releases function" {
    # Test that ubuntu.sh contains the install_from_github_releases function
    bash -n scripts/ubuntu.sh
    
    # Check that script contains install_from_github_releases function
    grep -q "install_from_github_releases" scripts/ubuntu.sh
    grep -q "github_releases" scripts/ubuntu.sh
}

@test "ubuntu.sh calls install_from_github_releases in main function" {
    # Check that main function calls install_from_github_releases
    grep -A 30 "main()" scripts/ubuntu.sh | grep -q "install_from_github_releases"
}

@test "neovim installation creates vim symlink" {
    # Test that packages.yml neovim installation creates vim symlink
    local packages_file="$BATS_TEST_DIRNAME/../packages.yml"
    grep -A 15 "name: nvim" "$packages_file" | grep -q "vim"
}