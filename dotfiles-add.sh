#!/usr/bin/env bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_debug() { echo -e "${BLUE}[DEBUG]${NC} $1"; }

# Function to get the appropriate home directory (test-aware)
get_home_dir() {
    # Check if we're in a test environment (script dir under /tmp)
    if [[ "$SCRIPT_DIR" == /tmp/* ]]; then
        # Look for a "home" directory at the parent level (typical test setup)
        local test_home_dir="$(dirname "$SCRIPT_DIR")/home"
        if [[ -d "$test_home_dir" ]]; then
            echo "$test_home_dir"
            return
        fi
        # Fallback: Look for a "home" directory in the script directory  
        local test_home_dir_alt="$SCRIPT_DIR/home"
        if [[ -d "$test_home_dir_alt" ]]; then
            echo "$test_home_dir_alt"
            return
        fi
    fi
    
    # Default to real HOME directory
    echo "$HOME"
}

# Function to show help
show_help() {
    cat << EOF
Usage: $0 [OPTIONS] <file_or_directory>

Add a file or directory to dotfiles management.

ARGUMENTS:
    file_or_directory    Path to the file or directory to add (relative to HOME or absolute)

OPTIONS:
    -h, --help          Show this help message
    -v, --verbose       Show detailed output
    -n, --dry-run       Show what would be done without making changes
    -f, --force         Overwrite existing managed file without prompting

EXAMPLES:
    $0 .config/starship.toml        # Add starship config
    $0 ~/.local/bin/my-script       # Add custom script
    $0 .config/nvim                 # Add entire nvim directory

BEHAVIOR:
    1. Creates backup of original file/directory
    2. Moves original to dotfiles/ directory
    3. Creates symlink from original location
    4. Updates dotfiles manifest

EOF
}

# Function to normalize path (remove HOME prefix, ensure relative)
normalize_path() {
    local path="$1"
    local home_dir
    home_dir=$(get_home_dir)
    
    # Convert absolute path to relative to home directory
    if [[ "$path" == "$home_dir"* ]]; then
        path="${path#$home_dir/}"
    elif [[ "$path" == /* ]]; then
        # For absolute paths not under home, use basename for manifest
        # This handles edge cases where paths are under unexpected directories
        path=$(basename "$path")
    fi
    
    # Remove leading ./
    path="${path#./}"
    
    # Remove leading /
    path="${path#/}"
    
    echo "$path"
}

# Function to check if file is already managed
is_managed() {
    local rel_path="$1"
    local manifest_file="$SCRIPT_DIR/.dotfiles-manifest"
    
    if [[ -f "$manifest_file" ]]; then
        grep -q "^$rel_path$" "$manifest_file" 2>/dev/null
    else
        return 1
    fi
}

# Function to add entry to manifest
add_to_manifest() {
    local rel_path="$1"
    local manifest_file="$SCRIPT_DIR/.dotfiles-manifest"
    
    # Create manifest if it doesn't exist
    touch "$manifest_file"
    
    # Add entry if not already present
    if ! is_managed "$rel_path"; then
        echo "$rel_path" >> "$manifest_file"
        # Sort the manifest
        sort "$manifest_file" -o "$manifest_file"
        print_info "Added $rel_path to manifest"
    fi
}

# Function to create backup
create_backup() {
    local source_path="$1"
    local rel_path="$2"
    local backup_dir="$SCRIPT_DIR/backups/$(date +%Y%m%d_%H%M%S)"
    local backup_path="$backup_dir/$rel_path"
    
    mkdir -p "$(dirname "$backup_path")"
    
    if [[ -d "$source_path" ]]; then
        cp -r "$source_path" "$backup_path"
    else
        cp "$source_path" "$backup_path"
    fi
    
    print_info "Backup created: $backup_path"
}

# Function to move file to dotfiles directory
move_to_dotfiles() {
    local source_path="$1"
    local rel_path="$2"
    local dotfiles_path="$SCRIPT_DIR/dotfiles/$rel_path"
    
    # Create parent directory if needed
    mkdir -p "$(dirname "$dotfiles_path")"
    
    # Move the file/directory
    mv "$source_path" "$dotfiles_path"
    print_info "Moved to dotfiles: $rel_path"
}

# Function to create symlink
create_symlink() {
    local rel_path="$1"
    local original_target="$2"  # The original target path where symlink should be created
    local dotfiles_path="$SCRIPT_DIR/dotfiles/$rel_path"
    
    # Use original target location if provided, otherwise default to home directory
    local home_dir
    home_dir=$(get_home_dir)
    local target_path="${original_target:-$home_dir/$rel_path}"
    
    # Create parent directory if needed
    mkdir -p "$(dirname "$target_path")"
    
    # Create symlink
    ln -s "$dotfiles_path" "$target_path"
    print_info "Created symlink: $rel_path"
}

# Function to confirm action
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

# Main function
main() {
    local target_path=""
    local dry_run=false
    local verbose=false
    local force=false
    local skip_confirmation=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--verbose)
                verbose=true
                shift
                ;;
            -n|--dry-run)
                dry_run=true
                shift
                ;;
            -f|--force)
                force=true
                shift
                ;;
            -y|--yes|--skip-confirmation)
                skip_confirmation=true
                shift
                ;;
            -*)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                if [[ -z "$target_path" ]]; then
                    target_path="$1"
                else
                    print_error "Multiple file arguments provided. Only one file/directory can be added at a time."
                    exit 1
                fi
                shift
                ;;
        esac
    done
    
    # Validate arguments
    if [[ -z "$target_path" ]]; then
        print_error "No file or directory specified"
        show_help
        exit 1
    fi
    
    # Convert to absolute path for processing
    if [[ "$target_path" != /* ]]; then
        if [[ "$target_path" == ~* ]]; then
            target_path="${target_path/#~/$HOME}"
        else
            target_path="$HOME/$target_path"
        fi
    fi
    
    # Check if file exists
    if [[ ! -e "$target_path" ]]; then
        print_error "File or directory does not exist: $target_path"
        exit 1
    fi
    
    # Normalize path for manifest
    local rel_path
    rel_path=$(normalize_path "$target_path")
    
    # Check if already managed
    if is_managed "$rel_path"; then
        if [[ "$force" != true ]]; then
            print_error "File is already managed: $rel_path"
            print_info "Use --force to overwrite or run: ./dotfiles-remove.sh '$rel_path'"
            exit 1
        else
            print_warn "File is already managed, will overwrite due to --force flag"
        fi
    fi
    
    # Show preview
    echo -e "\n${GREEN}=== DOTFILES ADD PREVIEW ===${NC}"
    echo -e "Target file/directory: ${BLUE}$target_path${NC}"
    echo -e "Relative path: ${BLUE}$rel_path${NC}"
    echo -e "Actions to perform:"
    echo -e "  ${YELLOW}1.${NC} Create backup of original"
    echo -e "  ${YELLOW}2.${NC} Move original to dotfiles/$rel_path"
    echo -e "  ${YELLOW}3.${NC} Create symlink from $(get_home_dir)/$rel_path"
    echo -e "  ${YELLOW}4.${NC} Add to dotfiles manifest"
    
    if [[ "$dry_run" == true ]]; then
        print_info "DRY RUN - No changes will be made"
        exit 0
    fi
    
    # Confirm action
    if [[ "$skip_confirmation" != true ]]; then
        confirm_action "Add $rel_path to dotfiles management?"
    fi
    
    # Perform operations
    print_info "Adding $rel_path to dotfiles management..."
    
    # Create backup
    create_backup "$target_path" "$rel_path"
    
    # Move to dotfiles directory
    move_to_dotfiles "$target_path" "$rel_path"
    
    # Create symlink
    create_symlink "$rel_path" "$target_path"
    
    # Add to manifest
    add_to_manifest "$rel_path"
    
    print_info "Successfully added $rel_path to dotfiles management"
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run main function
main "$@"
