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
Unit tests use Bats framework in the `test/` directory. Integration tests use Podman containers to simulate real OS environments (Ubuntu, macOS simulation).

### Setup
```bash
# Install dotfiles (cross-platform)
./dotfiles-install.sh

# After installation, dotfiles commands are globally available
# (ensure ~/.local/bin is in PATH)

# Set environment variables first (optional)
export GIT_EMAIL_PERSONAL="your.personal@email.com"
export GIT_EMAIL_WORK="your.work@email.com"

# Or create .env.local file
cp .env.example .env.local
# Edit .env.local with your values
```

### Syncing Changes
```bash
# Commit and push dotfile changes to repository
# Can be run from anywhere after installation
dotfiles-sync

# Or from the dotfiles directory
./dotfiles-sync.sh

# Optional: Enable AI-enhanced commit messages
export OPENAI_API_KEY="your-api-key"
dotfiles-sync
```

### Managing Dotfiles (Global Commands)
```bash
# Add files to management (after installation, works from anywhere)
dotfiles-add ~/.config/starship.toml
dotfiles-add ~/.config/nvim

# Remove files from management
dotfiles-remove .config/starship.toml

# List and check status
dotfiles-list
dotfiles-status
dotfiles-status --fix

# Migrate from old system
dotfiles-migrate
```
The sync script will automatically:
- Change to the dotfiles directory (works from anywhere)
- Stage all changes
- Analyze changed files to generate intelligent commit messages
- Use AI (OpenAI) for complex changes if API key is provided
- Push to the remote repository

**Commit message patterns:**
- Config files: "Update .zshrc configuration" 
- Scripts: "Improve scripts/ubuntu.sh functionality"
- Tests: "Add test coverage for recent changes"
- Documentation: "Update documentation and project guidelines"
- Fallback: "Update dotfiles configuration"

## Architecture

This is a **simplified cross-platform dotfiles repository** using **selective symlink management**. No external dependencies like chezmoi or 1Password required.

### Key Components

**Installation**: `dotfiles-install.sh` is the main entry point that:
- Detects OS (macOS or Ubuntu)
- Runs platform-specific setup scripts
- Creates symlinks based on `.dotfiles-manifest` file
- Substitutes environment variables in git configs
- Sets up global dotfiles management commands in `~/.local/bin`

**Dotfiles Management System** (available globally after installation):
- `dotfiles-add` (`dotfiles-add.sh`) - Add files/directories to management
- `dotfiles-remove` (`dotfiles-remove.sh`) - Remove from management and restore originals
- `dotfiles-list` (`dotfiles-list.sh`) - List all managed files with status
- `dotfiles-status` (`dotfiles-status.sh`) - Check and fix symlink issues
- `dotfiles-sync` (`dotfiles-sync.sh`) - Sync changes to git repository
- `dotfiles-migrate` (`dotfiles-migrate.sh`) - Migrate from old system

**Platform Scripts**:
- `scripts/macos.sh` - Homebrew packages, macOS defaults, iTerm2 setup
- `scripts/ubuntu.sh` - APT packages, Visual Studio Code, service configuration

**Package Management**: `packages.yml` defines packages for each platform in unified YAML format.

**Selective Tracking**: `.dotfiles-manifest` file tracks which files are managed:
- Only explicitly added files are symlinked
- Prevents pollution from runtime data or binary installations
- Provides audit trail of what's under version control

**Dotfiles Structure**: `dotfiles/` directory contains **only** managed configuration files:
- `.gitconfig` and `.gitconfig-work` - Git configuration with environment variable substitution
- `.vimrc` - Vim settings  
- `.zshrc` - Zsh configuration with oh-my-zsh and plugin management
- `.config/starship.toml` - Starship prompt configuration
- Other files **only** when explicitly added via `dotfiles-add` command

**Environment Configuration**: Uses environment variables instead of templates:
- `GIT_EMAIL_PERSONAL` - Personal git email
- `GIT_EMAIL_WORK` - Work git email
- Defaults to GitHub noreply emails if not set

