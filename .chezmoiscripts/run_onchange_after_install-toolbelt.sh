#!/usr/bin/env bash
# Install what .zshrc's toolbelt check looks for, plus starship for the prompt,
# on Linux machines that lack them (Codespaces, dev containers). Only missing
# tools are installed. It never fails an apply: anything it cannot install is
# reported in one line. Skip it with DOTFILES_SKIP_TOOLBELT=1. macOS gets these
# from Homebrew.

[ "$(uname -s)" = Linux ] || exit 0
[ -z "${DOTFILES_SKIP_TOOLBELT:-}" ] || exit 0

bin="$HOME/.local/bin"
note() { printf 'toolbelt: %s\n' "$*" >&2; }
have() {
  local c
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || [ -x "$bin/$c" ] && return 0
  done
  return 1
}

# Debian/Ubuntu packages, checked on Ubuntu 24.04, Ubuntu 22.04 and Debian 12.
# fd and bat install as fdfind and batcat there. git-delta exists only on
# Ubuntu 24.04+; elsewhere delta comes from its release below. apt's yq is a
# different program from Homebrew's, so yq always comes from its release.
packages=() missing=()
want() { missing+=("$1"); [ -z "${2:-}" ] || packages+=("$2"); }
have rg || want rg ripgrep
have fd fdfind || want fd fd-find
have fzf || want fzf fzf
have jq || want jq jq
have bat batcat || want bat bat
have delta || want delta git-delta
have tree || want tree tree
have http || want httpie httpie
have gh || want gh gh
have yq || want yq
have ast-grep || want ast-grep
have task || want task
have starship || want starship
[ ${#missing[@]} -gt 0 ] || exit 0

if ! command -v apt-get >/dev/null 2>&1; then
  note "this is not an apt-based system, so nothing was installed. Missing: ${missing[*]}."
  note "install them with your package manager; run toolbelt in zsh for the hint."
  exit 0
fi

if [ ${#packages[@]} -gt 0 ]; then
  if [ "$(id -u)" = 0 ]; then
    as_root=(env)
  elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    as_root=(sudo -n env)
  else
    as_root=()
    note "installing ${packages[*]} needs root; run: sudo apt-get install ${packages[*]}"
  fi
  if [ ${#as_root[@]} -gt 0 ]; then
    "${as_root[@]}" DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null 2>&1 \
      || note "apt-get update failed; using the cached package lists"
    available=()
    for package in "${packages[@]}"; do
      candidate=$(apt-cache policy "$package" 2>/dev/null | awk '/Candidate:/ {print $2}')
      if [ -n "$candidate" ] && [ "$candidate" != "(none)" ]; then
        available+=("$package")
      elif [ "$package" != git-delta ]; then
        note "apt has no $package here; skipped"
      fi
    done
    if [ ${#available[@]} -gt 0 ]; then
      "${as_root[@]}" DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends "${available[@]}" \
        >/dev/null 2>&1 || note "apt-get install failed for: ${available[*]}"
    fi
  fi
fi

mkdir -p "$bin"
# Debian's names for fd and bat; link the usual ones.
have fd || { command -v fdfind >/dev/null 2>&1 && ln -sf "$(command -v fdfind)" "$bin/fd"; }
have bat || { command -v batcat >/dev/null 2>&1 && ln -sf "$(command -v batcat)" "$bin/bat"; }

if ! command -v curl >/dev/null 2>&1; then
  have yq delta starship task || note "curl is missing, so yq, delta, starship and task were skipped"
  exit 0
fi
fetch() { curl -fsL --retry 2 --connect-timeout 10 "$@"; }
case "$(uname -m)" in
  x86_64 | amd64) go_arch=amd64 rust_target=x86_64-unknown-linux-musl ;;
  aarch64 | arm64) go_arch=arm64 rust_target=aarch64-unknown-linux-gnu ;;
  *) go_arch='' rust_target='' ;;
esac

if ! have yq; then
  if [ -n "$go_arch" ] && fetch -o "$bin/yq.part" "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_$go_arch" \
    && chmod +x "$bin/yq.part" && "$bin/yq.part" --version >/dev/null 2>&1; then
    mv "$bin/yq.part" "$bin/yq"
  else
    rm -f "$bin/yq.part"
    note "could not install yq"
  fi
fi

if ! have delta; then
  version=$(fetch https://api.github.com/repos/dandavison/delta/releases/latest 2>/dev/null \
    | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n 1)
  work=$(mktemp -d)
  if [ -n "$rust_target" ] && [ -n "$version" ] \
    && fetch "https://github.com/dandavison/delta/releases/download/$version/delta-$version-$rust_target.tar.gz" \
      | tar -xz -C "$work" && install -m 755 "$work/delta-$version-$rust_target/delta" "$bin/delta"; then
    :
  else
    note "could not install delta"
  fi
  rm -rf "$work"
fi

# A failed download still exits sh 0, so each install is checked afterwards.
if ! have starship; then
  fetch https://starship.rs/install.sh | sh -s -- -y -b "$bin" >/dev/null 2>&1
  have starship || note "could not install starship"
fi

if ! have task; then
  fetch https://taskfile.dev/install.sh | sh -s -- -b "$bin" >/dev/null 2>&1
  have task || note "could not install task"
fi

if ! have ast-grep; then
  if command -v uv >/dev/null 2>&1; then
    uv tool install --quiet ast-grep-cli >/dev/null 2>&1
  elif command -v pipx >/dev/null 2>&1; then
    pipx install ast-grep-cli >/dev/null 2>&1
  elif command -v npm >/dev/null 2>&1; then
    npm install -g --silent @ast-grep/cli >/dev/null 2>&1
  fi
  have ast-grep || note "could not install ast-grep; it needs uv, pipx or npm"
fi
exit 0
