#!/usr/bin/env bash

# Test helpers to improve test independence and reduce mocking complexity
# This standardizes common test patterns across all test files

# Standardized test setup - creates isolated environment
setup_isolated_test_env() {
    local test_name="$1"
    export TEST_TEMP_DIR="$BATS_TEST_TMPDIR/${test_name}_$$"
    export TEST_HOME="$TEST_TEMP_DIR/home"
    export TEST_DOTFILES="$TEST_TEMP_DIR/dotfiles"
    
    # Create clean directory structure
    mkdir -p "$TEST_HOME" "$TEST_DOTFILES"
    
    # Copy necessary scripts to test directory
    cp "$BATS_TEST_DIRNAME/../dotfiles-add.sh" "$TEST_DOTFILES/" 2>/dev/null || true
    cp "$BATS_TEST_DIRNAME/../dotfiles-remove.sh" "$TEST_DOTFILES/" 2>/dev/null || true
    cp "$BATS_TEST_DIRNAME/../dotfiles-status.sh" "$TEST_DOTFILES/" 2>/dev/null || true
    cp "$BATS_TEST_DIRNAME/../dotfiles-list.sh" "$TEST_DOTFILES/" 2>/dev/null || true
    cp "$BATS_TEST_DIRNAME/../dotfiles-install.sh" "$TEST_DOTFILES/" 2>/dev/null || true
    cp "$BATS_TEST_DIRNAME/../packages.yml" "$TEST_DOTFILES/" 2>/dev/null || true
    cp -r "$BATS_TEST_DIRNAME/../scripts" "$TEST_DOTFILES/" 2>/dev/null || true
    cp -r "$BATS_TEST_DIRNAME/../dotfiles" "$TEST_DOTFILES/" 2>/dev/null || true
    
    # Create empty manifest
    touch "$TEST_DOTFILES/.dotfiles-manifest"
    
    # Change to test directory
    cd "$TEST_DOTFILES"
}

# Standardized cleanup
cleanup_test_env() {
    rm -rf "$TEST_TEMP_DIR" 2>/dev/null || true
}

# Create standard mock environment for external commands
setup_standard_mocks() {
    export BASH_ENV="$TEST_TEMP_DIR/mock_env.sh"
    cat <<'EOF' > "$BASH_ENV"
# Standard mocks for external commands
brew() { echo "brew $@" >> "$TEST_TEMP_DIR/brew.log"; return 0; }
apt() { echo "apt $@" >> "$TEST_TEMP_DIR/apt.log"; return 0; }
apt-get() { echo "apt-get $@" >> "$TEST_TEMP_DIR/apt.log"; return 0; }
sudo() { 
    shift
    echo "sudo $@" >> "$TEST_TEMP_DIR/sudo.log"
    "$@"
}
curl() { 
    # Simple curl mock that creates expected files
    local url="$2"
    local output="$4"
    echo "curl $@" >> "$TEST_TEMP_DIR/curl.log"
    
    # Mock different responses based on URL patterns
    if [[ "$url" == *"github.com/repos"* && "$url" == *"/releases/latest"* ]]; then
        echo '{"tag_name": "v1.0.0", "assets": [{"browser_download_url": "https://github.com/test/test/releases/download/v1.0.0/test.tar.gz"}]}' > "$output"
    elif [[ "$url" == *".tar.gz" ]]; then
        # Create a fake tarball
        mkdir -p "$TEST_TEMP_DIR/fake_extract/bin"
        echo '#!/bin/bash\necho "fake binary"' > "$TEST_TEMP_DIR/fake_extract/bin/test"
        chmod +x "$TEST_TEMP_DIR/fake_extract/bin/test"
        tar -czf "$output" -C "$TEST_TEMP_DIR/fake_extract" .
    else
        echo "mock response" > "$output"
    fi
    return 0
}
git() { echo "git $@" >> "$TEST_TEMP_DIR/git.log"; return 0; }
systemctl() { echo "systemctl $@" >> "$TEST_TEMP_DIR/systemctl.log"; return 0; }
chsh() { echo "chsh $@" >> "$TEST_TEMP_DIR/chsh.log"; return 0; }
gem() { echo "gem $@" >> "$TEST_TEMP_DIR/gem.log"; return 0; }
npm() { echo "npm $@" >> "$TEST_TEMP_DIR/npm.log"; return 0; }
tar() {
    # Smart tar mock that can extract our fake tarballs
    if [[ "$1" == "-xzf" ]]; then
        local tarball="$2"
        local dest_dir="$4"
        if [[ "$tarball" == *"fake"* ]]; then
            # Extract our fake tarball
            /usr/bin/tar "$@"
        else
            # Create fake extracted content
            mkdir -p "$dest_dir/bin"
            echo '#!/bin/bash\necho "extracted binary"' > "$dest_dir/bin/extracted"
            chmod +x "$dest_dir/bin/extracted"
        fi
        return 0
    else
        /usr/bin/tar "$@"
    fi
}
EOF
}

