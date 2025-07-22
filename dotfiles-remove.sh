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

# Function to show help
show_help() {
    cat << EOF
Usage: $0 [OPTIONS] <file_or_directory>

Remove a file or directory from dotfiles management.

ARGUMENTS:
    file_or_directory    Path to the file or directory to remove (relative to HOME)

OPTIONS:
    -h, --help          Show this help message
    -v, --verbose       Show detailed output
    -n, --dry-run       Show what would be done without making changes
    -k, --keep-backup   Keep the backup instead of restoring original
    -y, --yes           Skip confirmation prompts

EXAMPLES:
    $0 .config/starship.toml        # Remove starship config from management
    $0 .local/bin/my-script         # Remove custom script from management
    $0 .config/nvim                 # Remove entire nvim directory from management

BEHAVIOR:
    1. Removes symlink from home directory
    2. Copies managed file back to original location
    3. Removes file from dotfiles/ directory
    4. Updates dotfiles manifest
    5. Optionally keeps backup for safety

EOF
}

# Function to normalize path (remove HOME prefix, ensure relative)
normalize_path() {
    local path="$1"
    
    # Convert absolute path to relative to HOME
    if [[ "$path" == "$HOME"* ]]; then
        path="${path#$HOME/}"
    fi
    
    # Remove leading ./
    path="${path#./}"
    
    # Remove leading /
    path="${path#/}"
    
    echo "$path"
}

# Function to check if file is managed
is_managed() {
    local rel_path="$1"
    local manifest_file="$SCRIPT_DIR/.dotfiles-manifest"
    
    if [[ -f "$manifest_file" ]]; then
        grep -q "^$rel_path$" "$manifest_file" 2>/dev/null
    else
        return 1
    fi
}

# Function to remove entry from manifest
remove_from_manifest() {
    local rel_path="$1"
    local manifest_file="$SCRIPT_DIR/.dotfiles-manifest"
    
    if [[ -f "$manifest_file" ]]; then
        # Create temporary file without the entry
        grep -v "^$rel_path$" "$manifest_file" > "$manifest_file.tmp" || true
        mv "$manifest_file.tmp" "$manifest_file"
        print_info "Removed $rel_path from manifest"
    fi
}

# Function to create backup before removal
create_removal_backup() {
    local dotfiles_path="$1"
    local rel_path="$2"
    local backup_dir="$SCRIPT_DIR/backups/removal_$(date +%Y%m%d_%H%M%S)"
    local backup_path="$backup_dir/$rel_path"
    
    mkdir -p "$(dirname "$backup_path")"
    
    if [[ -d "$dotfiles_path" ]]; then
        cp -r "$dotfiles_path" "$backup_path"
    else
        cp "$dotfiles_path" "$backup_path"
    fi
    
    print_info "Removal backup created: $backup_path"
}

# Function to remove symlink
remove_symlink() {
    local rel_path="$1"
    local target_path="$HOME/$rel_path"
    
    if [[ -L "$target_path" ]]; then
        rm "$target_path"
        print_info "Removed symlink: $rel_path"
    elif [[ -e "$target_path" ]]; then
        print_warn "Target exists but is not a symlink: $target_path"
        print_warn "Manual intervention may be required"
    fi
}

# Function to restore file from dotfiles
restore_file() {
    local rel_path="$1"
    local dotfiles_path="$SCRIPT_DIR/dotfiles/$rel_path"
    local target_path="$HOME/$rel_path"
    
    # Create parent directory if needed
    mkdir -p "$(dirname "$target_path")"
    
    # Copy file back to original location
    if [[ -d "$dotfiles_path" ]]; then
        cp -r "$dotfiles_path" "$target_path"
    else
        cp "$dotfiles_path" "$target_path"
    fi
    
    print_info "Restored file to: $target_path"
}

# Function to remove from dotfiles directory
remove_from_dotfiles() {
    local rel_path="$1"
    local dotfiles_path="$SCRIPT_DIR/dotfiles/$rel_path"
    
    if [[ -e "$dotfiles_path" ]]; then
        rm -rf "$dotfiles_path"
        print_info "Removed from dotfiles: $rel_path"
    fi
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
    local keep_backup=false
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
            -k|--keep-backup)
                keep_backup=true
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
                    print_error "Multiple file arguments provided. Only one file/directory can be removed at a time."
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
    
    # Normalize path for manifest
    local rel_path
    rel_path=$(normalize_path "$target_path")
    
    # Check if managed
    if ! is_managed "$rel_path"; then
        print_error "File is not managed: $rel_path"
        print_info "Run './dotfiles-list.sh' to see managed files"
        exit 1
    fi
    
    local dotfiles_path="$SCRIPT_DIR/dotfiles/$rel_path"
    local target_full_path="$HOME/$rel_path"
    
    # Check if dotfiles version exists
    if [[ ! -e "$dotfiles_path" ]]; then
        print_error "Managed file not found in dotfiles: $dotfiles_path"
        print_warn "This indicates a corrupt state. Removing from manifest only."
        remove_from_manifest "$rel_path"
        exit 1
    fi
    
    # Show preview
    echo -e "\n${GREEN}=== DOTFILES REMOVE PREVIEW ===${NC}"
    echo -e "Target file/directory: ${BLUE}$rel_path${NC}"
    echo -e "Dotfiles location: ${BLUE}$dotfiles_path${NC}"
    echo -e "Home location: ${BLUE}$target_full_path${NC}"
    echo -e "Actions to perform:"
    echo -e "  ${YELLOW}1.${NC} Create backup of managed file"
    echo -e "  ${YELLOW}2.${NC} Remove symlink from $HOME/$rel_path"
    echo -e "  ${YELLOW}3.${NC} Restore file to original location"
    echo -e "  ${YELLOW}4.${NC} Remove from dotfiles/$rel_path"
    echo -e "  ${YELLOW}5.${NC} Remove from dotfiles manifest"
    
    if [[ "$keep_backup" == true ]]; then
        echo -e "  ${BLUE}Note:${NC} Backup will be kept due to --keep-backup flag"
    fi
    
    if [[ "$dry_run" == true ]]; then
        print_info "DRY RUN - No changes will be made"
        exit 0
    fi
    
    # Confirm action
    if [[ "$skip_confirmation" != true ]]; then
        confirm_action "Remove $rel_path from dotfiles management?"
    fi
    
    # Perform operations
    print_info "Removing $rel_path from dotfiles management..."
    
    # Create backup
    if [[ "$keep_backup" == true ]]; then
        create_removal_backup "$dotfiles_path" "$rel_path"
    fi
    
    # Remove symlink
    remove_symlink "$rel_path"
    
    # Restore file
    restore_file "$rel_path"
    
    # Remove from dotfiles directory
    remove_from_dotfiles "$rel_path"
    
    # Remove from manifest
    remove_from_manifest "$rel_path"
    
    print_info "Successfully removed $rel_path from dotfiles management"
    print_info "File restored to: $target_full_path"
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run main function
main "$@"
