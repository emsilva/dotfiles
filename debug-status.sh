#!/usr/bin/env bash

# Simple debug script to test status checking

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
manifest_file="$SCRIPT_DIR/.dotfiles-manifest"

echo "=== DEBUG STATUS CHECK ==="

if [[ ! -f "$manifest_file" ]]; then
    echo "No manifest found"
    exit 1
fi

echo "Manifest contents:"
cat "$manifest_file"
echo ""

while IFS= read -r rel_path; do
    [[ -z "$rel_path" ]] && continue
    
    echo "Checking: $rel_path"
    
    target_path="$HOME/$rel_path"
    dotfiles_path="$SCRIPT_DIR/dotfiles/$rel_path"
    
    echo "  Target: $target_path"
    echo "  Dotfiles: $dotfiles_path"
    
    if [[ ! -e "$dotfiles_path" ]]; then
        echo "  Status: DOTFILE_MISSING"
    elif [[ ! -e "$target_path" ]]; then
        echo "  Status: MISSING"
    elif [[ ! -L "$target_path" ]]; then
        echo "  Status: NOT_SYMLINK"
    else
        link_target=$(readlink "$target_path")
        if [[ "$link_target" == "$dotfiles_path" ]]; then
            echo "  Status: OK"
        else
            echo "  Status: WRONG_TARGET (points to: $link_target)"
        fi
    fi
    echo ""
done < "$manifest_file"
