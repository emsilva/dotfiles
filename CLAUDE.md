# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Testing
```bash
# Unit tests
make test

# Integration tests (requires Podman)
make integration-test
./integration-tests/verify-setup.sh  # Check setup first
```
Unit tests use Bats framework in the `test/` directory. Integration tests use Podman containers to simulate real OS environments (Ubuntu, macOS simulation, Alpine).

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
- Integration tests: Podman containers in `integration-tests/` validate complete installation on real OS environments

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
- ~~**Legacy Chezmoi Artifacts**: Remove `dotfiles/.config/chezmoi/` directory and vim autocmd references~~ ✅ **COMPLETED**
- ~~**Plugin Management**: Consolidate zsh plugins (currently uses both oh-my-zsh and zplug)~~ ✅ **COMPLETED**  
- ~~**Hardcoded Paths**: Ruby gem paths in .zshrc need dynamic detection~~ ✅ **COMPLETED**
- ~~**Mixed Indentation**: .vimrc uses both 2-space and 4-space indentation~~ ✅ **COMPLETED**
- **AWK Parsing Errors**: Fix syntax errors in packages.yml processing (identified via integration tests)
- **Shell Change Failures**: Handle `chsh` authentication failures gracefully in container environments
- **Ruby Gem Failures**: Improve error handling for gem installation failures (video_transcoding gem)

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

### Git Workflow Requirements

**MANDATORY: Commit important changes immediately**

- **Commit after completing each logical feature or fix**
  - Don't bundle multiple unrelated changes into one commit
  - Each commit should represent a single, complete change
  - Use descriptive commit messages explaining the "why"

- **When to commit:**
  - After adding new functionality (with tests)
  - After fixing bugs or issues
  - After refactoring code sections
  - After updating documentation
  - Before starting work on the next feature

- **Commit message format:**
  ```
  Brief description of what was changed
  
  🤖 Generated with [Claude Code](https://claude.ai/code)
  
  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

**Always run tests before committing**: `make test` must pass

### Testing Requirements

**MANDATORY: Always run tests when making changes**

- **Unit tests must pass**: `make test` (30 Bats tests)
  - Run before committing any changes
  - Add new test cases when adding functionality
  - Update existing tests when modifying script behavior
  
- **Integration tests recommended**: `make integration-test` (requires Podman)
  - Test complete installation in real container environments
  - Validates Ubuntu, macOS simulation, Alpine environments
  - Update `integration-tests/validate.sh` when adding new features

**Test Coverage Requirements:**
- **New functionality**: Must have corresponding unit tests in `test/` directory
- **Script changes**: Update platform script tests in `test/platform_scripts.bats`
- **Package additions**: Verify parsing tests in `test/file_structure.bats`
- **Integration validation**: Add checks to `integration-tests/validate.sh` for user-facing features

**Current Test Count:** 30 unit tests, 24+ integration validation checks

### Integration Test Learnings

**Successfully Validated:**
- Container timezone configuration (fixed with `ENV TZ=UTC` + proper timezone setup)
- Package installation process works correctly in Ubuntu 22.04/20.04 environments
- Symlink creation and git configuration substitution mechanisms
- LS_COLORS installation processes
- Overall script execution flow and error handling

**Identified Failure Points:**
1. **`chsh` Authentication Failures**
   - Issue: `chsh -s /usr/bin/zsh` fails with "PAM: Authentication failure" in containers
   - Impact: Default shell cannot be changed in containerized environments
   - Solution needed: Graceful fallback or container-specific handling

2. **Ruby Gem Installation Failures**
   - Issue: `video_transcoding` gem fails to install (network/dependency issues)
   - Impact: Ruby gem installation step fails, potentially stopping installation
   - Solution needed: Better error handling and optional gem installation

3. **AWK Parsing Syntax Errors**
   - Issue: `awk: line 1: syntax error at or near ,` and `awk: line 1: syntax error at or near }`
   - Impact: packages.yml parsing fails in some contexts
   - Solution needed: Review and fix AWK parsing patterns in platform scripts

**Backup/Rollback Priority Areas:**
- Package installation state (before/after package installs)
- Symlink creation/removal (track created symlinks for cleanup)
- Git configuration changes (backup existing configs)
- Shell change operations (revert to original shell on failure)
- File system state (track created directories and files)

### File Organization
```
install.sh           # Main entry point - OS detection, symlinks, git config
packages.yml         # Single source of truth for all packages
scripts/macos.sh     # Homebrew, macOS defaults, iTerm2 setup
scripts/ubuntu.sh    # APT packages, systemd services, Ubuntu-specific
dotfiles/           # Actual config files (symlinked to ~/)
test/               # Unit tests (Bats framework)
integration-tests/  # Podman-based real environment tests
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