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

## Known Issues & TODOs

### Current Technical Debt
- **Legacy Chezmoi Artifacts**: Remove `dotfiles/.config/chezmoi/` directory and vim autocmd references
- **Plugin Management**: Consolidate zsh plugins (currently uses both oh-my-zsh and zplug)
- **Hardcoded Paths**: Ruby gem paths in .zshrc need dynamic detection
- **Mixed Indentation**: .vimrc uses both 2-space and 4-space indentation

### Key Improvement Areas
- **Error Recovery**: Add backup/rollback mechanisms for failed installations
- **User Experience**: Interactive installation mode, progress indicators
- **Performance**: Package caching, parallel installations
- **Security**: GPG verification for downloads, checksum validation

## Development Guidelines

### Code Standards
- Use `set -e` for error handling in all scripts
- Implement colored output for user feedback (`print_info`, `print_warn`, `print_error`)
- Make operations idempotent where possible
- Parse packages.yml using awk patterns (avoid hardcoded package lists)

### Testing Requirements
- Unit tests must pass: `make test` (28 Bats tests)
- Integration tests recommended: `make integration-test` (requires Docker)
- Update tests when modifying package lists or script logic

### File Organization
```
install.sh           # Main entry point - OS detection, symlinks, git config
packages.yml         # Single source of truth for all packages
scripts/macos.sh     # Homebrew, macOS defaults, iTerm2 setup
scripts/ubuntu.sh    # APT packages, systemd services, Ubuntu-specific
dotfiles/           # Actual config files (symlinked to ~/)
test/               # Unit tests (Bats framework)
integration-tests/  # Docker-based real environment tests
```

### Common Tasks

**Adding New Packages:**
1. Edit `packages.yml` only (scripts auto-parse)
2. Add to appropriate section: common, macos.homebrew.formulas, ubuntu.apt
3. Run tests to verify parsing works

**Modifying Scripts:**
1. Update the relevant platform script (macos.sh or ubuntu.sh)
2. Ensure awk parsing patterns match packages.yml structure
3. Test locally and run full test suite

**Environment Variables:**
- `GIT_EMAIL_PERSONAL` - Personal git email
- `GIT_EMAIL_WORK` - Work git email
- Defaults to GitHub noreply emails if unset

### Platform-Specific Notes

**macOS Limitations:**
- Requires Homebrew for package management
- macOS defaults only apply after restart/logout
- iTerm2 preferences require manual import

**Ubuntu Limitations:**
- APT packages only (no snap support currently)
- systemd user services may need manual start
- fd-find symlinked to fd for compatibility

### Architecture Decisions

**Why Symlinks vs Templates:**
- Simplicity: No templating engine required
- Transparency: Easy to see actual file contents
- Git Integration: Changes tracked in repository
- Cross-platform: Works identically on macOS/Ubuntu

**Why AWK vs YAML Parser:**
- Dependency Reduction: AWK available everywhere
- Performance: Faster than Python/Ruby YAML libs
- Reliability: Simple parsing patterns less error-prone
- Maintainability: Easy to understand and modify patterns