#!/usr/bin/env bats

@test "update.sh exists and is executable" {
    [ -f update.sh ]
    [ -x update.sh ]
}

@test "update.sh has proper shebang" {
    head -n1 update.sh | grep -q "#!/usr/bin/env bash"
}

@test "update.sh has error handling" {
    grep -q "set -e" update.sh
}

@test "update.sh has colored output functions" {
    grep -q "print_info()" update.sh
    grep -q "print_warn()" update.sh
    grep -q "print_error()" update.sh
}

@test "update.sh checks for git repository" {
    grep -q "git rev-parse --git-dir" update.sh
}

@test "update.sh checks for changes before committing" {
    grep -q "git diff --quiet" update.sh
}

@test "update.sh has intelligent commit message generation" {
    grep -q "generate_commit_message()" update.sh
    grep -q "files_changed=" update.sh
    grep -q "files_list=" update.sh
}

@test "update.sh has file-based heuristics" {
    grep -q "dotfiles/.*rc" update.sh
    grep -q "scripts/" update.sh
    grep -q "test/" update.sh
    grep -q "CLAUDE" update.sh
}

@test "update.sh has optional AI integration" {
    grep -q "generate_ai_commit_message()" update.sh
    grep -q "OPENAI_API_KEY" update.sh
}

@test "update.sh prioritizes AI over local heuristics when API key is available" {
    # Check that AI analysis is tried first
    grep -A 10 "generate_commit_message()" update.sh | grep -q "Try AI analysis first"
    # Check that the function structure prioritizes AI
    grep -A 20 "generate_commit_message()" update.sh | grep -B 5 -A 5 "generate_ai_commit_message" | grep -q "if.*OPENAI_API_KEY"
}

@test "update.sh has improved JSON handling for AI requests" {
    grep -q "grep -o.*content" update.sh
    grep -q "escaped_content" update.sh
    grep -q "json_payload" update.sh
}

@test "update.sh has proper AI fallback behavior" {
    # Check that it returns empty string on AI failure
    grep -A 5 "API Error" update.sh | grep -q 'echo ""'
    # Check that main function handles empty AI response
    grep -A 3 "ai_message.*generate_ai_commit_message" update.sh | grep -q "Update dotfiles configuration"
}

@test "update.sh has fallback commit message" {
    grep -q "Update dotfiles configuration" update.sh
}

@test "update.sh handles remote repository gracefully" {
    grep -q "git remote get-url origin" update.sh
    grep -q "No remote repository configured" update.sh
}

@test "update.sh has confirmation functionality" {
    grep -q "confirm_action()" update.sh
    grep -q "show_update_preview()" update.sh
    grep -q "skip_confirmation" update.sh
}

@test "update.sh supports bypass flags" {
    grep -q "\-y.*skip.confirmation" update.sh
    grep -q "\-\-yes.*skip.confirmation" update.sh
    grep -q "\-\-skip.confirmation" update.sh
}

@test "update.sh has help functionality" {
    grep -q "\-h.*help" update.sh
    grep -q "Usage:" update.sh
    grep -q "Environment Variables:" update.sh
}