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
Usage: $0 [OPTIONS]

Migrate from the old symlink-everything approach to the new manifest-based system.

This script helps transition your dotfiles to the new selective management system by:
1. Identifying currently symlinked files that point to the dotfiles directory
2. Adding them to the manifest if they're not already managed
3. Cleaning up any problematic symlinks

OPTIONS:
    -h, --help          Show this help message
    -n, --dry-run       Show what would be done without making changes
    -y, --yes           Skip confirmation prompts
    -v, --verbose       Show detailed output

EXAMPLES:
    $0                  # Interactive migration
    $0 --dry-run        # Preview migration actions
    $0 --yes            # Automatic migration

EOF
}

# Function to find dotfiles symlinks
find_dotfiles_symlinks() {
    local symlinks=()
    local home_dir
    home_dir=$(get_home_dir)
    
    # Check common locations for dotfiles
    for pattern in "$home_dir"/.[!.]* "$home_dir"/.config/* "$home_dir"/.local/bin/* "$home_dir"/.local/share/*; do
        [[ -e "$pattern" ]] || continue
        
        if [[ -L "$pattern" ]]; then
            local link_target
            link_target=$(readlink "$pattern")
            
            # Check if it points to our dotfiles directory
            if [[ "$link_target" == *"/dotfiles/"* ]]; then
                local rel_path="${pattern#$home_dir/}"
                symlinks+=("$rel_path")
            fi
        fi
    done
    
    printf '%s\n' "${symlinks[@]}"
}

# Function to check if file is in manifest
is_in_manifest() {
    local rel_path="$1"
    local manifest_file="$SCRIPT_DIR/.dotfiles-manifest"
    
    if [[ -f "$manifest_file" ]]; then
        grep -q "^$rel_path$" "$manifest_file" 2>/dev/null
    else
        return 1
    fi
}

# Function to add to manifest
add_to_manifest() {
    local rel_path="$1"
    local manifest_file="$SCRIPT_DIR/.dotfiles-manifest"
    
    # Create manifest if it doesn't exist
    touch "$manifest_file"
    
    # Add entry if not already present
    if ! is_in_manifest "$rel_path"; then
        echo "$rel_path" >> "$manifest_file"
        # Sort the manifest
        sort "$manifest_file" -o "$manifest_file"
        return 0
    fi
    
    return 1
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
    local dry_run=false
    local verbose=false
    local skip_confirmation=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -n|--dry-run)
                dry_run=true
                shift
                ;;
            -v|--verbose)
                verbose=true
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
                print_error "Unexpected argument: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    echo -e "${GREEN}=== DOTFILES MIGRATION TOOL ===${NC}"
    echo "This tool helps migrate from the old system to the new manifest-based approach."
    echo ""
    
    # Find current symlinks
    print_info "Scanning for existing dotfiles symlinks..."
    local symlinks=()
    mapfile -t symlinks < <(find_dotfiles_symlinks)
    
    if [[ ${#symlinks[@]} -eq 0 ]]; then
        print_info "No existing dotfiles symlinks found."
        print_info "Your system is ready for the new manifest-based approach!"
        exit 0
    fi
    
    print_info "Found ${#symlinks[@]} existing dotfiles symlinks"
    
    # Categorize symlinks
    local already_managed=()
    local to_add=()
    local problematic=()
    
    for rel_path in "${symlinks[@]}"; do
        local dotfiles_path="$SCRIPT_DIR/dotfiles/$rel_path"
        
        if is_in_manifest "$rel_path"; then
            already_managed+=("$rel_path")
        elif [[ -e "$dotfiles_path" ]]; then
            to_add+=("$rel_path")
        else
            problematic+=("$rel_path")
        fi
    done
    
    # Show summary
    echo -e "\n${BLUE}=== MIGRATION SUMMARY ===${NC}"
    echo -e "Already managed: ${GREEN}${#already_managed[@]}${NC}"
    echo -e "Will be added: ${YELLOW}${#to_add[@]}${NC}"
    echo -e "Problematic: ${RED}${#problematic[@]}${NC}"
    echo ""
    
    # Show files to be added
    if [[ ${#to_add[@]} -gt 0 ]]; then
        echo -e "${YELLOW}Files to be added to manifest:${NC}"
        for rel_path in "${to_add[@]}"; do
            echo -e "  + $rel_path"
        done
        echo ""
    fi
    
    # Show problematic files
    if [[ ${#problematic[@]} -gt 0 ]]; then
        echo -e "${RED}Problematic symlinks (pointing to non-existent files):${NC}"
        for rel_path in "${problematic[@]}"; do
            echo -e "  ! $rel_path"
        done
        echo -e "${YELLOW}These will be removed during migration.${NC}"
        echo ""
    fi
    
    # Show already managed
    if [[ ${#already_managed[@]} -gt 0 ]] && [[ "$verbose" == true ]]; then
        echo -e "${GREEN}Already managed files:${NC}"
        for rel_path in "${already_managed[@]}"; do
            echo -e "  ✓ $rel_path"
        done
        echo ""
    fi
    
    if [[ ${#to_add[@]} -eq 0 ]] && [[ ${#problematic[@]} -eq 0 ]]; then
        print_info "No migration needed. All symlinks are already properly managed!"
        exit 0
    fi
    
    if [[ "$dry_run" == true ]]; then
        print_info "DRY RUN - No changes will be made"
        exit 0
    fi
    
    # Confirm migration
    if [[ "$skip_confirmation" != true ]]; then
        confirm_action "Proceed with migration?"
    fi
    
    # Perform migration
    print_info "Starting migration..."
    
    local added_count=0
    local removed_count=0
    
    # Add valid files to manifest
    for rel_path in "${to_add[@]}"; do
        if add_to_manifest "$rel_path"; then
            print_info "Added to manifest: $rel_path"
            ((added_count++))
        fi
    done
    
    # Remove problematic symlinks
    for rel_path in "${problematic[@]}"; do
        local home_dir
        home_dir=$(get_home_dir)
        local target_path="$home_dir/$rel_path"
        if [[ -L "$target_path" ]]; then
            rm "$target_path"
            print_warn "Removed problematic symlink: $rel_path"
            ((removed_count++))
        fi
    done
    
    print_info "Migration complete!"
    print_info "Added $added_count files to manifest"
    print_info "Removed $removed_count problematic symlinks"
    
    echo ""
    print_info "Next steps:"
    echo -e "  1. Run ${BLUE}./dotfiles-status.sh${NC} to verify your dotfiles"
    echo -e "  2. Use ${BLUE}./dotfiles-add.sh <file>${NC} to manage new files"
    echo -e "  3. Use ${BLUE}./dotfiles-list.sh${NC} to see all managed files"
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run main function
main "$@"
