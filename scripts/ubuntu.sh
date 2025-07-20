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
    
    # Install common packages
    print_info "Installing common packages..."
    local common_packages
    mapfile -t common_packages < <(awk '/^common:/,/^macos:/ {if ($0 ~ /^  - /) print $2}' packages.yml)
    
    for package in "${common_packages[@]}"; do
        if [[ -n "$package" ]]; then
            if ! dpkg -l | grep -q "^ii  $package "; then
                print_info "Installing common package: $package..."
                sudo apt install -y "$package" || print_warn "Failed to install $package"
            else
                print_info "$package is already installed"
            fi
        fi
    done
    
    # Install Ubuntu-specific packages from packages.yml
    print_info "Installing Ubuntu-specific packages..."
    local ubuntu_packages
    mapfile -t ubuntu_packages < <(awk '/^ubuntu:/,/^ruby_gems:/ {if ($0 ~ /^  apt:/,/^ruby_gems:/) {if ($0 ~ /^    - /) print $2}}' packages.yml)
    
    for package in "${ubuntu_packages[@]}"; do
        if [[ -n "$package" ]]; then
            if ! dpkg -l | grep -q "^ii  $package "; then
                print_info "Installing Ubuntu package: $package..."
                sudo apt install -y "$package" || print_warn "Failed to install $package"
            else
                print_info "$package is already installed"
            fi
        fi
    done
}

# Install Ruby gems
install_ruby_gems() {
    print_info "Installing Ruby gems..."
    
    local gems
    mapfile -t gems < <(awk '/^ruby_gems:/,/^services:/ {if ($0 ~ /^  - /) print $2}' packages.yml)
    
    for gem in "${gems[@]}"; do
        if [[ -n "$gem" ]]; then
            if ! gem list | grep "$gem" &> /dev/null; then
                print_info "Installing gem: $gem"
                gem install "$gem" || print_warn "Failed to install $gem"
            fi
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
    
    local services
    mapfile -t services < <(awk '/^services:/,/^[a-z]/ {if ($0 ~ /^  ubuntu:/,/^  [a-z]/) {if ($0 ~ /^    - /) print $2}}' packages.yml)
    
    for service in "${services[@]}"; do
        if [[ -n "$service" ]]; then
            if ! systemctl --user is-enabled "$service" &> /dev/null; then
                print_info "Enabling $service service..."
                systemctl --user enable "$service"
                systemctl --user start "$service"
            else
                print_info "$service service already enabled"
            fi
        fi
    done
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

# Configure Podman for rootless operation
configure_podman() {
    if command -v podman &> /dev/null; then
        print_info "Configuring Podman for rootless operation..."
        
        # Enable and start podman socket for user
        systemctl --user enable podman.socket || print_warn "Failed to enable podman socket"
        systemctl --user start podman.socket || print_warn "Failed to start podman socket"
        
        # Configure subuid and subgid if not already configured
        local username=$(whoami)
        if ! grep -q "^${username}:" /etc/subuid 2>/dev/null; then
            print_info "Configuring subuid and subgid for rootless Podman..."
            echo "${username}:100000:65536" | sudo tee -a /etc/subuid > /dev/null
            echo "${username}:100000:65536" | sudo tee -a /etc/subgid > /dev/null
        fi
        
        # Initialize Podman if needed
        if ! podman info &> /dev/null; then
            print_info "Initializing Podman..."
            podman system migrate || print_warn "Podman migration failed"
        fi
    fi
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
    
    # Change default shell
    if chsh -s "$zsh_path"; then
        print_info "Default shell changed to zsh"
        print_warn "Please restart your terminal or log out/in for the change to take effect"
    else
        print_error "Failed to change default shell to zsh"
        return 1
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
    configure_fd
    configure_podman
    configure_services
    set_default_shell
    
    print_info "Ubuntu setup complete!"
    print_info "Please log out and log back in for all changes to take effect"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi