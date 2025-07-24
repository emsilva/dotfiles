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

## Development State & Progress Tracking

### Current Active Development (Updated: 2025-07-24)

**🎯 PRIMARY GOAL: Achieve 100% Test Passing (TDD Compliance)**
- **Current Status**: 99/107 tests passing (~93%)
- **Target**: 107/107 tests passing (100%)
- **Estimated Effort**: 1-2 hours remaining
- **Business Value**: Enable true test-driven development workflow

**🔄 REMAINING FAILING TESTS (8 of 107):**

**CRITICAL PRIORITY - Test Infrastructure Issues**
- [ ] **Fix install.bats setup failures** (Tests 52-53)
  - Issue: `create_symlinks function creates proper symlinks` and cleanup tests fail in setup phase
  - Problem: cd command failures in test setup function  
  - Status: High priority - affects core installation testing

**MEDIUM PRIORITY - Platform-Specific Tests** (Tests 61, 63, 85-88)
- [ ] **Fix macOS homebrew tests**
  - Tests: `macos.sh installs homebrew if not present`, `macos.sh configures system defaults`
  - Issue: Mock expectations don't match actual implementation behavior
  
- [ ] **Fix streamlined mocking tests**
  - Tests: `OS detection with streamlined mocking`, `complex workflow with streamlined setup`, `mocking external commands works reliably`
  - Issue: External command mocks not sourcing properly in some test environments
  - Fix: Improve BASH_ENV sourcing and mock isolation

**LOW PRIORITY - Edge Cases** (Test 28)
- [ ] **Fix interrupted operations test**
  - Test: `dotfiles management handles interrupted operations`
  - Issue: Test expects status 0 but unclear what the expected behavior should be
  - Status: Needs analysis of intended behavior

### Recent Achievements ✅

**2025-07-24 - Major Progress: 99/107 Tests Passing (93%)**

**COMPLETED MAJOR FUNCTIONALITY:**
- ✅ **Fixed dotfiles-status command completely** (6+ tests)
  - Resolved hanging issues with associative array syntax
  - Added test-aware path resolution for /tmp environments  
  - Fixed exit code logic for --fix mode
  - Added --yes flag support for automation
  - Implemented symlink detection and repair functionality

- ✅ **Cross-platform path resolution** (5+ tests)
  - Added get_home_dir() function to dotfiles-add.sh, dotfiles-migrate.sh, dotfiles-status.sh
  - Fixed path normalization to preserve directory structure
  - Resolved test environment detection across all management scripts
  - Fixed dotfiles-migrate symlink detection in test environments

- ✅ **Security and validation improvements** (3+ tests)
  - Added validate_manifest_entry() function for corrupted file detection
  - Implemented path traversal prevention in dotfiles-add.sh
  - Added binary data detection and graceful error handling
  - Updated tests with case-insensitive error message matching

- ✅ **Error handling and edge cases** (4+ tests)
  - Fixed permission denied scenarios with realistic test setup
  - Added unsupported OS detection with proper OSTYPE mocking
  - Fixed symlink validation and broken link cleanup
  - Corrected test expectations for various error scenarios

### Development Recovery Information

**CURRENT STATUS: 99/107 tests passing (93% pass rate)**

**If Power Outage/Session Lost - RESTART COMMANDS:**
1. **Check Current Test Status**: `make test 2>&1 | grep -E "^not ok" | wc -l` (should show 8)
2. **List Remaining Failing Tests**: `make test 2>&1 | grep -E "^not ok" | head -8`
3. **Expected Failing Tests**:
   - not ok 28 dotfiles management handles interrupted operations
   - not ok 52 create_symlinks function creates proper symlinks  
   - not ok 53 create_symlinks function cleans up orphaned symlinks
   - not ok 61 macos.sh installs homebrew if not present
   - not ok 63 macos.sh configures system defaults
   - not ok 85 OS detection with streamlined mocking
   - not ok 86 complex workflow with streamlined setup
   - not ok 88 mocking external commands works reliably

**NEXT STEPS TO REACH 100%:**
1. **Priority 1**: Fix install.bats setup issues (tests 52-53) - affects core functionality
2. **Priority 2**: Fix macOS and mocking tests (tests 61, 63, 85-88) - platform compatibility
3. **Priority 3**: Analyze interrupted operations test (test 28) - edge case

**Key Development Commands:**
```bash
# Test specific failing functionality (PRIORITY ORDER)
bats test/install.bats -f "create_symlinks function creates proper symlinks"
bats test/install.bats -f "create_symlinks function cleans up orphaned symlinks"
bats test/platform_scripts.bats -f "macos.sh installs homebrew if not present"
bats test/error_scenarios.bats -f "dotfiles management handles interrupted operations"

# Quick test status check
make test 2>&1 | grep -E "^not ok" | wc -l  # Should show 8

# Commit progress (use descriptive messages)
git add . && git commit -m "Fix [specific issue]: [what was fixed]"
```