**Testing Framework**:
- Unit tests: Bats tests in `test/` verify script functionality and structure
- Integration tests: Podman containers in `integration-tests/` validate complete installation on real OS environments
- New tests in `test/dotfiles_management.bats` for the management system

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

### Dotfiles Management Improvements ✅ **COMPLETED**
- **Selective Management**: Replaced symlink-everything with explicit file tracking
- **Management Scripts**: Added `dotfiles-add.sh`, `dotfiles-remove.sh`, `dotfiles-list.sh`, `dotfiles-status.sh`
- **Migration Tool**: `dotfiles-migrate.sh` for transitioning from old system
- **Manifest System**: `.dotfiles-manifest` tracks managed files
- **Backup System**: Automatic backups during add/remove operations
- **Status Checking**: Health checks and automatic repair capabilities

## Development Guidelines

### Code Standards
- Use `set -e` for error handling in all scripts
- Implement colored output for user feedback (`print_info`, `print_warn`, `print_error`)
- Make operations idempotent where possible
- Parse packages.yml using awk patterns (avoid hardcoded package lists)

### Script Interaction Guidelines
**MANDATORY: All environment-modifying scripts must be interactive by default**

**Required Behavior:**
- **Show preview** of all actions before executing
- **Ask for user confirmation** before proceeding
- **Provide bypass flag** (`-y`, `--yes`, `--skip-confirmation`) for automation
- **Include help option** (`-h`, `--help`) with usage information

**Implementation Pattern:**
```bash
# Function to show action preview
show_preview() {
    echo -e "\n${GREEN}=== SCRIPT PREVIEW ===${NC}"
    echo -e "This script will perform the following actions:"
    echo -e "  ${YELLOW}1. Action description${NC}"
    echo -e "  ${YELLOW}2. Another action${NC}"
    echo -e "${YELLOW}WARNING:${NC} Description of potential impact"
}

# Function to ask for confirmation
confirm_action() {
    local message="$1"
    echo -e "${YELLOW}[CONFIRM]${NC} $message"
    read -r -p "Do you want to proceed? (y/N): " response
    case "$response" in [yY]*) return 0;; *) exit 0;; esac
}

# Main function with argument parsing
main() {
    local skip_confirmation=false
    while [[ $# -gt 0 ]]; do
        case $1 in
            -y|--yes|--skip-confirmation) skip_confirmation=true; shift ;;
            -h|--help) show_help; exit 0 ;;
            *) print_error "Unknown option: $1"; exit 1 ;;
        esac
    done
    
    show_preview
    [[ "$skip_confirmation" != true ]] && confirm_action "Proceed with actions?"
    # ... perform actions
}
```

**Scripts that MUST follow this pattern:**
- `dotfiles-install.sh` - System and environment modifications
- `dotfiles-sync.sh` - Git operations and pushes
- Any `scripts/*.sh` that modify system state
- All future scripts that change files, install packages, or modify configuration

### AI/Claude Attribution Policy
**IMPORTANT: No Claude or Anthropic attribution in commits or code**
- Do NOT add Claude Code attribution to commit messages
- Do NOT add "Co-Authored-By: Claude" to commits
- Use clean, descriptive commit messages following the existing project style
- Focus on "what" and "why" rather than "who" created the changes
- All commits should appear as normal human-authored commits

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
  
  Optional longer explanation of why the change was needed
  and what specific problem it solves.
  ```

**CRITICAL: Always run tests before committing**: `make test` must pass

**NEVER commit without running tests first**

### Testing Requirements

**MANDATORY: Always run tests when making changes**

- **Unit tests must pass**: `make test` (30 Bats tests)
  - Run before committing any changes
  - Add new test cases when adding functionality
  - Update existing tests when modifying script behavior
  
- **Integration tests recommended**: `make integration-test` (requires Podman)
  - Test complete installation in real container environments
  - Validates Ubuntu, macOS simulation environments
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
dotfiles-install.sh    # Main entry point - OS detection, symlinks, git config
dotfiles-sync.sh       # Commit and push changes to repository
packages.yml           # Single source of truth for all packages
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