# Create a test file with specified content and path
create_test_file() {
    local path="$1"
    local content="${2:-test content}"
    
    mkdir -p "$(dirname "$path")"
    echo "$content" > "$path"
}

# Create a test manifest with specified entries
create_test_manifest() {
    local manifest_file="$TEST_DOTFILES/.dotfiles-manifest"
    
    # Clear existing manifest
    > "$manifest_file"
    
    # Add each entry
    for entry in "$@"; do
        echo "$entry" >> "$manifest_file"
    done
    
    # Sort manifest
    sort "$manifest_file" -o "$manifest_file"
}

# Assert that a file exists and is a symlink
assert_symlink_exists() {
    local path="$1"
    local expected_target="$2"
    
    [ -L "$path" ] || {
        echo "Expected symlink not found: $path"
        return 1
    }
    
    if [[ -n "$expected_target" ]]; then
        local actual_target
        actual_target=$(readlink "$path")
        [[ "$actual_target" == "$expected_target" ]] || {
            echo "Symlink target mismatch. Expected: $expected_target, Actual: $actual_target"
            return 1
        }
    fi
}

# Assert that manifest contains specific entry
assert_manifest_contains() {
    local entry="$1"
    local manifest_file="$TEST_DOTFILES/.dotfiles-manifest"
    
    [ -f "$manifest_file" ] || {
        echo "Manifest file not found: $manifest_file"
        return 1
    }
    
    grep -q "^$entry$" "$manifest_file" || {
        echo "Manifest does not contain: $entry"
        echo "Manifest contents:"
        cat "$manifest_file"
        return 1
    }
}

# Mock OS detection
mock_os() {
    local os_name="$1"
    export BASH_ENV="$TEST_TEMP_DIR/os_mock.sh"
    cat <<EOF > "$BASH_ENV"
uname() {
    if [[ "\$1" == "-s" ]]; then
        echo "$os_name"
    else
        /usr/bin/uname "\$@"
    fi
}
EOF
}

# Assert that command output contains expected string
assert_output_contains() {
    local expected="$1"
    local actual="$output"
    
    [[ "$actual" == *"$expected"* ]] || {
        echo "Output does not contain expected string: $expected"
        echo "Actual output: $actual"
        return 1
    }
}

# Assert that command failed with expected status
assert_failure() {
    local expected_status="${1:-1}"
    
    [ "$status" -eq "$expected_status" ] || {
        echo "Expected status $expected_status, got $status"
        echo "Output: $output"
        return 1
    }
}

# Assert that command succeeded
assert_success() {
    [ "$status" -eq 0 ] || {
        echo "Expected success (status 0), got $status"
        echo "Output: $output"
        return 1
    }
}

# Run command with timeout (for preventing hangs)
run_with_timeout() {
    local timeout_seconds="${1:-30}"
    shift
    
    timeout "$timeout_seconds" "$@"
}

# Create a standardized test dotfiles structure
setup_standard_dotfiles() {
    mkdir -p "$TEST_DOTFILES/dotfiles/.config"
    
    # Create standard dotfiles
    echo "# Test vimrc" > "$TEST_DOTFILES/dotfiles/.vimrc"
    echo "# Test zshrc" > "$TEST_DOTFILES/dotfiles/.zshrc"
    echo "[user]" > "$TEST_DOTFILES/dotfiles/.gitconfig"
    echo "    name = Test User" >> "$TEST_DOTFILES/dotfiles/.gitconfig"
    echo "# Test config" > "$TEST_DOTFILES/dotfiles/.config/test.conf"
    
    # Create corresponding manifest
    create_test_manifest ".vimrc" ".zshrc" ".gitconfig" ".config/test.conf"
}

# Verify that no external commands were actually executed
verify_no_system_changes() {
    # Check that no real system modification logs exist
    [[ ! -f "/tmp/brew.log" ]] || {
        echo "Real brew commands may have been executed"
        return 1
    }
    
    # Add other verification as needed
    return 0
}

# Print debug information about test state
debug_test_state() {
    echo "=== TEST DEBUG INFO ==="
    echo "TEST_TEMP_DIR: $TEST_TEMP_DIR"
    echo "TEST_HOME: $TEST_HOME"
    echo "TEST_DOTFILES: $TEST_DOTFILES"
    echo "Current directory: $(pwd)"
    echo "Home directory contents:" 
    ls -la "$TEST_HOME" 2>/dev/null || echo "No home directory"
    echo "Dotfiles directory contents:"
    ls -la "$TEST_DOTFILES" 2>/dev/null || echo "No dotfiles directory"
    echo "Manifest contents:"
    cat "$TEST_DOTFILES/.dotfiles-manifest" 2>/dev/null || echo "No manifest"
    echo "======================="
}