**KNOWN ISSUES AND SOLUTIONS:**
- **install.bats setup failures**: cd command failing in setup function, possibly due to directory timing issues
- **macOS test expectations**: Tests expect different homebrew behavior than actually implemented  
- **Mock environment isolation**: BASH_ENV sourcing not working properly in some test contexts
- **Test directory structure**: Some tests assume different working directory setups

**Current Architecture Understanding:**
- **Core Issue**: Test environments use different HOME paths than production
- **Solution Pattern**: Smart path detection functions that work in both environments  
- **Test Strategy**: Fix core functionality first, then test infrastructure, then edge cases

**Development Philosophy:**
- **Test-Driven Development**: Write tests first, make them pass, refactor
- **100% Test Passing Goal**: No exceptions - all tests must pass before features are complete
- **Cross-Platform First**: Every feature must work on all supported platforms from day one
- **Incremental Progress**: Fix one test at a time, commit frequently with clear messages
- **Recovery-Ready**: Always maintain state in CLAUDE.md for session continuity

**Quick Recovery Commands:**
```bash
# Check development status
./dev-status.sh

# Work on next high priority item  
bats test/dotfiles_management.bats -f "dotfiles-status detects missing symlinks"

# Update progress in CLAUDE.md when significant milestone reached
```

## Known Issues & TODOs (Historical)
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

### Cross-Platform Feature Parity Requirements
**CRITICAL: All features must be implemented across ALL supported platforms**

**Root Cause of Past Issues:**
- `github_releases` was added to packages.yml for both Ubuntu and macOS
- Implementation was only added to `scripts/ubuntu.sh`, not `scripts/macos.sh`
- Testing didn't catch this cross-platform gap
- Result: nvim installation failed silently on macOS

**MANDATORY Development Process:**
1. **Feature Definition**: When adding features to `packages.yml`, they MUST work on all platforms
2. **Implementation Requirement**: If a feature is added to packages.yml for multiple platforms, it MUST be implemented in ALL corresponding platform scripts
3. **Test-First Development**: Write tests that verify feature works on ALL platforms BEFORE considering implementation complete
4. **Cross-Platform Validation**: Use integration tests to validate actual functionality on each platform

**Current Supported Platforms:** 
- macOS (`scripts/macos.sh`)
- Ubuntu (`scripts/ubuntu.sh`)

**Testing Requirements for New Features:**
- Unit tests must verify parsing works for ALL platforms 
- Integration tests must validate installation succeeds on ALL platforms
- Feature parity tests must ensure identical functionality across platforms
- Tests MUST fail if a feature is defined in packages.yml but not implemented in platform scripts

**Example Failure Pattern to Avoid:**
```yaml
# In packages.yml - defined for both platforms
macos:
  github_releases: [...] 
ubuntu:
  github_releases: [...]
```
```bash
# In scripts/ubuntu.sh - implemented ✅
process_github_releases() { ... }

# In scripts/macos.sh - missing ❌ 
# No process_github_releases() function
```

**Required Implementation Pattern:**
- If packages.yml defines a section for multiple platforms → ALL platform scripts must implement it
- If packages.yml adds a new installation method → ALL platforms must support it  
- If packages.yml references a function → ALL platform scripts must have that function

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

### Comprehensive Testing Strategy

**PHILOSOPHY: Test-Driven Development (TDD)**
Write tests FIRST, then implement features. Tests are the specification - they define what the code should do before the code exists.

#### **Three-Layer Testing Architecture**

**1. Unit Tests (83 tests) - `make test`**
- **Framework**: Bats (Bash Automated Testing System)
- **Purpose**: Test individual functions and script logic in isolation
- **Speed**: Fast (~30 seconds)
- **Coverage**: 
  - Cross-platform feature parity (`test/cross_platform_parity.bats`) - 5 tests
  - Dotfiles management system (`test/dotfiles_management.bats`) - 14 tests  
  - File structure validation (`test/file_structure.bats`) - 12 tests
  - Installation logic (`test/install.bats`) - 10 tests
  - Platform-specific scripts (`test/platform_scripts.bats`) - 24 tests
  - Sync functionality (`test/update.bats`) - 17 tests
  - Homebrew integration (`test/homebrew_apps.bats`) - 1 test

**2. Integration Tests - `make integration-test`**
- **Framework**: Podman containers with real OS environments
- **Purpose**: Test complete installation workflows end-to-end
- **Speed**: Slow (~5-10 minutes)
- **Environments**:
  - `ubuntu`: Full Ubuntu 22.04 environment
  - `ubuntu-minimal`: Minimal Ubuntu 20.04 environment  
  - `macos-sim`: macOS simulation (Ubuntu with macOS-like setup)
  - `alpine`: Unsupported OS testing (expected failures)
