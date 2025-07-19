# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Testing
```bash
# Unit tests
make test

# Integration tests (requires Docker)
make integration-test
./integration-tests/verify-setup.sh  # Check setup first
```
Unit tests use Bats framework in the `test/` directory. Integration tests use Docker containers to simulate real OS environments (Ubuntu, macOS simulation, Alpine).

### Setup
```bash
# Install dotfiles (cross-platform)
./install.sh

# Set environment variables first (optional)
export GIT_EMAIL_PERSONAL="your.personal@email.com"
export GIT_EMAIL_WORK="your.work@email.com"

# Or create .env.local file
cp .env.example .env.local
# Edit .env.local with your values
```

## Architecture

This is a **simplified cross-platform dotfiles repository** using symlinks. No external dependencies like chezmoi or 1Password required.

### Key Components

**Installation**: `install.sh` is the main entry point that:
- Detects OS (macOS or Ubuntu)
- Runs platform-specific setup scripts
- Creates symlinks from `dotfiles/` to home directory
- Substitutes environment variables in git configs

**Platform Scripts**:
- `scripts/macos.sh` - Homebrew packages, macOS defaults, iTerm2 setup
- `scripts/ubuntu.sh` - APT packages, Visual Studio Code, service configuration

**Package Management**: `packages.yml` defines packages for each platform in unified YAML format.

**Dotfiles Structure**: `dotfiles/` directory contains actual configuration files:
- `.gitconfig` and `.gitconfig-work` - Git configuration with environment variable substitution
- `.vimrc` - Vim settings
- `.zshrc` - Zsh configuration with oh-my-zsh and plugin management
- `.p10k.zsh` - Powerlevel10k prompt configuration
- `.config/` and `.local/` - Application configuration directories

**Environment Configuration**: Uses environment variables instead of templates:
- `GIT_EMAIL_PERSONAL` - Personal git email
- `GIT_EMAIL_WORK` - Work git email
- Defaults to GitHub noreply emails if not set

**Testing Framework**:
- Unit tests: Bats tests in `test/` verify script functionality and structure
- Integration tests: Docker containers in `integration-tests/` validate complete installation on real OS environments

### Cross-Platform Support

**macOS Features**:
- Homebrew package installation with taps and casks
- macOS system defaults configuration (Finder, Dock, trackpad, etc.)
- iTerm2 preference management
- Hot corners and UI behavior customization

**Ubuntu Features**:
- APT package installation
- Visual Studio Code installation from Microsoft repository
- Systemd service management
- fd symlink creation (fd-find → fd)

**Shared Features**:
- Oh-my-zsh installation
- Git configuration with environment variables
- Directory structure creation (~/org, ~/code/work)
- Ruby gem installation
- Symlink management