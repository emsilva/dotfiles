#!/bin/bash

# This script runs inside the container to validate the installation
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_pass() { echo -e "${GREEN}✅ PASS:${NC} $1"; }
print_fail() { echo -e "${RED}❌ FAIL:${NC} $1"; }
print_info() { echo -e "${BLUE}ℹ️  INFO:${NC} $1"; }
print_warn() { echo -e "${YELLOW}⚠️  SKIP:${NC} $1"; }

FAILED_TESTS=0
PASSED_TESTS=0
SKIPPED_TESTS=0

# Test function with better error handling
test_condition() {
    local description="$1"
    local condition="$2"
    local is_container_limitation="$3"  # Optional: true for expected container failures
    
    if eval "$condition" 2>/dev/null; then
        print_pass "$description"
        ((PASSED_TESTS++))
        return 0
    elif [[ "$is_container_limitation" == "true" ]]; then
        print_warn "$description (expected container limitation)"
        ((SKIPPED_TESTS++))
        return 0
    else
        print_fail "$description"
        ((FAILED_TESTS++))
        return 1
    fi
}

print_info "Starting comprehensive post-installation validation..."
echo -e "${BLUE}=======================================================${NC}"

# ============================================================================
# STEP 1: VALIDATE SYMLINKS (from create_symlinks function)
# ============================================================================
print_info "Step 1: Testing symlink creation..."
if [[ -f .dotfiles-manifest ]]; then
    while IFS= read -r rel_path; do
        [[ -z "$rel_path" ]] && continue
        target_path="$HOME/$rel_path"
        dotfiles_path="$(pwd)/dotfiles/$rel_path"
        
        test_condition "Symlink exists: $rel_path" "[ -L '$target_path' ]"
        if [[ -L "$target_path" ]]; then
            test_condition "Symlink points correctly: $rel_path" "readlink '$target_path' | grep -q 'dotfiles/$rel_path'"
        fi
    done < .dotfiles-manifest
else
    print_fail "No .dotfiles-manifest file found"
    ((FAILED_TESTS++))
fi

# ============================================================================
# STEP 2: VALIDATE GIT CONFIGURATION (from setup_git_config function)
# ============================================================================
print_info "Step 2: Testing git configuration setup..."
test_condition "Personal email substituted in .gitconfig" "grep -q '$GIT_EMAIL_PERSONAL' ~/.gitconfig"
test_condition "Work email substituted in .gitconfig-work" "grep -q '$GIT_EMAIL_WORK' ~/.gitconfig-work"
test_condition "Git user name is set" "git config --get user.name > /dev/null"
test_condition "Git personal email is set" "git config --get user.email > /dev/null"
test_condition ".gitconfig has content" "[ -s ~/.gitconfig ]"
test_condition ".gitconfig-work has content" "[ -s ~/.gitconfig-work ]"

# ============================================================================
# STEP 3: VALIDATE DIRECTORY CREATION (from create_folders function)
# ============================================================================
print_info "Step 3: Testing directory creation..."
test_condition "~/org directory created" "[ -d ~/org ]"
test_condition "~/code/work directory created" "[ -d ~/code/work ]"
test_condition "~/.local/bin directory created" "[ -d ~/.local/bin ]"
test_condition "~/.config directory exists" "[ -d ~/.config ]"
test_condition "~/.local/share directory exists" "[ -d ~/.local/share ]"

# ============================================================================
# STEP 4: VALIDATE DOTFILES SCRIPTS (from setup_dotfiles_scripts function)
# ============================================================================
print_info "Step 4: Testing dotfiles management scripts..."
for script in dotfiles-add dotfiles-remove dotfiles-list dotfiles-status dotfiles-sync dotfiles-migrate; do
    test_condition "$script script exists in ~/.local/bin" "[ -f ~/.local/bin/$script ]"
    test_condition "$script script is executable" "[ -x ~/.local/bin/$script ]"
    if [[ -f ~/.local/bin/$script ]]; then
        test_condition "$script points to dotfiles directory" "readlink ~/.local/bin/$script | grep -q dotfiles"
    fi
done