- **Validation**: 24+ checks in `integration-tests/validate.sh`

**3. Cross-Platform Feature Parity Tests**
- **Special Focus**: Prevents the nvim-on-macOS type failures
- **Location**: `test/cross_platform_parity.bats`
- **Purpose**: Ensure features defined in `packages.yml` work on ALL platforms
- **Tests**:
  - `github_releases` implementation parity across platforms
  - `custom_install` function availability 
  - Platform-specific asset pattern validation
  - Function existence verification
  - Main function call verification

#### **Testing Requirements by Change Type**

**When Adding New Features:**
1. **Write failing tests first** (TDD approach)
2. **Unit tests**: Test parsing, logic, error handling
3. **Cross-platform tests**: Ensure works on ALL supported platforms
4. **Integration tests**: Add validation checks to `validate.sh`
5. **Run full test suite**: Both unit and integration tests must pass

**When Modifying Existing Code:**
1. **Update existing tests** to match new behavior
2. **Add regression tests** for bugs being fixed
3. **Ensure cross-platform compatibility** if touching platform scripts
4. **Run tests before AND after changes**

**When Adding New Platforms:**
1. **Update cross-platform tests** to include new platform
2. **Add new integration test environment** 
3. **Ensure all existing features work** on new platform
4. **Update documentation** with new platform support

#### **Test Categories and Their Focus**

**Structural Tests** (`file_structure.bats`):
- File existence and permissions
- Script syntax validation  
- Configuration file format validation
- Directory structure verification

**Functional Tests** (`install.bats`, `platform_scripts.bats`):
- OS detection logic
- Package installation workflows
- Git configuration substitution
- Symlink creation and management

**Integration Tests** (`dotfiles_management.bats`):
- Complete user workflows
- Multi-step operations
- Error recovery scenarios
- Backup and restore functionality

**Parity Tests** (`cross_platform_parity.bats`):
- Cross-platform feature consistency
- Implementation gap detection
- Asset pattern validation
- Function existence verification

#### **Testing Best Practices**

**Test Structure:**
```bash
@test "descriptive test name explains what should happen" {
    # Arrange: Set up test conditions
    setup_test_environment
    
    # Act: Execute the code being tested
    run command_under_test
    
    # Assert: Verify expected outcomes
    [ "$status" -eq 0 ]
    [[ "$output" == *"expected string"* ]]
}
```

**Mocking Strategy:**
- Mock external commands (brew, apt, curl) to avoid system changes
- Use temporary directories for file operations
- Stub environment variables and functions
- Simulate different OS environments in unit tests

**Error Testing:**
- Test both success and failure scenarios
- Verify proper error messages and exit codes
- Test edge cases and boundary conditions
- Ensure graceful degradation when dependencies missing

#### **Continuous Testing Workflow**

**Development Cycle:**
1. **Write failing test** that describes desired behavior
2. **Run test to confirm it fails** (red phase)
3. **Write minimal code** to make test pass (green phase)  
4. **Refactor code** while keeping tests passing (refactor phase)
5. **Run full test suite** to ensure no regressions
6. **Commit only when all tests pass**

**Before Each Commit:**
```bash
# MANDATORY: Must pass before committing
make test

# RECOMMENDED: Run when touching installation logic  
make integration-test-ubuntu

# REQUIRED: When adding cross-platform features
./integration-tests/verify-setup.sh
```

#### **Integration Test Architecture**

**Container-Based Testing:**
- **Real OS environments**: Not simulated, actual Ubuntu/Alpine containers
- **Complete installation**: Full `dotfiles-install.sh` execution
- **Post-installation validation**: Comprehensive checks via `validate.sh`
- **Cleanup**: Automatic container removal after tests

**Validation Categories:**
- Symlink creation and target verification
- Package installation verification  
- Service configuration validation
- Git configuration substitution
- Shell configuration verification
- Cross-platform compatibility checks

#### **Test Maintenance Guidelines**

**When Tests Fail:**
- **Don't ignore failing tests** - they indicate real problems
- **Fix the root cause**, don't just update the test
- **Add regression tests** for newly discovered issues
- **Update test expectations** only when behavior intentionally changes

**Test Quality Standards:**
- **Descriptive names**: Tests should read like specifications
- **Single responsibility**: One test per behavior
- **Deterministic**: Tests should pass/fail consistently  
- **Fast feedback**: Unit tests should run in under 60 seconds
- **Independent**: Tests shouldn't depend on each other

**Current Test Status:**
- **Unit tests**: 83 tests, ~68% passing (some expected failures in development)
- **Integration tests**: 4 environments, 24+ validation checks
- **Cross-platform tests**: 5 tests, 100% passing (new)
- **Total coverage**: ~1300 lines of test code, growing with TDD approach

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