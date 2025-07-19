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

# Update package list
update_packages() {
    print_info "Updating package list..."
    sudo apt update
}

# Install packages
install_packages() {
    print_info "Installing Ubuntu packages..."
    
    local packages=(
        python3
        python3-tk
        python3-pip
        coreutils
        cmake
        wget
        curl
        git
        ruby
        ruby-dev
        shellcheck
        graphviz
        jq
        grep
        ansible
        ripgrep
        fd-find
        openjdk-11-jdk
        plantuml
        syncthing
        build-essential
        libssl-dev
        zsh
        vim
        meld
        zsh-syntax-highlighting
        zsh-autosuggestions
    )
    
    for package in "${packages[@]}"; do
        if ! dpkg -l | grep -q "^ii  $package "; then
            print_info "Installing $package..."
            sudo apt install -y "$package" || print_warn "Failed to install $package"
        else
            print_info "$package is already installed"
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

# Install zplug (zsh plugin manager)
install_zplug() {
    if ! test -d ~/.local/share/zplug; then
        print_info "Installing zplug..."
        git clone https://github.com/zplug/zplug ~/.local/share/zplug
    else
        print_info "zplug already installed"
    fi
}

# Install LS_COLORS
install_ls_colors() {
    if ! test -d ~/.local/share/LS_COLORS; then
        print_info "Installing LS_COLORS..."
        git clone https://github.com/trapd00r/LS_COLORS ~/.local/share/LS_COLORS
        # Set up dircolors
        if test -f ~/.local/share/LS_COLORS/LS_COLORS; then
            print_info "Setting up LS_COLORS..."
            dircolors -b ~/.local/share/LS_COLORS/LS_COLORS > ~/.dircolors
        fi
    else
        print_info "LS_COLORS already installed"
    fi
}

# Start and enable services
configure_services() {
    print_info "Configuring services..."
    
    # Enable and start syncthing
    if ! systemctl --user is-enabled syncthing &> /dev/null; then
        print_info "Enabling syncthing service..."
        systemctl --user enable syncthing
        systemctl --user start syncthing
    else
        print_info "Syncthing service already enabled"
    fi
}

# Install Visual Studio Code (if not already installed)
install_vscode() {
    if ! command -v code &> /dev/null; then
        print_info "Installing Visual Studio Code..."
        
        # Add Microsoft GPG key and repository
        wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > packages.microsoft.gpg
        sudo install -o root -g root -m 644 packages.microsoft.gpg /etc/apt/trusted.gpg.d/
        sudo sh -c 'echo "deb [arch=amd64,arm64,armhf signed-by=/etc/apt/trusted.gpg.d/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main" > /etc/apt/sources.list.d/vscode.list'
        
        # Update package list and install
        sudo apt update
        sudo apt install -y code
        
        # Clean up
        rm packages.microsoft.gpg
    else
        print_info "Visual Studio Code already installed"
    fi
}

# Configure git to use fd instead of fd-find
configure_fd() {
    # On Ubuntu, fd is installed as fd-find, so we need to create a symlink
    if command -v fd-find &> /dev/null && ! command -v fd &> /dev/null; then
        print_info "Creating fd symlink..."
        mkdir -p ~/.local/bin
        ln -sf "$(which fd-find)" ~/.local/bin/fd
        
        # Add ~/.local/bin to PATH if not already there
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
        fi
    fi
}

# Main function
main() {
    print_info "Setting up Ubuntu environment..."
    
    update_packages
    install_packages
    install_ruby_gems
    install_zplug
    install_ls_colors
    install_vscode
    configure_fd
    configure_services
    
    print_info "Ubuntu setup complete!"
    print_info "Please log out and log back in for all changes to take effect"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi