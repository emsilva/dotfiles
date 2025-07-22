#!/usr/bin/env bash

# Simple status checker

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== SIMPLE STATUS CHECK ==="

while IFS= read -r rel_path; do
    [[ -z "$rel_path" ]] && continue
    
    echo "Checking: $rel_path"
    
    target_path="$HOME/$rel_path"
    dotfiles_path="$SCRIPT_DIR/dotfiles/$rel_path"
    
    if [[ ! -e "$dotfiles_path" ]]; then
        echo "  ✗ DOTFILE_MISSING"
    elif [[ ! -e "$target_path" ]]; then
        echo "  ✗ MISSING"
    elif [[ ! -L "$target_path" ]]; then
        echo "  ⚠ NOT_SYMLINK"
    else
        link_target=$(readlink "$target_path")
        if [[ "$link_target" == "$dotfiles_path" ]]; then
            echo "  ✓ OK"
        else
            echo "  ⚠ WRONG_TARGET"
        fi
    fi
done < .dotfiles-manifest
