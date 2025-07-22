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

# Ensure ~/.local/bin is in PATH and shell configs
ensure_local_bin_in_path() {
    # Create ~/.local/bin if it doesn't exist
    mkdir -p ~/.local/bin
    
    # Add to PATH if not already there
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        print_info "Adding ~/.local/bin to PATH in shell configs..."
        
        # Add to .bashrc if it exists
        if [ -f ~/.bashrc ] && ! grep -q 'PATH.*\.local/bin' ~/.bashrc; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
        fi
        
        # Add to .zshrc if it exists
        if [ -f ~/.zshrc ] && ! grep -q 'PATH.*\.local/bin' ~/.zshrc; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
        fi
        
        print_info "PATH updated in shell configs (restart shell to take effect)"
    fi
}

# Install packages from GitHub releases
process_github_releases() {
    print_info "Processing GitHub releases from packages.yml..."
    
    # Parse github_releases section from packages.yml using a simpler approach
    local temp_file="/tmp/github_releases_$$.yml"
    awk '/^ubuntu:/,/^ruby_gems:/ { if (/^  github_releases:/) found=1; if (found && !/^ruby_gems:/) print }' packages.yml > "$temp_file"
    
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

# Main GitHub releases installer function  
install_from_github_releases() {
    print_info "Installing packages from GitHub releases..."
    
    # Ensure ~/.local/bin is set up properly
    ensure_local_bin_in_path
    
    # Process releases using the helper function
    process_github_releases
}

# Install custom packages via script
install_custom_packages() {
    print_info "Installing custom packages..."
    
    # Ensure ~/.local/bin is set up properly
    ensure_local_bin_in_path
    
    # Parse custom_install section from packages.yml (Ubuntu section only)
    local custom_installs
    mapfile -t custom_installs < <(awk '
/^ubuntu:/,/^ruby_gems:/ {
    if (/^  custom_install:/) { in_custom = 1; next }
    if (/^ruby_gems:/) { in_custom = 0 }
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
        # Set up the sourcing script
        if test -f ~/.local/share/LS_COLORS/LS_COLORS; then
            print_info "Setting up LS_COLORS..."
            cat > ~/.local/share/LS_COLORS/lscolors.sh << 'EOF'
# Load LS_COLORS from trapd00r repository
if [[ -f ~/.local/share/LS_COLORS/LS_COLORS ]]; then
    eval "$(dircolors -b ~/.local/share/LS_COLORS/LS_COLORS)"
fi
EOF
        fi
    else
        print_info "LS_COLORS already installed"
        # Ensure the sourcing script exists
        if [[ ! -f ~/.local/share/LS_COLORS/lscolors.sh ]] && [[ -f ~/.local/share/LS_COLORS/LS_COLORS ]]; then
            print_info "Creating LS_COLORS sourcing script..."
            cat > ~/.local/share/LS_COLORS/lscolors.sh << 'EOF'
# Load LS_COLORS from trapd00r repository
if [[ -f ~/.local/share/LS_COLORS/LS_COLORS ]]; then
    eval "$(dircolors -b ~/.local/share/LS_COLORS/LS_COLORS)"
fi
EOF
        fi
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
    install_from_github_releases
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