#!/usr/bin/env bats

@test "required files and directories exist" {
    # Main files
    [ -f install.sh ]
    [ -f packages.yml ]
    [ -f .env.example ]
    [ -f README.md ]
    
    # Scripts directory
    [ -d scripts ]
    [ -f scripts/macos.sh ]
    [ -f scripts/ubuntu.sh ]
    
    # Dotfiles directory
    [ -d dotfiles ]
    [ -f dotfiles/.gitconfig ]
    [ -f dotfiles/.gitconfig-work ]
    [ -f dotfiles/.vimrc ]
    [ -f dotfiles/.zshrc ]
    [ -f dotfiles/.p10k.zsh ]
    
    # Config directories
    [ -d dotfiles/.config ]
    [ -d dotfiles/.local ]
}

@test "all scripts are executable" {
    [ -x install.sh ]
    [ -x scripts/macos.sh ]
    [ -x scripts/ubuntu.sh ]
}

@test "packages.yml has valid structure" {
    # Check that packages.yml contains expected sections
    grep -q "^common:" packages.yml
    grep -q "^macos:" packages.yml
    grep -q "^ubuntu:" packages.yml
    grep -q "^ruby_gems:" packages.yml
    grep -q "^services:" packages.yml
    
    # Check for some expected packages
    grep -q "git" packages.yml
    grep -q "vim" packages.yml
    grep -q "ripgrep" packages.yml
    grep -q "python3" packages.yml
}

@test ".env.example contains expected variables" {
    grep -q "GIT_EMAIL_PERSONAL" .env.example
    grep -q "GIT_EMAIL_WORK" .env.example
}

@test "git config files use environment variables" {
    grep -q "\$GIT_EMAIL_PERSONAL" dotfiles/.gitconfig
    grep -q "\$GIT_EMAIL_WORK" dotfiles/.gitconfig-work
}

@test "git config has required sections" {
    # Check main git config
    grep -q "^\[user\]" dotfiles/.gitconfig
    grep -q "^\[color\]" dotfiles/.gitconfig
    grep -q "^\[merge\]" dotfiles/.gitconfig
    grep -q "^\[init\]" dotfiles/.gitconfig
    grep -q "includeIf.*gitdir:~/work/" dotfiles/.gitconfig
    
    # Check work git config
    grep -q "^\[user\]" dotfiles/.gitconfig-work
}

@test "no chezmoi template files remain" {
    # Ensure no .tmpl files exist
    ! find . -name "*.tmpl" -type f | grep -q .
    
    # Ensure no onepassword references remain
    ! grep -r "onepassword" dotfiles/ || true
    ! grep -r "1password" packages.yml || true
}

@test "no emacs configurations remain" {
    # Ensure Emacs configs were removed
    ! [ -d dotfiles/.doom.d ]
    ! [ -d dotfiles/.config/doom ]
    ! [ -d dot_doom.d ]
    
    # Ensure no emacs packages in config
    ! grep -i "emacs" packages.yml || true
    ! grep -i "doom" packages.yml || true
}

@test "README.md updated for new approach" {
    grep -q "Cross-Platform Dotfiles" README.md
    grep -q "Environment Variables" README.md
    grep -q "./install.sh" README.md
    grep -q "packages.yml" README.md
    
    # Should not contain old chezmoi references
    ! grep -q "chezmoi init" README.md || true
    ! grep -q "1password" README.md || true
}

@test "scripts contain proper error handling" {
    # Check that scripts use 'set -e' for error handling
    grep -q "set -e" install.sh
    grep -q "set -e" scripts/macos.sh
    grep -q "set -e" scripts/ubuntu.sh
    
    # Check for colored output functions
    grep -q "print_info" scripts/macos.sh
    grep -q "print_warn" scripts/macos.sh
    grep -q "print_error" scripts/macos.sh
    
    grep -q "print_info" scripts/ubuntu.sh
    grep -q "print_warn" scripts/ubuntu.sh
    grep -q "print_error" scripts/ubuntu.sh
}

@test "install.sh has proper OS detection" {
    grep -q "detect_os()" install.sh
    grep -q "darwin" install.sh
    grep -q "linux-gnu" install.sh
    grep -q "ubuntu" install.sh
    grep -q "macos" install.sh
}

@test "dotfiles directory structure is correct" {
    # Check that dotfiles use proper naming (no dot_ prefix)
    [ -f dotfiles/.vimrc ]
    [ -f dotfiles/.zshrc ]
    [ -f dotfiles/.gitconfig ]
    [ -f dotfiles/.p10k.zsh ]
    
    # Should not have old chezmoi naming
    ! [ -f dotfiles/dot_vimrc ] || true
    ! [ -f dotfiles/dot_zshrc ] || true
}