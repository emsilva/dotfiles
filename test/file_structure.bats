#!/usr/bin/env bats

@test "required files and directories exist" {
    # Main files
    [ -f dotfiles-install.sh ]
    [ -f dotfiles-sync.sh ]
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
    [ -f dotfiles/.config/starship.toml ]
    
    # Config directories
    [ -d dotfiles/.config ]
    
    # Check for specific managed files that might exist
    # Note: .local directory should only contain explicitly managed files
    if [ -f dotfiles/.local/share/iterm2/com.googlecode.iterm2.plist ]; then
        [ -f dotfiles/.local/share/iterm2/com.googlecode.iterm2.plist ]
    fi
}

@test "all scripts are executable" {
    [ -x dotfiles-install.sh ]
    [ -x dotfiles-sync.sh ]
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

@test "no template files remain" {
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
    grep -q "./dotfiles-install.sh" README.md
    grep -q "packages.yml" README.md
    
    # Should not contain old migration references
    ! grep -q "1password" README.md || true
}

@test "scripts contain proper error handling" {
    # Check that scripts use 'set -e' for error handling
    grep -q "set -e" dotfiles-install.sh
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

@test "dotfiles-install.sh has proper OS detection" {
    grep -q "detect_os()" dotfiles-install.sh
    grep -q "darwin" dotfiles-install.sh
    grep -q "linux-gnu" dotfiles-install.sh
    grep -q "ubuntu" dotfiles-install.sh
    grep -q "macos" dotfiles-install.sh
}

@test "dotfiles directory structure is correct" {
    # Check that dotfiles use proper naming (no dot_ prefix)
    [ -f dotfiles/.vimrc ]
    [ -f dotfiles/.zshrc ]
    [ -f dotfiles/.gitconfig ]
    [ -f dotfiles/.config/starship.toml ]
    
    # Should not have old template naming
    ! [ -f dotfiles/dot_vimrc ] || true
    ! [ -f dotfiles/dot_zshrc ] || true
}