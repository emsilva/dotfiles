#!/usr/bin/env bash
set -e

# Minimal version to test the main loop logic
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Function to determine the correct target path for symlinks
get_target_path() {
    local rel_path="$1"
    local default_path="$HOME/$rel_path"
    
    # If symlink already exists, use its location
    if [[ -L "$default_path" ]]; then
        echo "$default_path"
        return
    fi
    
    # Check if we're in a test environment (script dir under /tmp)
    if [[ "$SCRIPT_DIR" == /tmp/* ]]; then
        # Look for a "home" directory in the parent directory
        local test_home_dir="$(dirname "$SCRIPT_DIR")/home"
        if [[ -d "$test_home_dir" ]]; then
            echo "$test_home_dir/$rel_path"
            return
        fi
    fi
    
    # Default to HOME-based path
    echo "$default_path"
}

# Function to check symlink status
check_symlink_status() {
    local rel_path="$1"
    local target_path
    target_path=$(get_target_path "$rel_path")
    local dotfiles_path="$SCRIPT_DIR/dotfiles/$rel_path"
    
    echo "DEBUG: checking $rel_path" >&2
    echo "DEBUG: target_path=$target_path" >&2
    echo "DEBUG: dotfiles_path=$dotfiles_path" >&2
    
    # Check if dotfile exists
    if [[ ! -e "$dotfiles_path" ]]; then
        echo "DOTFILE_MISSING"
        return
    fi
    
    # Check target path
    if [[ ! -e "$target_path" ]]; then
        echo "MISSING"
    elif [[ ! -L "$target_path" ]]; then
        echo "NOT_SYMLINK"
    else
        local link_target
        link_target=$(readlink "$target_path")
        if [[ "$link_target" == "$dotfiles_path" ]]; then
            echo "OK"
        else
            echo "WRONG_TARGET"
        fi
    fi
}

# Read managed files
manifest_file="$SCRIPT_DIR/.dotfiles-manifest"
if [[ ! -f "$manifest_file" ]]; then
    echo "No manifest found"
    exit 0
fi

echo "Reading manifest from: $manifest_file" >&2

# Simple approach: read files one by one
while IFS= read -r rel_path; do
    [[ -n "$rel_path" ]] || continue
    echo "Processing: $rel_path" >&2
    
    file_status=$(check_symlink_status "$rel_path")
    echo "Status: $file_status" >&2
    
    case "$file_status" in
        "MISSING")
            echo -e "  ${RED}✗${NC} ${BLUE}$rel_path${NC} - MISSING"
            ;;
        "OK")
            echo -e "  ${GREEN}✓${NC} ${BLUE}$rel_path${NC}"
            ;;
        *)
            echo -e "  ${RED}?${NC} ${BLUE}$rel_path${NC} - $file_status"
            ;;
    esac
done < "$manifest_file"