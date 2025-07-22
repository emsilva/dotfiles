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

@test "update.sh has fallback commit message" {
    grep -q "Update dotfiles configuration" update.sh
}

@test "update.sh handles remote repository gracefully" {
    grep -q "git remote get-url origin" update.sh
    grep -q "No remote repository configured" update.sh
}