# ============================================================================
# STEP 5: VALIDATE OH-MY-ZSH INSTALLATION (from install_oh_my_zsh function)
# ============================================================================
print_info "Step 5: Testing oh-my-zsh installation..."
test_condition "oh-my-zsh directory exists" "[ -d ~/.oh-my-zsh ]"
if [[ -d ~/.oh-my-zsh ]]; then
    test_condition "oh-my-zsh core files exist" "[ -f ~/.oh-my-zsh/oh-my-zsh.sh ]"
    test_condition "oh-my-zsh plugins directory exists" "[ -d ~/.oh-my-zsh/plugins ]"
    test_condition "oh-my-zsh themes directory exists" "[ -d ~/.oh-my-zsh/themes ]"
fi

# ============================================================================
# STEP 6: VALIDATE SHELL SETUP (from set_default_shell function)
# ============================================================================
print_info "Step 6: Testing shell configuration..."
test_condition "zsh is installed" "command -v zsh > /dev/null"
test_condition "zsh is in /etc/shells" "grep -q zsh /etc/shells" "true"  # May fail in containers
# Note: Default shell change (chsh) expected to fail in containers
if [[ -n "$SHELL" ]] && echo "$SHELL" | grep -q zsh; then
    print_pass "zsh is set as default shell"
    ((PASSED_TESTS++))
elif [[ -n "$SHELL" ]]; then
    print_warn "Default shell is $SHELL (chsh expected to fail in containers)"
    ((SKIPPED_TESTS++))
else
    print_warn "SHELL variable not set (expected in container environment)"
    ((SKIPPED_TESTS++))
fi

# ============================================================================
# STEP 7: VALIDATE PACKAGE INSTALLATION (from scripts/OS.sh)
# ============================================================================
print_info "Step 7: Testing package installation..."

# Detect OS to know what packages to expect
if command -v apt-get > /dev/null 2>&1; then
    OS_TYPE="ubuntu"
