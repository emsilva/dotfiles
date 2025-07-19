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
    "alpine:Dockerfile.alpine:Alpine Linux (Unsupported OS) Test"
)

# Function to run a single integration test
run_integration_test() {
    local test_name="$1"
    local dockerfile="$2"
    local description="$3"
    
    print_section "$description"
    
    # Build the Docker image
    print_info "Building Docker image for $test_name..."
    if ! docker build -f "integration-tests/$dockerfile" -t "dotfiles-test-$test_name" .; then
        print_error "Failed to build Docker image for $test_name"
        return 1
    fi
    
    # Run the test
    print_info "Running integration test for $test_name..."
    local container_id
    container_id=$(docker run -d "dotfiles-test-$test_name")
    
    # Wait for container to finish and get the exit code
    local exit_code
    docker wait "$container_id" > /dev/null
    exit_code=$(docker inspect "$container_id" --format='{{.State.ExitCode}}')
    
    # Get the logs
    print_info "Container output for $test_name:"
    docker logs "$container_id"
    
    # Check exit code and report result
    if [ "$exit_code" -eq 0 ]; then
        print_info "✅ $description: PASSED"
    else
        print_error "❌ $description: FAILED (exit code: $exit_code)"
        
        # For debugging, let's also check what files were created
        print_info "Checking container filesystem for debugging..."
        docker exec "$container_id" ls -la /home/testuser/ || true
        docker exec "$container_id" ls -la /home/testuser/.config/ || true
    fi
    
    # Clean up container
    docker rm "$container_id" > /dev/null
    
    return "$exit_code"
}

# Function to run post-installation validation
validate_installation() {
    local test_name="$1"
    local dockerfile="$2"
    
    print_info "Running post-installation validation for $test_name..."
    
    # Create a new container from the image and run validation commands
    local container_id
    container_id=$(docker run -d "dotfiles-test-$test_name" sleep 3600)
    
    # Check that symlinks were created
    print_info "Validating symlinks..."
    docker exec "$container_id" bash -c "
        ls -la /home/testuser/.vimrc && echo '✅ .vimrc symlink created' || echo '❌ .vimrc symlink missing'
        ls -la /home/testuser/.zshrc && echo '✅ .zshrc symlink created' || echo '❌ .zshrc symlink missing'
        ls -la /home/testuser/.gitconfig && echo '✅ .gitconfig symlink created' || echo '❌ .gitconfig symlink missing'
    "
    
    # Check that git config was properly substituted
    print_info "Validating git configuration..."
    docker exec "$container_id" bash -c "
        grep 'test.personal@example.com' /home/testuser/.gitconfig && echo '✅ Personal email substituted' || echo '❌ Personal email not found'
        grep 'test.work@example.com' /home/testuser/.gitconfig-work && echo '✅ Work email substituted' || echo '❌ Work email not found'
    "
    
    # Check that directories were created
    print_info "Validating directories..."
    docker exec "$container_id" bash -c "
        [ -d /home/testuser/org ] && echo '✅ org directory created' || echo '❌ org directory missing'
        [ -d /home/testuser/code/work ] && echo '✅ code/work directory created' || echo '❌ code/work directory missing'
    "
    
    # Clean up
    docker rm -f "$container_id" > /dev/null
}

# Main test runner
main() {
    print_section "Dotfiles Integration Test Suite"
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running"
        exit 1
    fi
    
    local failed_tests=0
    local total_tests=${#TESTS[@]}
    
    # Run each test
    for test_config in "${TESTS[@]}"; do
        IFS=':' read -r test_name dockerfile description <<< "$test_config"
        
        if run_integration_test "$test_name" "$dockerfile" "$description"; then
            # For successful tests (except Alpine which should fail), run validation
            if [ "$test_name" != "alpine" ]; then
                validate_installation "$test_name" "$dockerfile"
            fi
        else
            # Alpine test should fail gracefully
            if [ "$test_name" = "alpine" ]; then
                print_info "✅ Alpine test failed as expected (unsupported OS)"
            else
                ((failed_tests++))
            fi
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
    print_info "Cleaning up Docker images..."
    docker rmi -f $(docker images "dotfiles-test-*" -q) 2>/dev/null || true
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
        echo "  clean: Remove all test Docker images"
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