#!/usr/bin/env bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Install Homebrew if not present
install_homebrew() {
    if ! command -v brew &> /dev/null; then
        print_info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    else
        print_info "Homebrew already installed"
    fi
}

# Update Homebrew and upgrade packages
update_homebrew() {
    print_info "Updating Homebrew..."
    brew update || print_warn "Failed to update Homebrew"
    
    print_info "Upgrading Homebrew packages..."
    brew upgrade || print_warn "Failed to upgrade packages"
}

# Install packages from packages.yml
install_packages() {
    print_info "Installing Homebrew packages..."
    
    # Install common packages
    print_info "Installing common packages..."
    local common_packages
    mapfile -t common_packages < <(awk '/^common:$/,/^macos:$/ {if ($0 ~ /^  - /) {gsub(/^  - /, ""); print}}' packages.yml)
    
    for package in "${common_packages[@]}"; do
        if [[ -n "$package" ]]; then
            if ! brew list --formula "$package" &> /dev/null; then
                print_info "Installing common package: $package"
                brew install "$package" || print_warn "Failed to install $package"
            fi
        fi
    done
    
    # Tap repositories from packages.yml
    print_info "Adding Homebrew taps..."
    local taps
    mapfile -t taps < <(awk '/^    taps:$/,/^    [a-z]/ {if ($0 ~ /^      - /) {gsub(/^      - /, ""); print}}' packages.yml)
    
    for tap in "${taps[@]}"; do
        if [[ -n "$tap" ]]; then
            print_info "Adding tap: $tap"
            brew tap "$tap" || print_warn "Failed to add tap $tap"
        fi
    done
    
    # Install macOS-specific formulas from packages.yml
    print_info "Installing macOS-specific packages..."
    local formulas
    mapfile -t formulas < <(awk '/^    formulas:$/,/^    [a-z]/ {if ($0 ~ /^      - /) {gsub(/^      - /, ""); print}}' packages.yml)
    
    for formula in "${formulas[@]}"; do
        if [[ -n "$formula" ]]; then
            if ! brew list --formula "$formula" &> /dev/null; then
                print_info "Installing formula: $formula"
                brew install "$formula" || print_warn "Failed to install $formula"
            fi
        fi
    done
}

