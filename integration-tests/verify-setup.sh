#!/bin/bash

# Verify integration test setup without requiring Podman
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
print_warn() { echo -e "${YELLOW}⚠️  WARN:${NC} $1"; }

FAILED_CHECKS=0

check() {
    local description="$1"
    local condition="$2"
    
    if eval "$condition"; then
        print_pass "$description"
        return 0
    else
        print_fail "$description"
        ((FAILED_CHECKS++))
        return 1
    fi
}

print_info "Verifying integration test setup..."

# Check required files exist
print_info "Checking required files..."
check "Dockerfile.ubuntu exists" "[ -f integration-tests/Dockerfile.ubuntu ]"
check "Dockerfile.ubuntu-minimal exists" "[ -f integration-tests/Dockerfile.ubuntu-minimal ]"
check "Dockerfile.macos-sim exists" "[ -f integration-tests/Dockerfile.macos-sim ]"
check "run-tests.sh exists and is executable" "[ -x integration-tests/run-tests.sh ]"
check "validate.sh exists and is executable" "[ -x integration-tests/validate.sh ]"
check ".containerignore exists" "[ -f .containerignore ]"

# Check main dotfiles structure
print_info "Checking dotfiles structure..."
check "install.sh exists and is executable" "[ -x install.sh ]"
check "packages.yml exists" "[ -f packages.yml ]"
check "scripts/macos.sh exists and is executable" "[ -x scripts/macos.sh ]"
check "scripts/ubuntu.sh exists and is executable" "[ -x scripts/ubuntu.sh ]"
check "dotfiles directory exists" "[ -d dotfiles ]"
check "dotfiles/.gitconfig exists" "[ -f dotfiles/.gitconfig ]"
check "dotfiles/.gitconfig-work exists" "[ -f dotfiles/.gitconfig-work ]"

# Check Dockerfile syntax
print_info "Validating Dockerfile syntax..."
for dockerfile in integration-tests/Dockerfile.*; do
    filename=$(basename "$dockerfile")
    if command -v podman &> /dev/null; then
        # Use basic syntax validation since --dry-run is not available in Podman
        if grep -q "FROM" "$dockerfile" && grep -q "CMD" "$dockerfile"; then
            print_pass "$filename has basic Dockerfile structure"
        else
            print_fail "$filename missing required Dockerfile commands"
            ((FAILED_CHECKS++))
        fi
    else
        # Basic syntax check without Podman
        if grep -q "FROM" "$dockerfile" && grep -q "CMD" "$dockerfile"; then
            print_pass "$filename has basic Dockerfile structure"
        else
            print_fail "$filename missing basic Dockerfile structure"
            ((FAILED_CHECKS++))
        fi
    fi
done

# Check script syntax
print_info "Validating script syntax..."
check "run-tests.sh syntax is valid" "bash -n integration-tests/run-tests.sh"
check "validate.sh syntax is valid" "bash -n integration-tests/validate.sh"
check "install.sh syntax is valid" "bash -n install.sh"
check "scripts/macos.sh syntax is valid" "bash -n scripts/macos.sh"
check "scripts/ubuntu.sh syntax is valid" "bash -n scripts/ubuntu.sh"

# Check Makefile targets
print_info "Validating Makefile..."
check "Makefile has integration-test target" "grep -q '^integration-test:' Makefile"
check "Makefile has integration-test-ubuntu target" "grep -q '^integration-test-ubuntu:' Makefile"
check "Makefile has integration-test-clean target" "grep -q '^integration-test-clean:' Makefile"

# Check environment dependencies
print_info "Checking environment..."
if command -v podman &> /dev/null; then
    print_pass "Podman is installed"
    if podman info &> /dev/null 2>&1; then
        print_pass "Podman is running and configured"
        print_info "Ready to run: make integration-test"
    else
        print_warn "Podman is not configured properly (run: podman machine init && podman machine start)"
    fi
else
    print_warn "Podman not installed - integration tests will not work"
    print_info "Install Podman to run integration tests"
fi

# Check if unit tests pass
print_info "Verifying unit tests..."
if command -v bats &> /dev/null; then
    if make test &> /dev/null; then
        print_pass "Unit tests pass"
    else
        print_fail "Unit tests are failing"
        ((FAILED_CHECKS++))
    fi
else
    print_warn "Bats not available - cannot verify unit tests"
fi

# Summary
print_info "Verification Summary"
TOTAL_CHECKS=20
PASSED_CHECKS=$((TOTAL_CHECKS - FAILED_CHECKS))

echo
if [ $FAILED_CHECKS -eq 0 ]; then
    print_pass "Integration test setup is complete! ($PASSED_CHECKS checks passed)"
    echo
    print_info "Next steps:"
    echo "  1. Ensure Podman is configured: podman machine init && podman machine start"
    echo "  2. Run integration tests: make integration-test"
    echo "  3. Or run individual tests: make integration-test-ubuntu"
    exit 0
else
    print_fail "Setup has issues ($FAILED_CHECKS checks failed)"
    echo
    print_info "Fix the issues above and run this script again"
    exit 1
fi