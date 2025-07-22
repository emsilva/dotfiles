#!/usr/bin/env bats

@test "dotfiles-sync.sh exists and is executable" {
    [ -f dotfiles-sync.sh ]
    [ -x dotfiles-sync.sh ]
}

@test "dotfiles-sync.sh has proper shebang" {
    head -n1 dotfiles-sync.sh | grep -q "#!/usr/bin/env bash"
}

@test "dotfiles-sync.sh has error handling" {
    grep -q "set -e" dotfiles-sync.sh
}

@test "dotfiles-sync.sh has colored output functions" {
    grep -q "print_info()" dotfiles-sync.sh
    grep -q "print_warn()" dotfiles-sync.sh
    grep -q "print_error()" dotfiles-sync.sh
}

@test "dotfiles-sync.sh checks for git repository" {
    grep -q "git rev-parse --git-dir" dotfiles-sync.sh
}

@test "dotfiles-sync.sh checks for changes before committing" {
    grep -q "git diff --quiet" dotfiles-sync.sh
}

@test "dotfiles-sync.sh has intelligent commit message generation" {
    grep -q "generate_commit_message()" dotfiles-sync.sh
    grep -q "files_changed=" dotfiles-sync.sh
    grep -q "files_list=" dotfiles-sync.sh
}

@test "dotfiles-sync.sh has file-based heuristics" {
    grep -q "dotfiles/.*rc" dotfiles-sync.sh
    grep -q "scripts/" dotfiles-sync.sh
    grep -q "test/" dotfiles-sync.sh
    grep -q "CLAUDE" dotfiles-sync.sh
}

@test "dotfiles-sync.sh has optional AI integration" {
    grep -q "generate_ai_commit_message()" dotfiles-sync.sh
    grep -q "OPENAI_API_KEY" dotfiles-sync.sh
}

@test "dotfiles-sync.sh prioritizes AI over local heuristics when API key is available" {
    # Check that AI analysis is tried first
    grep -A 10 "generate_commit_message()" dotfiles-sync.sh | grep -q "Try AI analysis first"
    # Check that the function structure prioritizes AI
    grep -A 20 "generate_commit_message()" dotfiles-sync.sh | grep -B 5 -A 5 "generate_ai_commit_message" | grep -q "if.*OPENAI_API_KEY"
}

@test "dotfiles-sync.sh has improved JSON handling for AI requests" {
    grep -q "grep -o.*content" dotfiles-sync.sh
    grep -q "escaped_content" dotfiles-sync.sh
    grep -q "json_payload" dotfiles-sync.sh
}

@test "dotfiles-sync.sh has proper AI fallback behavior" {
    # Check that it returns empty string on AI failure
    grep -A 5 "API Error" dotfiles-sync.sh | grep -q 'echo ""'
    # Check that main function handles empty AI response
    grep -A 3 "ai_message.*generate_ai_commit_message" dotfiles-sync.sh | grep -q "Update dotfiles configuration"
}

@test "dotfiles-sync.sh has fallback commit message" {
    grep -q "Update dotfiles configuration" dotfiles-sync.sh
}

@test "dotfiles-sync.sh handles remote repository gracefully" {
    grep -q "git remote get-url origin" dotfiles-sync.sh
    grep -q "No remote repository configured" dotfiles-sync.sh
}

@test "dotfiles-sync.sh has confirmation functionality" {
    grep -q "confirm_action()" dotfiles-sync.sh
    grep -q "show_update_preview()" dotfiles-sync.sh
    grep -q "skip_confirmation" dotfiles-sync.sh
}

@test "dotfiles-sync.sh supports bypass flags" {
    grep -q "\-y.*skip.confirmation" dotfiles-sync.sh
    grep -q "\-\-yes.*skip.confirmation" dotfiles-sync.sh
    grep -q "\-\-skip.confirmation" dotfiles-sync.sh
}

@test "dotfiles-sync.sh has help functionality" {
    grep -q "\-h.*help" dotfiles-sync.sh
    grep -q "Usage:" dotfiles-sync.sh
    grep -q "Environment Variables:" dotfiles-sync.sh
}