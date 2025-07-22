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

# Function to ask for user confirmation
confirm_action() {
    local message="$1"
    echo -e "${YELLOW}[CONFIRM]${NC} $message"
    read -r -p "Do you want to proceed? (y/N): " response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            return 0
            ;;
        *)
            print_info "Operation cancelled by user."
            exit 0
            ;;
    esac
}

# Function to show update preview
show_update_preview() {
    local staged_files=$(git diff --cached --name-only | wc -l)
    local unstaged_files=$(git diff --name-only | wc -l)
    local total_files=$((staged_files + unstaged_files))
    
    echo -e "\n${GREEN}=== DOTFILES UPDATE PREVIEW ===${NC}"
    echo -e "This script will perform the following actions:"
    echo -e ""
    echo -e "  ${YELLOW}1. Stage all changes${NC} ($total_files files)"
    
    if ! git diff --cached --quiet; then
        echo -e "     Staged files:"
        git diff --cached --name-only | sed 's/^/       - /'
    fi
    
    if ! git diff --quiet; then
        echo -e "     Unstaged files:"
        git diff --name-only | sed 's/^/       - /'
    fi
    
    echo -e "  ${YELLOW}2. Generate intelligent commit message${NC}"
    if [ -n "$OPENAI_API_KEY" ]; then
        echo -e "     Using AI analysis (OpenAI API)"
    else
        echo -e "     Using local file analysis"
    fi
    
    echo -e "  ${YELLOW}3. Create git commit${NC} with generated message"
    
    if git remote get-url origin > /dev/null 2>&1; then
        echo -e "  ${YELLOW}4. Push to remote repository${NC} (origin)"
    else
        echo -e "  ${YELLOW}4. Commit locally${NC} (no remote configured)"
    fi
    
    echo -e ""
    echo -e "${YELLOW}WARNING:${NC} This will commit and push changes to your git repository."
    echo -e ""
}

# Main update function  
main() {
    # Get the directory where this script is located
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Change to the dotfiles directory to ensure git operations work correctly
    cd "$script_dir" || {
        print_error "Failed to change to script directory: $script_dir"
        exit 1
    }
    
    # Parse command line arguments
    local skip_confirmation=false
    while [[ $# -gt 0 ]]; do
        case $1 in
            -y|--yes|--skip-confirmation)
                skip_confirmation=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  -y, --yes, --skip-confirmation    Skip confirmation prompts"
                echo "  -h, --help                        Show this help message"
                echo ""
                echo "Environment Variables:"
                echo "  OPENAI_API_KEY                    Enable AI-enhanced commit messages"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use -h or --help for usage information."
                exit 1
                ;;
        esac
    done

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

    # Show preview and get confirmation
    show_update_preview
    
    if [[ "$skip_confirmation" != true ]]; then
        confirm_action "The above actions will be performed on your git repository."
    fi
    
    print_info "Proceeding with update..."

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
}

# Function to analyze changes and generate commit message
generate_commit_message() {
    local files_changed=$(git diff --cached --name-only | wc -l)
    local files_list=$(git diff --cached --name-only | head -5)
    
    # Try AI analysis first if API key is available
    if command -v curl >/dev/null 2>&1 && [ -n "$OPENAI_API_KEY" ]; then
        local ai_message=$(generate_ai_commit_message)
        if [ -n "$ai_message" ] && [ "$ai_message" != "Update dotfiles configuration" ]; then
            echo "$ai_message"
            return
        fi
    fi
    
    # Fallback to local heuristics based on changed files
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
        echo "Update dotfiles configuration"
    fi
}

# Function to generate commit message using AI (optional)
generate_ai_commit_message() {
    local diff_content=$(git diff --cached)
    # Escape quotes and newlines for JSON
    local escaped_content=$(echo "$diff_content" | sed 's/"/\\"/g' | tr '\n' '\\' | sed 's/\\/\\n/g')
    local prompt="Analyze these git changes and generate a clear, descriptive commit message (50-72 characters ideal, max 100). Use conventional commit format when appropriate (feat:, fix:, docs:, etc.). Focus on what changed and why. Changes:\\n\\n$escaped_content"
    
    local json_payload=$(cat <<EOF
{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "$prompt"}],
    "max_tokens": 80,
    "temperature": 0.2
}
EOF
)
    
    local response=$(echo "$json_payload" | curl -s -X POST "https://api.openai.com/v1/chat/completions" \
        -H "Authorization: Bearer $OPENAI_API_KEY" \
        -H "Content-Type: application/json" \
        -d @- 2>/dev/null)
    
    if [ $? -eq 0 ] && echo "$response" | grep -q '"content"'; then
        # Extract content using grep and sed (no jq required)
        echo "$response" | grep -o '"content":"[^"]*"' | sed 's/"content":"//' | sed 's/"$//' | head -1
    else
        # Debug: uncomment next line to see API response
        # echo "API Error: $response" >&2
        echo ""
    fi
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi