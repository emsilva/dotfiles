#!/usr/bin/env bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not in a git repository!"
    exit 1
fi

# Check if there are any changes to commit
if git diff --quiet && git diff --cached --quiet; then
    print_info "No changes to commit. Repository is clean."
    exit 0
fi

print_info "Checking git status..."
git status --short

# Show what changes will be committed
if ! git diff --cached --quiet; then
    print_info "Staged changes:"
    git diff --cached --name-only | sed 's/^/  - /'
fi

if ! git diff --quiet; then
    print_info "Unstaged changes:"
    git diff --name-only | sed 's/^/  - /'
    
    # Stage all changes
    print_info "Staging all changes..."
    git add .
fi

# Function to analyze changes and generate commit message
generate_commit_message() {
    local files_changed=$(git diff --cached --name-only | wc -l)
    local files_list=$(git diff --cached --name-only | head -5)
    
    # Simple heuristics based on changed files
    if echo "$files_list" | grep -q "^dotfiles/\..*rc$\|^dotfiles/\..*sh$"; then
        local config_files=$(echo "$files_list" | grep "^dotfiles/\." | sed 's/^dotfiles\///' | head -3 | paste -sd, -)
        if [ $files_changed -eq 1 ]; then
            echo "Update $config_files configuration"
        else
            echo "Update configuration files ($config_files)"
        fi
    elif echo "$files_list" | grep -q "^scripts/"; then
        local script_files=$(echo "$files_list" | grep "^scripts/" | head -2 | paste -sd, -)
        echo "Improve $script_files functionality"
    elif echo "$files_list" | grep -q "^test/"; then
        echo "Add test coverage for recent changes"
    elif echo "$files_list" | grep -q "CLAUDE\.md\|README\.md"; then
        echo "Update documentation and project guidelines"
    elif echo "$files_list" | grep -q "packages\.yml"; then
        echo "Update package definitions"
    elif echo "$files_list" | grep -q "install\.sh\|update\.sh"; then
        echo "Improve installation and update scripts"
    else
        # Fallback: try to use API if available
        if command -v curl >/dev/null 2>&1 && [ -n "$OPENAI_API_KEY" ]; then
            generate_ai_commit_message
        else
            echo "Update dotfiles configuration"
        fi
    fi
}

# Function to generate commit message using AI (optional)
generate_ai_commit_message() {
    local diff_content=$(git diff --cached)
    local prompt="Analyze these git changes and generate a concise commit message (max 50 chars) following the pattern: 'Fix X for Y' or 'Add X to Y' or 'Update X configuration'. Changes:\n\n$diff_content"
    
    local response=$(curl -s -X POST "https://api.openai.com/v1/chat/completions" \
        -H "Authorization: Bearer $OPENAI_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"gpt-3.5-turbo\",
            \"messages\": [{\"role\": \"user\", \"content\": \"$prompt\"}],
            \"max_tokens\": 20,
            \"temperature\": 0.3
        }" 2>/dev/null)
    
    if [ $? -eq 0 ] && echo "$response" | grep -q "content"; then
        echo "$response" | grep -o '"content":"[^"]*"' | cut -d'"' -f4 | head -1
    else
        echo "Update dotfiles configuration"
    fi
}

# Generate commit message
COMMIT_MSG=$(generate_commit_message)

# Commit changes
print_info "Committing changes..."
git commit -m "$COMMIT_MSG"

# Check if we have a remote to push to
if git remote get-url origin > /dev/null 2>&1; then
    print_info "Pushing to remote repository..."
    git push
    print_info "✅ Dotfiles updated and pushed successfully!"
else
    print_warn "No remote repository configured. Changes committed locally only."
fi