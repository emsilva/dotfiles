# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Testing
```bash
make test
```
Runs Bats tests in the `test/` directory. Tests verify setup scripts handle Homebrew installations correctly.

### Setup
```bash
# Apply dotfiles to system
chezmoi apply

# Run macOS setup (installs Homebrew packages, clones repos)
bin/executable_set-me-up.sh

# Configure macOS system defaults
bin/executable_macos-sane-defaults.sh
```

## Architecture

This is a dotfiles repository managed by **chezmoi**. Files prefixed with `dot_` become dotfiles when applied (e.g., `dot_vimrc` becomes `.vimrc`).

### Key Components

**Chezmoi Management**: Configuration in `dot_config/chezmoi/chezmoi.toml` defines editor and diff tools.

**Shell Environment**: `dot_zshrc` configures Zsh with oh-my-zsh and zplug plugin management. Prompt styling in `dot_p10k.zsh` (Powerlevel10k theme).

**Git Templates**: `dot_gitconfig.tmpl` and `dot_gitconfig-work.tmpl` use template variables that pull email addresses from 1Password during chezmoi application.

**Editor Configurations**: 
- `dot_vimrc` for Vim settings
- `dot_doom.d/` contains Doom Emacs configuration with modules (`init.el`) and personal tweaks (`config.el`)

**macOS Integration**: 
- `bin/executable_set-me-up.sh` automates Homebrew package installation
- `bin/executable_macos-sane-defaults.sh` sets system preferences
- `dot_local/share/iterm2/` contains iTerm2 preference files

**Testing**: Bats tests in `test/` verify setup script behavior, particularly Homebrew command handling with complex package names and options.