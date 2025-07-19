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

# Install packages from packages.yml
install_packages() {
    print_info "Installing Homebrew packages..."
    
    # Parse packages.yml and install (simplified approach)
    # In a real implementation, you'd want to use a proper YAML parser
    # For now, we'll just install the packages we know we need
    
    # Tap repositories
    brew tap trapd00r/LS_COLORS || true
    
    # Install formulas
    local formulas=(
        python3
        python-tk@3.9
        coreutils
        cmake
        wget
        dockutil
        mysides
        ruby
        mosh
        shellcheck
        graphviz
        jq
        grep
        ansible
        ripgrep
        fd
        plantuml
        syncthing
        openjdk
        handbrake
        marked
        mactex
        tradingview
        zplug
    )
    
    for formula in "${formulas[@]}"; do
        if ! brew list --formula "$formula" &> /dev/null; then
            print_info "Installing formula: $formula"
            brew install "$formula" || print_warn "Failed to install $formula"
        fi
    done
    
    # Install casks
    local casks=(
        iterm2
        visual-studio-code
        monitorcontrol
        whatsapp
        telegram
        signal
    )
    
    for cask in "${casks[@]}"; do
        if ! brew list --cask "$cask" &> /dev/null; then
            print_info "Installing cask: $cask"
            brew install --cask "$cask" || print_warn "Failed to install $cask"
        fi
    done
}

# Install Ruby gems
install_ruby_gems() {
    print_info "Installing Ruby gems..."
    
    local gems=(
        video_transcoding
    )
    
    for gem in "${gems[@]}"; do
        if ! gem list | grep "$gem" &> /dev/null; then
            print_info "Installing gem: $gem"
            gem install "$gem" || print_warn "Failed to install $gem"
        fi
    done
}

# Start services
start_services() {
    print_info "Starting services..."
    
    local services=(
        syncthing
    )
    
    for service in "${services[@]}"; do
        local service_status=$(brew services list | grep "$service" | awk '{print $2}')
        if [[ "$service_status" == "none" ]]; then
            print_info "Starting service: $service"
            brew services start "$service"
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

# Main function
main() {
    print_info "Setting up macOS environment..."
    
    install_homebrew
    install_packages
    install_ruby_gems
    start_services
    configure_macos_defaults
    configure_iterm2
    
    print_info "macOS setup complete!"
    print_warn "Please restart your computer for all changes to take effect"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi