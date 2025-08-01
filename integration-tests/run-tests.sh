#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_section() { echo -e "${BLUE}=== $1 ===${NC}"; }

# Test configurations
TESTS=(
    "ubuntu:Dockerfile.ubuntu:Ubuntu 22.04 Full Test"
    "ubuntu-minimal:Dockerfile.ubuntu-minimal:Ubuntu 20.04 Minimal Test"
    "macos-sim:Dockerfile.macos-sim:macOS Simulation Test"
)

# Function to run a single integration test
run_integration_test() {
    local test_name="$1"
    local dockerfile="$2"
    local description="$3"
    
    print_section "$description"
    
    # Build the Podman image
    print_info "Building Podman image for $test_name..."
    if ! podman build -f "integration-tests/$dockerfile" -t "dotfiles-test-$test_name" .; then
        print_error "Failed to build Podman image for $test_name"
        return 1
    fi
    
    # Run the test
    print_info "Running integration test for $test_name..."
    local container_id
    container_id=$(podman run -d "dotfiles-test-$test_name")
    
    # Wait for container to finish and get the exit code
    local exit_code
    podman wait "$container_id" > /dev/null
    exit_code=$(podman inspect "$container_id" --format='{{.State.ExitCode}}')
    
    # Get the logs
    print_info "Container output for $test_name:"
    podman logs "$container_id"
    
    # Check exit code and report result
    if [ "$exit_code" -eq 0 ]; then
        print_info "✅ $description: PASSED"
    else
        print_error "❌ $description: FAILED (exit code: $exit_code)"
        
        # For debugging, let's also check what files were created
        print_info "Checking container filesystem for debugging..."
        podman exec "$container_id" ls -la /home/testuser/ || true
        podman exec "$container_id" ls -la /home/testuser/.config/ || true
    fi
    
    # Clean up container
    podman rm "$container_id" > /dev/null
    
    return "$exit_code"
}

# Function to run post-installation validation
validate_installation() {
    local test_name="$1"
    local dockerfile="$2"
    
    print_info "Running post-installation validation for $test_name..."
    
    # Create a new container from the image and run validation commands
    local container_id
    container_id=$(podman run -d "dotfiles-test-$test_name" sleep 3600)
    
    # Check that symlinks were created
    print_info "Validating symlinks..."
    podman exec "$container_id" bash -c "
        ls -la /home/testuser/.vimrc && echo '✅ .vimrc symlink created' || echo '❌ .vimrc symlink missing'
        ls -la /home/testuser/.zshrc && echo '✅ .zshrc symlink created' || echo '❌ .zshrc symlink missing'
        ls -la /home/testuser/.gitconfig && echo '✅ .gitconfig symlink created' || echo '❌ .gitconfig symlink missing'
    "
    
    # Check that git config was properly substituted
    print_info "Validating git configuration..."
    podman exec "$container_id" bash -c "
        grep 'test.personal@example.com' /home/testuser/.gitconfig && echo '✅ Personal email substituted' || echo '❌ Personal email not found'
        grep 'test.work@example.com' /home/testuser/.gitconfig-work && echo '✅ Work email substituted' || echo '❌ Work email not found'
    "
    
    # Check that directories were created
    print_info "Validating directories..."
    podman exec "$container_id" bash -c "
        [ -d /home/testuser/org ] && echo '✅ org directory created' || echo '❌ org directory missing'
        [ -d /home/testuser/code/work ] && echo '✅ code/work directory created' || echo '❌ code/work directory missing'
    "
    
    # Clean up
    podman rm -f "$container_id" > /dev/null
}

# Main test runner
main() {
    print_section "Dotfiles Integration Test Suite"
    
    # Check if Podman is available
    if ! command -v podman &> /dev/null; then
        print_error "Podman is not installed or not in PATH"
        exit 1
    fi
    
    # Check if Podman is running
    if ! podman info &> /dev/null; then
        print_error "Podman is not running or not configured properly"
        exit 1
    fi
    
    local failed_tests=0
    local total_tests=${#TESTS[@]}
    
    # Run each test
    for test_config in "${TESTS[@]}"; do
        IFS=':' read -r test_name dockerfile description <<< "$test_config"
        
        if run_integration_test "$test_name" "$dockerfile" "$description"; then
            validate_installation "$test_name" "$dockerfile"
        else
            ((failed_tests++))
        fi
        
        echo
    done
    
    # Summary
    print_section "Test Summary"
    local passed_tests=$((total_tests - failed_tests))
    print_info "Passed: $passed_tests/$total_tests"
    
    if [ $failed_tests -eq 0 ]; then
        print_info "🎉 All integration tests passed!"
        exit 0
    else
        print_error "💥 $failed_tests test(s) failed"
        exit 1
    fi
}

# Cleanup function
cleanup() {
    print_info "Cleaning up Podman images..."
    podman rmi -f $(podman images "dotfiles-test-*" -q) 2>/dev/null || true
}

# Set trap for cleanup
trap cleanup EXIT

# Parse command line arguments
case "${1:-}" in
    "clean")
        cleanup
        exit 0
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [clean|help]"
        echo "  clean: Remove all test Podman images"
        echo "  help:  Show this help message"
        exit 0
        ;;
    "")
        main "$@"
        ;;
    *)
        print_error "Unknown argument: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac