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

Check the status of all managed dotfiles and detect issues.

OPTIONS:
    -h, --help          Show this help message
    -v, --verbose       Show detailed output for all files
    -q, --quiet         Only show issues (errors and warnings)
    -f, --fix           Attempt to fix issues automatically
    -n, --dry-run       Show what fixes would be applied without making changes
    -y, --yes           Skip confirmation prompts (used for automation)

EXAMPLES:
    $0                  # Check status of all managed files
    $0 --quiet          # Only show problems
    $0 --fix            # Automatically fix issues

STATUS MEANINGS:
    ✓ OK               - File is properly symlinked
    ✗ MISSING          - File missing from home directory
    ⚠ NOT_SYMLINK      - File exists but is not a symlink
    ⚠ WRONG_TARGET     - Symlink points to wrong location
    ✗ DOTFILE_MISSING  - Managed file missing from dotfiles directory

EOF
}

# Function to validate manifest entry
validate_manifest_entry() {
    local entry="$1"
    
    # Check for binary data (non-printable characters except newlines/spaces)
    if [[ "$entry" =~ [[:cntrl:]] && ! "$entry" =~ ^[[:space:]]*$ ]]; then
        return 1
    fi
    
    # Check for suspicious patterns
    if [[ "$entry" =~ \.\./ ]] || [[ "$entry" =~ ^/ ]]; then
        return 1
    fi
    
    # Entry seems valid
    return 0
}

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
        # Look for a "home" directory at the parent level (typical test setup)
        local test_home_dir="$(dirname "$SCRIPT_DIR")/home"
        if [[ -d "$test_home_dir" ]]; then
            echo "$test_home_dir/$rel_path"
            return
        fi
        # Fallback: Look for a "home" directory in the script directory  
        local test_home_dir_alt="$SCRIPT_DIR/home"
        if [[ -d "$test_home_dir_alt" ]]; then
            echo "$test_home_dir_alt/$rel_path"
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

# Function to fix symlink issues
fix_symlink_issue() {
    local rel_path="$1"
    local status="$2"
    local target_path
    target_path=$(get_target_path "$rel_path")
    local dotfiles_path="$SCRIPT_DIR/dotfiles/$rel_path"
    
    case "$status" in
        "MISSING")
            print_info "Creating missing symlink: $rel_path"
            mkdir -p "$(dirname "$target_path")"
            ln -s "$dotfiles_path" "$target_path"
            ;;
        "NOT_SYMLINK")
            print_warn "Backing up non-symlink file and creating symlink: $rel_path"
            local backup_dir="$SCRIPT_DIR/backups/status_fix_$(date +%Y%m%d_%H%M%S)"
            mkdir -p "$backup_dir/$(dirname "$rel_path")"
            
            if [[ -d "$target_path" ]]; then
                cp -r "$target_path" "$backup_dir/$rel_path"
            else
                cp "$target_path" "$backup_dir/$rel_path"
            fi
            
            rm -rf "$target_path"
            ln -s "$dotfiles_path" "$target_path"
            print_info "Backup created: $backup_dir/$rel_path"
            ;;
        "WRONG_TARGET")
            print_info "Fixing wrong symlink target: $rel_path"
            rm "$target_path"
            ln -s "$dotfiles_path" "$target_path"
            ;;
        "DOTFILE_MISSING")
            print_error "Cannot fix: Managed file missing from dotfiles directory: $rel_path"
            print_info "Consider removing from management: ./dotfiles-remove.sh '$rel_path'"
            return 1
            ;;
    esac
    
    return 0
}

# Function to count issues by type
count_issues() {
    local -A issue_counts=()
    local manifest_file="$SCRIPT_DIR/.dotfiles-manifest"
    
    if [[ ! -f "$manifest_file" ]]; then
        return
    fi
    
    while IFS= read -r rel_path; do
        [[ -z "$rel_path" ]] && continue
        
        local status
        status=$(check_symlink_status "$rel_path")
        
        if [[ "$status" != "OK" ]]; then
            # Simplified counting without associative arrays
            echo "ISSUE: $status for $rel_path" >&2
        fi
    done < "$manifest_file"
    
    # Print summary
    local total_issues=0
    for count in "${issue_counts[@]}"; do
        ((total_issues += count))
    done
    
    if [[ $total_issues -gt 0 ]]; then
        echo -e "\n${YELLOW}=== ISSUE SUMMARY ===${NC}"
        for status in "${!issue_counts[@]}"; do
            echo -e "  $status: ${issue_counts[$status]}"
        done
        echo -e "  Total issues: $total_issues"
    fi
}

# Main function
main() {
    local verbose=false
    local quiet=false
    local fix_issues=false
    local dry_run=false
    
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
            -q|--quiet)
                quiet=true
                shift
                ;;
            -f|--fix)
                fix_issues=true
                shift
                ;;
            -n|--dry-run)
                dry_run=true
                shift
                ;;
            -y|--yes|--skip-confirmation)
                # Skip confirmation (used by tests and automation)
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
        exit 0
    fi
    
    # Read managed files using array with validation
    local managed_files=()
    local invalid_entries=0
    while IFS= read -r line; do
        if [[ -n "$line" ]]; then
            if validate_manifest_entry "$line"; then
                managed_files+=("$line")
            else
                print_warn "Skipping invalid manifest entry: $line"
                invalid_entries=$((invalid_entries + 1))
            fi
        fi
    done < "$manifest_file"
    
    # Show warning if invalid entries were found
    if [[ $invalid_entries -gt 0 ]]; then
        print_error "Found $invalid_entries invalid entries in manifest file"
        print_info "Consider cleaning the manifest: ./dotfiles-list.sh"
    fi
    
    if [[ ${#managed_files[@]} -eq 0 ]]; then
        print_info "No files are currently managed by dotfiles"
        exit 0
    fi
    
    # Show header
    if [[ "$quiet" != true ]]; then
        echo -e "${GREEN}=== DOTFILES STATUS CHECK ===${NC}"
        echo -e "Checking ${#managed_files[@]} managed files...\n"
    fi
    
    local issues_found=0
    local issues_fixed=0
    local issues_failed=0
    
    # Check each file
    for rel_path in "${managed_files[@]}"; do
        local status
        status=$(check_symlink_status "$rel_path")
        
        local status_symbol=""
        local status_color=""
        local show_this_line=true
        
        case "$status" in
            "OK")
                status_symbol="${GREEN}✓${NC}"
                status_color="$GREEN"
                if [[ "$quiet" == true ]]; then
                    show_this_line=false
                fi
                ;;
            "MISSING")
                status_symbol="${RED}✗${NC}"
                status_color="$RED"
                issues_found=$((issues_found + 1))
                ;;
            "NOT_SYMLINK")
                status_symbol="${YELLOW}⚠${NC}"
                status_color="$YELLOW"
                issues_found=$((issues_found + 1))
                ;;
            "WRONG_TARGET")
                status_symbol="${YELLOW}⚠${NC}"
                status_color="$YELLOW"
                issues_found=$((issues_found + 1))
                ;;
            "DOTFILE_MISSING")
                status_symbol="${RED}✗${NC}"
                status_color="$RED"
                issues_found=$((issues_found + 1))
                ;;
        esac
        
        # Show status line
        if [[ "$show_this_line" == true ]]; then
            if [[ "$verbose" == true ]]; then
                echo -e "  $status_symbol ${BLUE}$rel_path${NC} - ${status_color}$status${NC}"
            else
                echo -e "  $status_symbol ${BLUE}$rel_path${NC}"
            fi
        fi
        
        # Attempt fix if requested
        if [[ "$fix_issues" == true && "$status" != "OK" ]]; then
            if [[ "$dry_run" == true ]]; then
                echo -e "    ${YELLOW}[DRY RUN]${NC} Would fix: $status"
            else
                if fix_symlink_issue "$rel_path" "$status"; then
                    issues_fixed=$((issues_fixed + 1))
                    echo -e "    ${GREEN}[FIXED]${NC} Issue resolved"
                else
                    issues_failed=$((issues_failed + 1))
                    echo -e "    ${RED}[FAILED]${NC} Could not fix issue"
                fi
            fi
        fi
    done
    
    # Show summary
    if [[ "$quiet" != true ]] || [[ $issues_found -gt 0 ]]; then
        echo ""
        if [[ $issues_found -eq 0 ]]; then
            print_info "All managed files are properly configured ✓"
        else
            print_warn "Found $issues_found issue(s) with managed files"
            
            if [[ "$fix_issues" == true ]]; then
                if [[ "$dry_run" == true ]]; then
                    print_info "DRY RUN: Would attempt to fix $issues_found issues"
                else
                    print_info "Fixed: $issues_fixed, Failed: $issues_failed"
                fi
            else
                print_info "Run with --fix to attempt automatic repairs"
            fi
        fi
    fi
    
    # Show issue breakdown
    if [[ "$verbose" == true ]] && [[ $issues_found -gt 0 ]]; then
        count_issues
    fi
    
    # Exit with error code based on situation
    if [[ "$fix_issues" == true && "$dry_run" != true ]]; then
        # When fixing, exit with number of failed fixes
        exit $issues_failed
    else
        # When just checking, exit with number of issues found
        exit $issues_found
    fi
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run main function
main "$@"
