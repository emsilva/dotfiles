#!/usr/bin/env bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Function to ask for user confirmation
confirm_action() {
    local message="$1"
    echo -e "${YELLOW}[CONFIRM]${NC} $message"
    read -r -p "Do you want to proceed? (y/N): " response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            return 0
            ;;
        *)
            print_info "Operation cancelled by user."
            exit 0
            ;;
    esac
}

# Detect operating system
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt &> /dev/null; then
            echo "ubuntu"
        else
            print_error "Unsupported Linux distribution. Only Ubuntu is supported."
            exit 1
        fi
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
}

# Function to create symlinks using manifest
create_symlinks() {
    print_info "Creating symlinks for managed dotfiles..."
    
    DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dotfiles"
    MANIFEST_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.dotfiles-manifest"
    
    # Check if manifest exists
    if [[ ! -f "$MANIFEST_FILE" ]]; then
        print_warn "No dotfiles manifest found. Creating empty manifest."
        print_info "Use './dotfiles-add.sh <file>' to start managing files"
        touch "$MANIFEST_FILE"
        return
    fi
    
    # Read manifest and create symlinks
    local created_count=0
    local skipped_count=0
    
    while IFS= read -r rel_path; do
        # Skip empty lines
        [[ -z "$rel_path" ]] && continue
        
        local dotfiles_path="$DOTFILES_DIR/$rel_path"
        local target_path="$HOME/$rel_path"
        
        # Check if dotfile exists
        if [[ ! -e "$dotfiles_path" ]]; then
            print_warn "Managed file not found: $dotfiles_path"
            continue
        fi
        
        # Create parent directory if needed
        mkdir -p "$(dirname "$target_path")"
        
        # Handle existing files
        if [[ -e "$target_path" ]] || [[ -L "$target_path" ]]; then
            if [[ -L "$target_path" ]]; then
                local current_target
                current_target=$(readlink "$target_path")
                if [[ "$current_target" == "$dotfiles_path" ]]; then
                    ((skipped_count++))
                    continue
                fi
            fi
            
            print_warn "Removing existing $target_path"
            rm -rf "$target_path"
        fi
        
        # Create symlink
        ln -s "$dotfiles_path" "$target_path"
        print_info "Linked $rel_path"
        ((created_count++))
        
    done < "$MANIFEST_FILE"
    
    print_info "Symlink creation complete: $created_count created, $skipped_count already existed"
    
    # Clean up orphaned symlinks that point to our dotfiles directory
    print_info "Cleaning up orphaned dotfiles symlinks..."
    local cleaned_count=0
    
    # Check common dotfile locations
    for pattern in "$HOME"/.[!.]* "$HOME"/.config/* "$HOME"/.local/bin/*; do
        [[ -e "$pattern" ]] || continue
        
        if [[ -L "$pattern" ]]; then
            local link_target
            link_target=$(readlink "$pattern")
            
            # Check if it points to our dotfiles directory but isn't in manifest
            if [[ "$link_target" == *"/dotfiles/"* ]]; then
                local rel_pattern="${pattern#$HOME/}"
                
                # Check if this path is in manifest
                if ! grep -q "^$rel_pattern$" "$MANIFEST_FILE" 2>/dev/null; then
                    print_warn "Removing orphaned dotfiles symlink: $rel_pattern"
                    rm "$pattern"
                    ((cleaned_count++))
                fi
            fi
        fi
    done
    
    if [[ $cleaned_count -gt 0 ]]; then
        print_info "Cleaned up $cleaned_count orphaned symlinks"
    fi
}

# Function to substitute environment variables in git config
setup_git_config() {
    print_info "Setting up git configuration with environment variables..."
    
    # Set defaults if environment variables are not set
    if [ -z "$GIT_EMAIL_PERSONAL" ]; then
        export GIT_EMAIL_PERSONAL="mannu@users.noreply.github.com"
        print_warn "GIT_EMAIL_PERSONAL not set, using default GitHub noreply email"
    fi
    
    if [ -z "$GIT_EMAIL_WORK" ]; then
        export GIT_EMAIL_WORK="mannu.work@users.noreply.github.com"
        print_warn "GIT_EMAIL_WORK not set, using default GitHub noreply work email"
    fi
    
    # Substitute environment variables in git config files
    envsubst < "$HOME/.gitconfig" > /tmp/.gitconfig.tmp && mv /tmp/.gitconfig.tmp "$HOME/.gitconfig"
    envsubst < "$HOME/.gitconfig-work" > /tmp/.gitconfig-work.tmp && mv /tmp/.gitconfig-work.tmp "$HOME/.gitconfig-work"
    
    print_info "Git configuration updated"
}

# Function to create folders
create_folders() {
    print_info "Creating standard directories..."
    
    directories=(
        "$HOME/org"
        "$HOME/code/work"
        "$HOME/.local/bin"
    )
    
    for dir in "${directories[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            print_info "Created directory: $dir"
        fi
    done
}

# Function to symlink dotfiles management scripts to ~/.local/bin
setup_dotfiles_scripts() {
    print_info "Setting up dotfiles management scripts..."
    
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local bin_dir="$HOME/.local/bin"
    
    # List of scripts to symlink
    local scripts=(
        "dotfiles-add.sh"
        "dotfiles-remove.sh"
        "dotfiles-list.sh"
        "dotfiles-status.sh"
        "dotfiles-sync.sh"
        "dotfiles-migrate.sh"
    )
    
    for script in "${scripts[@]}"; do
        local script_path="$script_dir/$script"
        local symlink_name="${script%.sh}"  # Remove .sh extension
        local symlink_path="$bin_dir/$symlink_name"
        
        # Remove existing symlink or file
        if [[ -e "$symlink_path" ]] || [[ -L "$symlink_path" ]]; then
            rm "$symlink_path"
        fi
        
        # Create symlink
        ln -s "$script_path" "$symlink_path"
        print_info "Linked $symlink_name -> $script"
    done
    
    print_info "Dotfiles scripts are now available globally (ensure ~/.local/bin is in PATH)"
}

# Function to install oh-my-zsh
install_oh_my_zsh() {
    if ! test -d "$HOME/.oh-my-zsh/"; then
        print_info "Installing oh-my-zsh..."
        sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --keep-zshrc
    else
        print_info "oh-my-zsh already installed"
    fi
}

# Function to set default shell
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

# Function to show installation preview
show_installation_preview() {
    local os="$1"
    
    echo -e "\n${GREEN}=== DOTFILES INSTALLATION PREVIEW ===${NC}"
    echo -e "This script will perform the following actions:"
    echo -e ""
    echo -e "  ${YELLOW}1. Install packages${NC} for $os (via ./scripts/$os.sh)"
    echo -e "  ${YELLOW}2. Create symlinks${NC} for dotfiles in your home directory"
    echo -e "  ${YELLOW}3. Setup git configuration${NC} with environment variables"
    echo -e "  ${YELLOW}4. Create standard directories${NC} (~/org, ~/code/work, ~/.local/bin)"
    echo -e "  ${YELLOW}5. Setup dotfiles scripts${NC} in ~/.local/bin (dotfiles-add, etc.)"
    echo -e "  ${YELLOW}6. Install oh-my-zsh${NC} (if not already installed)"
    echo -e "  ${YELLOW}7. Set zsh as default shell${NC}"
    echo -e ""
    echo -e "${YELLOW}WARNING:${NC} This will modify your system and home directory."
    echo -e "Existing files may be backed up or replaced."
    echo -e ""
}

# Main installation function
main() {
    # Parse command line arguments
    local skip_confirmation=false
    while [[ $# -gt 0 ]]; do
        case $1 in
            -y|--yes|--skip-confirmation)
                skip_confirmation=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  -y, --yes, --skip-confirmation    Skip confirmation prompts"
                echo "  -h, --help                        Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use -h or --help for usage information."
                exit 1
                ;;
        esac
    done
    
    print_info "Starting dotfiles installation..."
    
    # Detect OS
    OS=$(detect_os)
    print_info "Detected OS: $OS"
    
    # Show preview and get confirmation
    show_installation_preview "$OS"
    
    if [[ "$skip_confirmation" != true ]]; then
        confirm_action "The above actions will be performed on your system."
    fi
    
    print_info "Proceeding with installation..."
    
    # Install packages for the detected OS
    print_info "Installing packages for $OS..."
    ./scripts/"$OS".sh
    
    # Create symlinks
    create_symlinks
    
    # Setup git configuration
    setup_git_config
    
    # Create standard directories
    create_folders
    
    # Setup dotfiles management scripts
    setup_dotfiles_scripts
    
    # Install oh-my-zsh
    install_oh_my_zsh
    
    # Set default shell
    set_default_shell
    
    print_info "Dotfiles installation complete!"
    print_info ""
    print_info "✅ Dotfiles management commands are now available globally:"
    print_info "   dotfiles-add, dotfiles-remove, dotfiles-list, dotfiles-status, dotfiles-sync"
    print_info ""
    print_info "💡 Don't forget to set your environment variables:"
    print_info "   export GIT_EMAIL_PERSONAL='your.personal@email.com'"
    print_info "   export GIT_EMAIL_WORK='your.work@email.com'"
    print_info ""
    print_info "📚 Quick start:"
    print_info "   dotfiles-add ~/.config/starship.toml  # Add a file to management"
    print_info "   dotfiles-status                       # Check status"
    print_info "   dotfiles-sync                         # Sync changes to git"
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi