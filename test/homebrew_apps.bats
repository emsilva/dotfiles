#!/usr/bin/env bats

setup() {
  export BREW_LOG="$BATS_TEST_TMPDIR/brew.log"
  export BASH_ENV="$BATS_TEST_TMPDIR/stub_env.sh"
  cat <<'EOS' > "$BASH_ENV"
brew() {
  echo "brew $@" >> "$BREW_LOG"
  if [ "$1" = ls ]; then return 1; else return 0; fi
}
curl() { :; }
git() { :; }
defaults() { :; }
mas() { :; }
chezmoi() { :; }
gem() { :; }
rm() { :; }
mkdir() { :; }
EOS
}

@test "homebrew apps with spaces or options do not cause failures" {
  run bash bin/executable_set-me-up.sh
  [ "$status" -eq 0 ]
  grep -F "brew install emacs-plus@28 --with-native-comp --with-modern-black-variant-icon" "$BREW_LOG"
  grep -F "brew install --cask whatsapp" "$BREW_LOG"
}
