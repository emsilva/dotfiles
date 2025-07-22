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
    mapfile -t common_packages < <(awk '/^common:$/,/^macos:$/ {if ($0 ~ /^  - /) {gsub(/^  - /, ""); print}}' packages.yml)
    
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
    mapfile -t ubuntu_packages < <(awk '/^  apt:$/,/^  custom_install:$|^ruby_gems:$/ {if ($0 ~ /^    - /) {gsub(/^    - /, ""); print}}' packages.yml)
    
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

# Install custom packages via script
install_custom_packages() {
    print_info "Installing custom packages..."
    
    # Parse custom_install section from packages.yml
    local custom_installs
    mapfile -t custom_installs < <(awk '
        /^  custom_install:$/ { in_section = 1; next }
        /^ruby_gems:$/ { in_section = 0; next }
        /^[a-zA-Z]/ { if (match($0, /^  /)) {} else { in_section = 0 } }
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
                print name "|" command "|" description;
            }
        }
    ' packages.yml)
    
    for install_info in "${custom_installs[@]}"; do
        if [[ -n "$install_info" ]]; then
            IFS='|' read -r name command description <<< "$install_info"
            
            # Clean up any stdin redirection artifacts that might have been added
            command=$(echo "$command" | sed 's/ < \/dev\/null//g')
            
            # Check if the program is already installed
            if command -v "$name" &> /dev/null; then
                print_info "$name is already installed"
                continue
            fi
            
            print_info "Installing $name ($description)..."
            print_info "Running: $command"
            
            # Execute the installation command in a clean shell environment
            if /bin/sh -c "$command"; then
                # Verify installation worked by checking if command exists
                if command -v "$name" &> /dev/null; then
                    print_info "Successfully installed $name"
                else
                    print_warn "Installation appeared to succeed but $name command not found"
                fi
            else
                print_warn "Failed to install $name (continuing with other packages)"
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
    mapfile -t services < <(awk '/^  ubuntu:$/,/^  [a-z]/ {if ($0 ~ /^    - /) {gsub(/^    - /, ""); print}}' packages.yml)
    
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
    print_info "Setting up Ubuntu environment..."
    
    update_packages
    install_packages
    install_custom_packages
    install_ruby_gems
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