# Install Ruby gems
install_ruby_gems() {
    print_info "Installing Ruby gems..."
    
    # Check if Ruby and gem are available
    if ! command -v gem &> /dev/null; then
        print_warn "gem command not found. Skipping Ruby gem installation."
        return 0
    fi
    
    local gems
    mapfile -t gems < <(awk '/^ruby_gems:$/,/^services:$/ {if ($0 ~ /^  - /) {gsub(/^  - /, ""); print}}' packages.yml)
    
    local failed_gems=()
    
    for gem in "${gems[@]}"; do
        if [[ -n "$gem" ]]; then
            if ! gem list | grep "$gem" &> /dev/null; then
                print_info "Installing gem: $gem"
                if gem install "$gem" 2>/dev/null; then
                    print_info "Successfully installed gem: $gem"
                else
                    print_warn "Failed to install gem: $gem (continuing with other gems)"
                    failed_gems+=("$gem")
                fi
            else
                print_info "Gem $gem is already installed"
            fi
        fi
    done
    
    # Report failed gems at the end
    if [[ ${#failed_gems[@]} -gt 0 ]]; then
        print_warn "The following gems failed to install: ${failed_gems[*]}"
        print_info "You can try installing them manually later with: gem install <gem_name>"
    fi
}

# Start services
start_services() {
    print_info "Starting services..."
    
    local services
    mapfile -t services < <(awk '/^  macos:$/,/^  [a-z]/ {if ($0 ~ /^    - /) {gsub(/^    - /, ""); print}}' packages.yml)
    
    for service in "${services[@]}"; do
        if [[ -n "$service" ]]; then
            local service_status=$(brew services list | grep "$service" | awk '{print $2}')
            if [[ "$service_status" == "none" ]]; then
                print_info "Starting service: $service"
                brew services start "$service"
            fi
        fi
    done
}

# Configure macOS defaults
configure_macos_defaults() {
    print_info "Configuring macOS defaults..."
    
    # Finder & Desktop Preferences
    defaults write NSGlobalDomain AppleShowAllExtensions -bool true
    defaults write com.apple.finder FXDefaultSearchScope -string "SCcf"
    defaults write com.apple.finder ShowStatusBar -bool true
    defaults write com.apple.finder ShowPathbar -bool true
    defaults write com.apple.finder NewWindowTarget -string "PfLo"
    defaults write com.apple.finder NewWindowTargetPath -string "file://$HOME/"
    defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"
    chflags nohidden ~/Library
    
    # Dock
    defaults write com.apple.dock autohide-delay -float 0
    defaults write com.apple.dock autohide-time-modifier -float 0
    dockutil --remove all > /dev/null 2>&1 || true
    
    # General UI Behaviour
    defaults write NSGlobalDomain AppleShowScrollBars -string "Always"
    defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -bool true
    defaults write com.apple.AppleMultitouchTrackpad Clicking -bool true
    defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
    defaults write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
    defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadRightClick -bool true
    defaults write com.apple.AppleMultitouchTrackpad TrackpadRightClick -bool true
    defaults -currentHost write NSGlobalDomain com.apple.trackpad.enableSecondaryClick -bool true
    
    # Keyboard
    defaults write -g InitialKeyRepeat -int 10
    defaults write -g KeyRepeat -int 1
    defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false
    defaults write NSGlobalDomain NSAutomaticCapitalizationEnabled -bool false
    defaults write -g ApplePressAndHoldEnabled -bool false
    
    # Hot corners
    defaults write com.apple.dock wvous-tl-corner -int 3    # Top left: Show application windows
    defaults write com.apple.dock wvous-tl-modifier -int 0
    defaults write com.apple.dock wvous-tr-corner -int 4    # Top right: Desktop
    defaults write com.apple.dock wvous-tr-modifier -int 0
    defaults write com.apple.dock wvous-bl-corner -int 2    # Bottom left: Mission Control
    defaults write com.apple.dock wvous-bl-modifier -int 0
    defaults write com.apple.dock wvous-br-corner -int 5    # Bottom right: Start screen saver
    defaults write com.apple.dock wvous-br-modifier -int 0
}

# Install custom packages via script
install_custom_packages() {
    print_info "Installing custom packages..."
    
    # Create ~/.local/bin if it doesn't exist and ensure it's in PATH
    mkdir -p ~/.local/bin
    if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
        print_info "Adding ~/.local/bin to PATH in ~/.zshrc"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
    fi
    
    # Parse custom_install section from packages.yml (macOS section only)
    local custom_installs
    mapfile -t custom_installs < <(awk '
/^macos:/,/^ubuntu:/ {
    if (/^  custom_install:/) { in_custom = 1; next }
    if (/^ubuntu:/) { in_custom = 0 }
    if (in_custom && /^    - name:/) {
        gsub(/^    - name: /, "");
        name = $0;
        getline;
        if (/^      command:/) {
            gsub(/^      command: /, "");
            gsub(/^"/, ""); gsub(/"$/, "");
            command = $0;
            getline;
            if (/^      description:/) {
                gsub(/^      description: /, "");
                gsub(/^"/, ""); gsub(/"$/, "");
                description = $0;
            } else {
                description = "";
            }
            print name "§§§" command "§§§" description;
        }
    }
}' packages.yml)
    
    for install_info in "${custom_installs[@]}"; do
        if [[ -n "$install_info" ]]; then
            # Clean up any stdin redirection artifacts in the entire string first
            clean_install_info=$(echo "$install_info" | sed 's/ < \/dev\/null//g')
            
            # Parse the three fields using parameter expansion
            name="${clean_install_info%%§§§*}"
            rest="${clean_install_info#*§§§}"
            command="${rest%%§§§*}"
            description="${rest#*§§§}"
            
            # Trim whitespace from all fields
            name=$(echo "$name" | sed 's/^[ \t]*//;s/[ \t]*$//')
            command=$(echo "$command" | sed 's/^[ \t]*//;s/[ \t]*$//')
            description=$(echo "$description" | sed 's/^[ \t]*//;s/[ \t]*$//')
            
            # Check if the program is already installed
            # Check both system PATH and ~/.local/bin
            if command -v "$name" &> /dev/null || [ -x "$HOME/.local/bin/$name" ]; then
                print_info "$name is already installed"
                continue
            fi
            
            print_info "Installing $name ($description)..."
            print_info "Running: $command"
            
            # Execute the installation command in a clean shell environment
            if /bin/sh -c "$command"; then
                # Update PATH in current session for immediate use
                export PATH="$HOME/.local/bin:$PATH"
                
                # Verify installation worked by checking if executable exists in expected locations
                # Use a small delay to ensure file system operations are complete
                sleep 0.1
                
                if [ -x "$HOME/.local/bin/$name" ]; then
                    print_info "Successfully installed $name to ~/.local/bin"
                elif command -v "$name" &> /dev/null; then
                    print_info "Successfully installed $name (found in PATH)"
                else
                    print_warn "Installation appeared to succeed but $name executable not found at $HOME/.local/bin/$name"
                fi
            else
                print_warn "Failed to install $name (continuing with other packages)"
            fi
        fi
    done
}

# Install packages from GitHub releases
process_github_releases() {
    print_info "Processing GitHub releases from packages.yml..."
    
    # Parse github_releases section from packages.yml using a simpler approach
    local temp_file="/tmp/github_releases_$$.yml"
    awk '/^macos:/,/^ubuntu:/ { if (/^  github_releases:/) found=1; if (found && !/^ubuntu:/) print }' packages.yml > "$temp_file"
    
    # Process each package in the github_releases section
    local current_name=""
    local current_repo=""
    local current_pattern=""
    local current_dir=""
    local current_desc=""
    local current_executables=""
    
    while IFS= read -r line; do
        case "$line" in
            "    - name: "*)
                # Process previous package if we have one
                if [[ -n "$current_name" ]]; then
                    install_github_release "$current_name" "$current_repo" "$current_pattern" "$current_dir" "$current_executables" "$current_desc"
                fi
                
                # Start new package
                current_name="${line#*: }"
                current_repo=""
                current_pattern=""
                current_dir=""
                current_desc=""
                current_executables=""
                ;;
            "      repo: "*)
                current_repo="${line#*: }"
                ;;
            "      asset_pattern: "*)
                current_pattern="${line#*: }"
                ;;
            "      install_dir: "*)
                current_dir="${line#*: }"
                ;;
            "      description: "*)
                current_desc="${line#*: }"
                current_desc="${current_desc%\"}"
                current_desc="${current_desc#\"}"
                ;;
            "        - src: "*)
                src="${line#*: }"
                ;;
            "          dest: "*)
                dest="${line#*: }"
                if [[ -n "$current_executables" ]]; then
                    current_executables="$current_executables|$src:$dest"
                else
                    current_executables="$src:$dest"
                fi
                ;;
        esac
    done < "$temp_file"
    
    # Process the last package
    if [[ -n "$current_name" ]]; then
        install_github_release "$current_name" "$current_repo" "$current_pattern" "$current_dir" "$current_executables" "$current_desc"
    fi
    
    rm -f "$temp_file"
}

# Helper function to install a single GitHub release
install_github_release() {
    local name="$1"
    local repo="$2"
    local asset_pattern="$3"
    local install_dir="$4"
    local executables="$5"
    local description="$6"
    
    # Check if already installed
    if [[ -n "$executables" ]]; then
        IFS='|' read -ra EXEC_ARRAY <<< "$executables"
        first_exec="${EXEC_ARRAY[0]}"
        IFS=':' read -r src_path dest_path <<< "$first_exec"
        dest_path=$(eval echo "$dest_path")  # Expand ~ and variables
        
        if [[ -x "$dest_path" ]]; then
            print_info "$name is already installed"
            return 0
        fi
    fi
    
    print_info "Installing $name ($description)..."
    
    # Expand install directory
    install_dir=$(eval echo "$install_dir")
    mkdir -p "$install_dir" ~/.local/bin
    
    # Get download URL
    local download_url
    download_url=$(curl -s "https://api.github.com/repos/$repo/releases/latest" | \
                  grep -o "https://github.com/$repo/releases/download/[^\"]*$asset_pattern" | \
                  head -n1)
    
    if [[ -z "$download_url" ]]; then
        print_error "Failed to find download URL for $name with pattern $asset_pattern"
        return 1
    fi
    
    print_info "Downloading from: $download_url"
    
    # Download and extract
    local temp_file="/tmp/${name}.tar.gz"
    if curl -L "$download_url" -o "$temp_file"; then
        # Clear install directory and extract
        rm -rf "$install_dir"/*
        tar -xzf "$temp_file" -C "$install_dir" --strip-components=1
        rm "$temp_file"
        
        # Create executable symlinks
        if [[ -n "$executables" ]]; then
            IFS='|' read -ra EXEC_ARRAY <<< "$executables"
            for exec_mapping in "${EXEC_ARRAY[@]}"; do
                IFS=':' read -r src_path dest_path <<< "$exec_mapping"
                src_full="$install_dir/$src_path"
                dest_full=$(eval echo "$dest_path")  # Expand ~ and variables
                
                if [[ -f "$src_full" ]]; then
                    ln -sf "$src_full" "$dest_full"
                    print_info "Created symlink: $dest_full -> $src_full"
                else
                    print_warn "Source executable not found: $src_full"
                fi
            done
        fi
        
        print_info "Successfully installed $name"
        return 0
    else
        print_error "Failed to download $name"
        return 1
    fi
}

# Configure iTerm2
configure_iterm2() {
    print_info "Configuring iTerm2..."
    
    # Install shell integration
    if ! test -f ~/.iterm2_shell_integration.zsh; then
        curl -L https://iterm2.com/shell_integration/install_shell_integration.sh | bash
    fi
    
    # Set preferences location
    defaults write com.googlecode.iterm2 PrefsCustomFolder -string "~/.local/share/iterm2/"
    defaults write com.googlecode.iterm2 LoadPrefsFromCustomFolder -bool true
}

# Set zsh as default shell
set_default_shell() {
    local zsh_path
    zsh_path="$(which zsh)"
    
    if [[ -z "$zsh_path" ]]; then
        print_error "zsh not found in PATH"
        return 1
    fi
    
    if [[ "$SHELL" == "$zsh_path" ]]; then
        print_info "zsh is already the default shell"
        return 0
    fi
    
    print_info "Setting zsh as default shell..."
    
    # Add zsh to /etc/shells if not present
    if ! grep -Fxq "$zsh_path" /etc/shells; then
        print_info "Adding $zsh_path to /etc/shells"
        echo "$zsh_path" | sudo tee -a /etc/shells > /dev/null
    fi
    
    # Check if we're in a container environment
    if [[ -f /.dockerenv ]] || [[ -n "${container:-}" ]] || [[ "$(systemd-detect-virt 2>/dev/null || echo 'none')" != "none" ]]; then
        print_warn "Container environment detected. Cannot change default shell with chsh."
        print_info "To use zsh, run: exec zsh"
        return 0
    fi
    
    # Change default shell
    if chsh -s "$zsh_path" 2>/dev/null; then
        print_info "Default shell changed to zsh"
        print_warn "Please restart your terminal or log out/in for the change to take effect"
    else
        print_warn "Failed to change default shell to zsh (possibly due to authentication requirements)"
        print_info "You can manually change your shell by running: chsh -s $zsh_path"
        print_info "Or start zsh directly with: exec zsh"
        return 0  # Don't fail the entire setup for this
    fi
}

# Main function
main() {
    print_info "Setting up macOS environment..."
    
    install_homebrew
    update_homebrew
    install_packages
    install_custom_packages
    process_github_releases
    install_ruby_gems
    start_services
    configure_macos_defaults
    configure_iterm2
    set_default_shell
    
    print_info "macOS setup complete!"
    print_warn "Please restart your computer for all changes to take effect"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi