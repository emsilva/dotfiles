#!/usr/bin/env bats

# Tests to ensure feature parity across supported platforms
# This prevents the nvim-on-macOS type issues where features are defined
# in packages.yml but not implemented in platform scripts

setup() {
    export TEST_TEMP_DIR="$BATS_TEST_TMPDIR/cross_platform_test"
    mkdir -p "$TEST_TEMP_DIR"
    
    # Copy packages.yml to test directory
    cp "$BATS_TEST_DIRNAME/../packages.yml" "$TEST_TEMP_DIR/"
    cd "$TEST_TEMP_DIR"
}

teardown() {
    rm -rf "$TEST_TEMP_DIR"
}

# Test that all github_releases entries have corresponding implementations
@test "github_releases defined in packages.yml must be supported by all platform scripts" {
    # Check if github_releases is defined for macos
    local macos_has_github_releases
    macos_has_github_releases=$(awk '/^macos:/,/^ubuntu:/ { if (/^  github_releases:/) print "yes" }' packages.yml)
    
    # Check if github_releases is defined for ubuntu  
    local ubuntu_has_github_releases
    ubuntu_has_github_releases=$(awk '/^ubuntu:/,/^ruby_gems:/ { if (/^  github_releases:/) print "yes" }' packages.yml)
    
    # If either platform defines github_releases, both scripts must have the function
    if [[ "$macos_has_github_releases" == "yes" || "$ubuntu_has_github_releases" == "yes" ]]; then
        # Check that macos.sh has process_github_releases function
        grep -q "process_github_releases()" "$BATS_TEST_DIRNAME/../scripts/macos.sh"
        
        # Check that ubuntu.sh has process_github_releases function  
        grep -q "process_github_releases()" "$BATS_TEST_DIRNAME/../scripts/ubuntu.sh"
        
        # Check that both scripts call the function
        grep -q "process_github_releases" "$BATS_TEST_DIRNAME/../scripts/macos.sh"
        grep -q "process_github_releases" "$BATS_TEST_DIRNAME/../scripts/ubuntu.sh"
    fi
}

# Test that all custom_install entries have corresponding implementations
@test "custom_install defined in packages.yml must be supported by all platform scripts" {
    # Check if custom_install is defined for macos
    local macos_has_custom_install
    macos_has_custom_install=$(awk '/^macos:/,/^ubuntu:/ { if (/^  custom_install:/) print "yes" }' packages.yml)
    
    # Check if custom_install is defined for ubuntu
    local ubuntu_has_custom_install  
    ubuntu_has_custom_install=$(awk '/^ubuntu:/,/^ruby_gems:/ { if (/^  custom_install:/) print "yes" }' packages.yml)
    
    # If either platform defines custom_install, both scripts must handle it
    if [[ "$macos_has_custom_install" == "yes" || "$ubuntu_has_custom_install" == "yes" ]]; then
        # Check that both scripts parse custom_install section
        grep -q "custom_install" "$BATS_TEST_DIRNAME/../scripts/macos.sh"
        grep -q "custom_install" "$BATS_TEST_DIRNAME/../scripts/ubuntu.sh"
        
        # Check that both have install_custom_packages function
        grep -q "install_custom_packages()" "$BATS_TEST_DIRNAME/../scripts/macos.sh"
        grep -q "install_custom_packages()" "$BATS_TEST_DIRNAME/../scripts/ubuntu.sh"
    fi
}

# Test that the same packages defined in github_releases work on both platforms
@test "github_releases packages must have valid configurations for their target platforms" {
    # Extract package names from macos github_releases
    local macos_packages
    mapfile -t macos_packages < <(awk '/^macos:/,/^ubuntu:/ {
        if (/^  github_releases:/) in_section=1
        if (in_section && /^    - name:/) {
            gsub(/^    - name: /, "")
            print $0
        }
        if (/^ubuntu:/) in_section=0
    }' packages.yml)
    
    # Extract package names from ubuntu github_releases  
    local ubuntu_packages
    mapfile -t ubuntu_packages < <(awk '/^ubuntu:/,/^ruby_gems:/ {
        if (/^  github_releases:/) in_section=1
        if (in_section && /^    - name:/) {
            gsub(/^    - name: /, "")
            print $0
        }
        if (/^ruby_gems:/) in_section=0
    }' packages.yml)
    
    # Check that packages have appropriate asset patterns for their platforms
    for pkg in "${macos_packages[@]}"; do
        if [[ -n "$pkg" ]]; then
            # macOS packages should reference macOS assets
            local macos_pattern
            macos_pattern=$(awk "/^macos:/,/^ubuntu:/ {
                if (/^    - name: $pkg\$/) found=1
                if (found && /^      asset_pattern:/) {
                    gsub(/^      asset_pattern: /, \"\")
                    print \$0
                    found=0
                }
            }" packages.yml)
            
            # Should contain macos, darwin, or x86_64 identifier
            [[ "$macos_pattern" =~ (macos|darwin|x86_64) ]]
        fi
    done
    
    for pkg in "${ubuntu_packages[@]}"; do
        if [[ -n "$pkg" ]]; then
            # Ubuntu packages should reference Linux assets
            local ubuntu_pattern
            ubuntu_pattern=$(awk "/^ubuntu:/,/^ruby_gems:/ {
                if (/^    - name: $pkg\$/) found=1
                if (found && /^      asset_pattern:/) {
                    gsub(/^      asset_pattern: /, \"\")
                    print \$0
                    found=0
                }
            }" packages.yml)
            
            # Should contain linux identifier
            [[ "$ubuntu_pattern" =~ linux ]]
        fi
    done
}

# Test that functions called in packages.yml actually exist in scripts
@test "all package installation methods must have corresponding function implementations" {
    # Get all unique installation methods referenced in packages.yml
    local methods
    mapfile -t methods < <(grep -E "^  (homebrew|apt|custom_install|github_releases):" packages.yml | cut -d: -f1 | sed 's/^  //' | sort -u)
    
    for method in "${methods[@]}"; do
        case "$method" in
            "homebrew")
                # Should have homebrew-related functions in macos.sh
                grep -q "install_homebrew\|install_packages" "$BATS_TEST_DIRNAME/../scripts/macos.sh"
                ;;
            "apt")
                # Should have apt-related functions in ubuntu.sh
                grep -q "apt.*install\|install.*apt" "$BATS_TEST_DIRNAME/../scripts/ubuntu.sh"
                ;;
            "custom_install") 
                # Should have custom install handling in both
                grep -q "install_custom_packages" "$BATS_TEST_DIRNAME/../scripts/macos.sh"
                grep -q "install_custom_packages" "$BATS_TEST_DIRNAME/../scripts/ubuntu.sh"
                ;;
            "github_releases")
                # Should have github releases handling in both  
                grep -q "process_github_releases" "$BATS_TEST_DIRNAME/../scripts/macos.sh"
                grep -q "process_github_releases" "$BATS_TEST_DIRNAME/../scripts/ubuntu.sh"
                ;;
        esac
    done
}

# Test that main setup functions call all necessary sub-functions
@test "platform scripts must call all installation functions for defined package types" {
    # Check macos.sh calls all required functions
    local macos_content
    macos_content=$(cat "$BATS_TEST_DIRNAME/../scripts/macos.sh")
    
    # If packages.yml defines sections for macos, the script must call corresponding functions
    if grep -q "^macos:" packages.yml; then
        if grep -A 20 "^macos:" packages.yml | grep -q "homebrew:"; then
            [[ "$macos_content" =~ install_homebrew|install_packages ]]
        fi
        
        if grep -A 20 "^macos:" packages.yml | grep -q "custom_install:"; then
            [[ "$macos_content" =~ install_custom_packages ]]  
        fi
        
        if grep -A 20 "^macos:" packages.yml | grep -q "github_releases:"; then
            [[ "$macos_content" =~ process_github_releases ]]
        fi
    fi
    
    # Check ubuntu.sh calls all required functions
    local ubuntu_content
    ubuntu_content=$(cat "$BATS_TEST_DIRNAME/../scripts/ubuntu.sh")
    
    if grep -q "^ubuntu:" packages.yml; then
        if grep -A 20 "^ubuntu:" packages.yml | grep -q "apt:"; then
            [[ "$ubuntu_content" =~ install.*apt|apt.*install ]]
        fi
        
        if grep -A 20 "^ubuntu:" packages.yml | grep -q "custom_install:"; then
            [[ "$ubuntu_content" =~ install_custom_packages ]]
        fi
        
        if grep -A 20 "^ubuntu:" packages.yml | grep -q "github_releases:"; then
            [[ "$ubuntu_content" =~ process_github_releases ]]
        fi
    fi
}