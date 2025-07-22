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
Usage: $0 [OPTIONS]

List all files and directories currently managed by dotfiles.

OPTIONS:
    -h, --help          Show this help message
    -v, --verbose       Show detailed information about each managed file
    -s, --status        Show status of each managed file (symlink check)
    -p, --paths         Show full paths instead of relative paths
    -c, --count         Show only the count of managed files

EXAMPLES:
    $0                  # List all managed files
    $0 --verbose        # Show detailed information
    $0 --status         # Check symlink status for each file

EOF
}

# Function to check if file is properly symlinked
check_symlink_status() {
    local rel_path="$1"
    local target_path="$HOME/$rel_path"
    local dotfiles_path="$SCRIPT_DIR/dotfiles/$rel_path"
    
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

# Function to get file type
get_file_type() {
    local path="$1"
    
    if [[ -d "$path" ]]; then
        echo "directory"
    elif [[ -f "$path" ]]; then
        echo "file"
    elif [[ -L "$path" ]]; then
        echo "symlink"
    else
        echo "unknown"
    fi
}

# Function to format file size
format_size() {
    local size="$1"
    
    if [[ $size -lt 1024 ]]; then
        echo "${size}B"
    elif [[ $size -lt 1048576 ]]; then
        echo "$(( size / 1024 ))K"
    else
        echo "$(( size / 1048576 ))M"
    fi
}

# Main function
main() {
    local verbose=false
    local show_status=false
    local show_paths=false
    local count_only=false
    
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
            -s|--status)
                show_status=true
                shift
                ;;
            -p|--paths)
                show_paths=true
                shift
                ;;
            -c|--count)
                count_only=true
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
    
    local manifest_file="$SCRIPT_DIR/.dotfiles-manifest"
    
    # Check if manifest exists
    if [[ ! -f "$manifest_file" ]]; then
        print_warn "No dotfiles manifest found. No files are currently managed."
        print_info "Use './dotfiles-add.sh <file>' to start managing files"
        exit 0
    fi
    
    # Read managed files
    local managed_files=()
    while IFS= read -r line; do
        [[ -n "$line" ]] && managed_files+=("$line")
    done < "$manifest_file"
    
    # Handle count only
    if [[ "$count_only" == true ]]; then
        echo "${#managed_files[@]}"
        exit 0
    fi
    
    # Show header
    if [[ ${#managed_files[@]} -eq 0 ]]; then
        print_info "No files are currently managed by dotfiles"
        exit 0
    fi
    
    echo -e "${GREEN}=== MANAGED DOTFILES ===${NC}"
    echo -e "Total managed files: ${BLUE}${#managed_files[@]}${NC}"
    echo ""
    
    # Show files
    for rel_path in "${managed_files[@]}"; do
        local display_path="$rel_path"
        if [[ "$show_paths" == true ]]; then
            display_path="$HOME/$rel_path"
        fi
        
        if [[ "$verbose" == true ]] || [[ "$show_status" == true ]]; then
            local dotfiles_path="$SCRIPT_DIR/dotfiles/$rel_path"
            local target_path="$HOME/$rel_path"
            
            # File type and size
            local file_type=""
            local file_size=""
            if [[ -e "$dotfiles_path" ]]; then
                file_type=$(get_file_type "$dotfiles_path")
                if [[ "$file_type" == "file" ]]; then
                    local size
                    size=$(stat -c%s "$dotfiles_path" 2>/dev/null || stat -f%z "$dotfiles_path" 2>/dev/null || echo "0")
                    file_size=" ($(format_size "$size"))"
                fi
            else
                file_type="MISSING"
            fi
            
            # Status check
            local status=""
            if [[ "$show_status" == true ]]; then
                local link_status
                link_status=$(check_symlink_status "$rel_path")
                case "$link_status" in
                    "OK")
                        status=" ${GREEN}✓${NC}"
                        ;;
                    "MISSING")
                        status=" ${RED}✗ MISSING${NC}"
                        ;;
                    "NOT_SYMLINK")
                        status=" ${YELLOW}⚠ NOT SYMLINK${NC}"
                        ;;
                    "WRONG_TARGET")
                        status=" ${YELLOW}⚠ WRONG TARGET${NC}"
                        ;;
                esac
            fi
            
            # Format output
            if [[ "$verbose" == true ]]; then
                echo -e "  ${BLUE}$display_path${NC} (${file_type}${file_size})${status}"
                if [[ -e "$dotfiles_path" ]]; then
                    echo -e "    Managed: $dotfiles_path"
                    echo -e "    Target:  $target_path"
                fi
                echo ""
            else
                echo -e "  ${BLUE}$display_path${NC}${status}"
            fi
        else
            echo -e "  ${BLUE}$display_path${NC}"
        fi
    done
    
    # Show additional info
    if [[ "$show_status" == true ]]; then
        echo ""
        echo -e "${YELLOW}Status Legend:${NC}"
        echo -e "  ${GREEN}✓${NC}           - Properly symlinked"
        echo -e "  ${RED}✗ MISSING${NC}    - File missing from home directory"
        echo -e "  ${YELLOW}⚠ NOT SYMLINK${NC} - File exists but is not a symlink"
        echo -e "  ${YELLOW}⚠ WRONG TARGET${NC} - Symlink points to wrong location"
    fi
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run main function
main "$@"
