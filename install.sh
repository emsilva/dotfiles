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

# Function to create symlinks
create_symlinks() {
    print_info "Creating symlinks for dotfiles..."
    
    DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dotfiles"
    
    # Create necessary directories
    mkdir -p "$HOME/.config"
    mkdir -p "$HOME/.local/share"
    
    # Symlink all dotfiles
    for file in "$DOTFILES_DIR"/.??*; do
        if [ -f "$file" ] || [ -d "$file" ]; then
            filename=$(basename "$file")
            target="$HOME/$filename"
            
            # Remove existing file/symlink
            if [ -e "$target" ] || [ -L "$target" ]; then
                print_warn "Removing existing $target"
                rm -rf "$target"
            fi
            
            # Create symlink
            ln -s "$file" "$target"
            print_info "Linked $filename"
        fi
    done
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
    )
    
    for dir in "${directories[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            print_info "Created directory: $dir"
        fi
    done
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
    if [ "$SHELL" != "$(which zsh)" ]; then
        print_info "Setting zsh as default shell..."
        chsh -s "$(which zsh)"
        print_warn "Please log out and log back in for shell changes to take effect"
    fi
}

# Main installation function
main() {
    print_info "Starting dotfiles installation..."
    
    # Detect OS
    OS=$(detect_os)
    print_info "Detected OS: $OS"
    
    # Install packages for the detected OS
    print_info "Installing packages for $OS..."
    ./scripts/"$OS".sh
    
    # Create symlinks
    create_symlinks
    
    # Setup git configuration
    setup_git_config
    
    # Create standard directories
    create_folders
    
    # Install oh-my-zsh
    install_oh_my_zsh
    
    # Set default shell
    set_default_shell
    
    print_info "Dotfiles installation complete!"
    print_info "Don't forget to set your environment variables:"
    print_info "  export GIT_EMAIL_PERSONAL='your.personal@email.com'"
    print_info "  export GIT_EMAIL_WORK='your.work@email.com'"
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi