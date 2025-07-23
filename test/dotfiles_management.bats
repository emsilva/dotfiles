#!/usr/bin/env bats

# Test the new dotfiles management system

setup() {
    # Create temporary directory for testing
    TEST_DIR=$(mktemp -d)
    export TEST_HOME="$TEST_DIR/home"
    export TEST_DOTFILES="$TEST_DIR/dotfiles"
    
    mkdir -p "$TEST_HOME"
    mkdir -p "$TEST_DOTFILES/dotfiles"
    mkdir -p "$TEST_DOTFILES/backups"
    
    # Copy scripts to test directory (from parent directory)
    cp "${BATS_TEST_DIRNAME}/../dotfiles-"*.sh "$TEST_DOTFILES/"
    chmod +x "$TEST_DOTFILES"/dotfiles-*.sh
    
    # Create test files
    echo "test content" > "$TEST_DOTFILES/dotfiles/.testrc"
    mkdir -p "$TEST_DOTFILES/dotfiles/.config"
    echo "config content" > "$TEST_DOTFILES/dotfiles/.config/test.conf"
    
    cd "$TEST_DOTFILES"
}

teardown() {
    # Clean up
    rm -rf "$TEST_DIR"
}

@test "dotfiles-list shows empty when no manifest exists" {
    run ./dotfiles-list.sh
    [ "$status" -eq 0 ]
    [[ "$output" == *"No dotfiles manifest found"* ]]
}

@test "dotfiles-add creates manifest and adds file" {
    # Create a test file in home
    echo "content" > "$TEST_HOME/.testrc"
    
    # Add the file
    run ./dotfiles-add.sh --yes "$TEST_HOME/.testrc"
    [ "$status" -eq 0 ]
    
    # Check manifest was created
    [ -f ".dotfiles-manifest" ]
    
    # Check file was added to manifest
    grep -q "^.testrc$" .dotfiles-manifest
    
    # Check symlink was created
    [ -L "$TEST_HOME/.testrc" ]
    
    # Check file was moved to dotfiles
    [ -f "dotfiles/.testrc" ]
}

@test "dotfiles-add handles existing managed file with force" {
    # Setup initial state
    echo ".testrc" > .dotfiles-manifest
    echo "content" > "dotfiles/.testrc"
    ln -s "$TEST_DOTFILES/dotfiles/.testrc" "$TEST_HOME/.testrc"
    
    # Create new version
    echo "new content" > "$TEST_HOME/.testrc2"
    
    # Try to add existing file with force
    run ./dotfiles-add.sh --force --yes "$TEST_HOME/.testrc2"
    [ "$status" -eq 0 ]
}

@test "dotfiles-remove restores file and removes from manifest" {
    # Setup: add a file first
    echo "content" > "$TEST_HOME/.testrc"
    ./dotfiles-add.sh --yes "$TEST_HOME/.testrc"
    
    # Remove the file
    run ./dotfiles-remove.sh --yes .testrc
    [ "$status" -eq 0 ]
    
    # Check file was restored
    [ -f "$TEST_HOME/.testrc" ]
    [ ! -L "$TEST_HOME/.testrc" ]
    
    # Check removed from dotfiles
    [ ! -f "dotfiles/.testrc" ]
    
    # Check removed from manifest
    ! grep -q "^.testrc$" .dotfiles-manifest
}

@test "dotfiles-list shows managed files" {
    # Setup manifest
    echo -e ".testrc\n.config/test.conf" > .dotfiles-manifest
    
    run ./dotfiles-list.sh
    [ "$status" -eq 0 ]
    [[ "$output" == *".testrc"* ]]
    [[ "$output" == *".config/test.conf"* ]]
}

@test "dotfiles-list shows count with --count option" {
    # Setup manifest with 2 files
    echo -e ".testrc\n.config/test.conf" > .dotfiles-manifest
    
    run ./dotfiles-list.sh --count
    [ "$status" -eq 0 ]
    [ "$output" = "2" ]
}

@test "dotfiles-status detects missing symlinks" {
    # Setup manifest but no symlinks
    echo ".testrc" > .dotfiles-manifest
    echo "content" > "dotfiles/.testrc"
    
    # Copy updated script to ensure we have the latest version
    cp "${BATS_TEST_DIRNAME}/../dotfiles-status.sh" ./
    chmod +x dotfiles-status.sh
    
    run ./dotfiles-status.sh --verbose
    [ "$status" -eq 1 ]  # Should exit with error code when issues found
    [[ "$output" == *"MISSING"* ]]
}

@test "dotfiles-status can fix missing symlinks" {
    # Setup manifest but no symlinks
    echo ".testrc" > .dotfiles-manifest
    echo "content" > "dotfiles/.testrc"
    
    # Copy updated script to ensure we have the latest version
    cp "${BATS_TEST_DIRNAME}/../dotfiles-status.sh" ./
    chmod +x dotfiles-status.sh
    
    run ./dotfiles-status.sh --fix --yes
    [ "$status" -eq 0 ]
    
    # Check symlink was created
    [ -L "$TEST_HOME/.testrc" ]
}

@test "dotfiles-status detects wrong symlink targets" {
    # Setup manifest with wrong symlink
    echo ".testrc" > .dotfiles-manifest
    echo "content" > "dotfiles/.testrc"
    echo "wrong content" > "$TEST_HOME/.wrong"
    ln -s "$TEST_HOME/.wrong" "$TEST_HOME/.testrc"
    
    # Copy updated script to ensure we have the latest version
    cp "${BATS_TEST_DIRNAME}/../dotfiles-status.sh" ./
    chmod +x dotfiles-status.sh
    
    run ./dotfiles-status.sh --verbose
    [ "$status" -eq 1 ]
    [[ "$output" == *"WRONG_TARGET"* ]]
}

@test "dotfiles-migrate finds existing symlinks" {
    # Setup existing symlink to dotfiles
    ln -s "$TEST_DOTFILES/dotfiles/.testrc" "$TEST_HOME/.testrc"
    
    # Copy updated script to ensure we have the latest version
    cp "${BATS_TEST_DIRNAME}/../dotfiles-migrate.sh" ./
    chmod +x dotfiles-migrate.sh
    
    run ./dotfiles-migrate.sh --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *".testrc"* ]]
}

@test "manifest path normalization works" {
    # Test with absolute path
    echo "content" > "$TEST_HOME/.testrc"
    
    run ./dotfiles-add.sh --yes "$TEST_HOME/.testrc"
    [ "$status" -eq 0 ]
    
    # Check manifest contains relative path
    grep -q "^.testrc$" .dotfiles-manifest
}

@test "dotfiles-add creates parent directories" {
    # Create nested config file
    mkdir -p "$TEST_HOME/.config/deep/nested"
    echo "content" > "$TEST_HOME/.config/deep/nested/config.toml"
    
    # Copy updated script to ensure we have the latest version
    cp "${BATS_TEST_DIRNAME}/../dotfiles-add.sh" ./
    chmod +x dotfiles-add.sh
    
    run ./dotfiles-add.sh --yes "$TEST_HOME/.config/deep/nested/config.toml"
    [ "$status" -eq 0 ]
    
    # Check directories were created in dotfiles
    [ -f "dotfiles/.config/deep/nested/config.toml" ]
}

@test "dotfiles-add handles directories" {
    # Create a directory with files
    mkdir -p "$TEST_HOME/.config/testapp"
    echo "config1" > "$TEST_HOME/.config/testapp/config1.conf"
    echo "config2" > "$TEST_HOME/.config/testapp/config2.conf"
    
    run ./dotfiles-add.sh --yes "$TEST_HOME/.config/testapp"
    [ "$status" -eq 0 ]
    
    # Check directory was moved and symlinked
    [ -L "$TEST_HOME/.config/testapp" ]
    [ -d "dotfiles/.config/testapp" ]
    [ -f "dotfiles/.config/testapp/config1.conf" ]
}

@test "dotfiles-remove handles directories" {
    # Setup: add a directory first
    mkdir -p "$TEST_HOME/.config/testapp"
    echo "config" > "$TEST_HOME/.config/testapp/config.conf"
    ./dotfiles-add.sh --yes "$TEST_HOME/.config/testapp"
    
    # Remove the directory
    run ./dotfiles-remove.sh --yes .config/testapp
    [ "$status" -eq 0 ]
    
    # Check directory was restored
    [ -d "$TEST_HOME/.config/testapp" ]
    [ ! -L "$TEST_HOME/.config/testapp" ]
    [ -f "$TEST_HOME/.config/testapp/config.conf" ]
}