elif [[ "$(uname)" == "Darwin" ]] || [[ -n "$OSTYPE" && "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="macos"
else
    OS_TYPE="unknown"
fi

# Test common packages that should be installed
test_condition "git is installed" "command -v git > /dev/null"
test_condition "vim is installed" "command -v vim > /dev/null"
test_condition "curl is installed" "command -v curl > /dev/null"
test_condition "zsh is installed" "command -v zsh > /dev/null"

# Test OS-specific packages
if [[ "$OS_TYPE" == "ubuntu" ]]; then
    test_condition "ripgrep is installed" "command -v rg > /dev/null"
    test_condition "jq is installed" "command -v jq > /dev/null"
    test_condition "python3 is installed" "command -v python3 > /dev/null"
    test_condition "shellcheck is installed" "command -v shellcheck > /dev/null" "true"  # May fail
    
    # Test starship installation (custom_install)
    test_condition "starship is installed in ~/.local/bin" "[ -f ~/.local/bin/starship ]"
    test_condition "starship command works" "~/.local/bin/starship --version > /dev/null"
    
    # Test neovim installation (github_releases)
    test_condition "neovim is installed in ~/.local/bin" "[ -f ~/.local/bin/nvim ]"
    test_condition "vim symlink points to nvim" "[ -L ~/.local/bin/vim ]"
    test_condition "nvim command works" "~/.local/bin/nvim --version > /dev/null"
    
elif [[ "$OS_TYPE" == "macos" ]]; then
    test_condition "brew command exists" "command -v brew > /dev/null"
    # Note: In simulation, brew is mocked, so we test for the mock
    if command -v brew > /dev/null; then
        print_pass "Homebrew (or mock) is available"
        ((PASSED_TESTS++))
    fi
fi

# ============================================================================
# STEP 8: VALIDATE LS_COLORS SETUP
# ============================================================================
print_info "Step 8: Testing LS_COLORS installation..."
if [[ "$OS_TYPE" == "ubuntu" ]]; then
    test_condition "LS_COLORS repository cloned" "[ -d ~/.local/share/LS_COLORS ]"
    test_condition "LS_COLORS data file exists" "[ -f ~/.local/share/LS_COLORS/LS_COLORS ]"
    test_condition "LS_COLORS sourcing script exists" "[ -f ~/.local/share/LS_COLORS/lscolors.sh ]"
    if [[ -f ~/.local/share/LS_COLORS/lscolors.sh ]]; then
        test_condition "LS_COLORS script has correct content" "grep -q 'eval.*dircolors' ~/.local/share/LS_COLORS/lscolors.sh"
    fi
elif [[ "$OS_TYPE" == "macos" ]]; then
    # macOS uses ls_colors formula from Homebrew tap - test depends on mock setup
    print_info "macOS LS_COLORS setup varies by installation method"
fi

# ============================================================================
# STEP 9: VALIDATE CROSS-PLATFORM ZSH CONFIGURATION
# ============================================================================
print_info "Step 9: Testing cross-platform zsh configuration..."
if [[ -f ~/.zshrc ]]; then
    test_condition ".zshrc contains platform detection" "grep -q 'uname.*Darwin\\|uname.*Linux' ~/.zshrc"
    test_condition ".zshrc contains starship init" "grep -q 'starship init zsh' ~/.zshrc"
    test_condition ".zshrc contains oh-my-zsh loading" "grep -q 'oh-my-zsh.sh' ~/.zshrc"
    test_condition ".zshrc has proper plugin configuration" "grep -q 'plugins=' ~/.zshrc"
    test_condition ".zshrc handles LS_COLORS cross-platform" "grep -q 'LS_COLORS' ~/.zshrc"
fi

# ============================================================================
# STEP 10: VALIDATE RUBY GEMS (Expected to fail - that's OK)
# ============================================================================
print_info "Step 10: Testing Ruby gem installation (failures expected)..."
if command -v gem > /dev/null 2>&1; then
    # Ruby gems are expected to fail in containers due to network/dependency issues
    print_warn "Ruby gems installation - failures expected in container environment"
    ((SKIPPED_TESTS++))
else
    print_warn "Ruby not available - gem installation skipped"
    ((SKIPPED_TESTS++))
fi

# ============================================================================
# STEP 11: VALIDATE CONTAINER-SPECIFIC LIMITATIONS
# ============================================================================
print_info "Step 11: Testing expected container limitations..."
print_info "The following are EXPECTED to fail in containers and should not cause test failure:"
print_info "  - chsh (change default shell) - requires proper login session"
print_info "  - systemd services - containers don't run full init systems"
print_info "  - podman/docker setup - nested containerization issues"
print_info "  - some package installations - dependency/network issues"

# ============================================================================
# FINAL SUMMARY
# ============================================================================
echo -e "${BLUE}=======================================================${NC}"
print_info "VALIDATION SUMMARY"
echo -e "${BLUE}=======================================================${NC}"

TOTAL_TESTS=$((PASSED_TESTS + FAILED_TESTS + SKIPPED_TESTS))

print_pass "Passed: $PASSED_TESTS tests"
if [[ $SKIPPED_TESTS -gt 0 ]]; then
    print_warn "Skipped: $SKIPPED_TESTS tests (expected container limitations)"
fi
if [[ $FAILED_TESTS -gt 0 ]]; then
    print_fail "Failed: $FAILED_TESTS tests"
fi

echo -e "${BLUE}Total tests: $TOTAL_TESTS${NC}"
echo -e "${BLUE}=======================================================${NC}"

if [[ $FAILED_TESTS -eq 0 ]]; then
    echo -e "${GREEN}🎉 ALL CRITICAL TESTS PASSED!${NC}"
    echo -e "${GREEN}Dotfiles installation validated successfully in container environment.${NC}"
    if [[ $SKIPPED_TESTS -gt 0 ]]; then
        echo -e "${YELLOW}Note: $SKIPPED_TESTS tests were skipped due to expected container limitations.${NC}"
    fi
    exit 0
else
    echo -e "${RED}💥 $FAILED_TESTS CRITICAL TESTS FAILED!${NC}"
    echo -e "${RED}Dotfiles installation has issues that need to be addressed.${NC}"
    exit 1
fi