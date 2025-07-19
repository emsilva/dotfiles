#!/usr/bin/env bats

setup() {
  export BREW_LOG="$BATS_TEST_TMPDIR/brew.log"
  export BASH_ENV="$BATS_TEST_TMPDIR/stub_env.sh"
  cat <<'EOS' > "$BASH_ENV"
brew() {
  echo "brew $@" >> "$BREW_LOG"
  if [ "$1" = "list" ]; then return 1; 
  elif [ "$1" = "services" ] && [ "$2" = "list" ]; then echo "syncthing none"; return 0;
  elif [ "$1" = "tap" ]; then return 0;
  else return 0; fi
}
curl() { :; }
git() { :; }
defaults() { :; }
mas() { :; }
chezmoi() { :; }
gem() { if [ "$1" = "list" ]; then return 1; else return 0; fi }
rm() { :; }
mkdir() { :; }
chflags() { :; }
dockutil() { :; }
command() { if [ "$2" = "brew" ]; then return 1; else return 0; fi }
test() { return 1; }
EOS
}

@test "homebrew apps with spaces or options do not cause failures" {
  run bash scripts/macos.sh
  [ "$status" -eq 0 ]
  grep -F "brew install --cask whatsapp" "$BREW_LOG"
  grep -F "brew install python-tk@3.9" "$BREW_LOG"
}
