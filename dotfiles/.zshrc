# ──────────────────────────────────────────────────────────────────────────────
# 1) PATH & ENV
# ──────────────────────────────────────────────────────────────────────────────
# start with your own bins, then keep every default path
export PATH="$HOME/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# macOS coreutils (M1 vs Intel)
if [[ "$(uname)" == "Darwin" ]]; then
  export PATH="/opt/homebrew/opt/coreutils/libexec/gnubin:$PATH"
  export MANPATH="/opt/homebrew/opt/coreutils/libexec/gnuman:$MANPATH"
else
  export PATH="/usr/local/opt/coreutils/libexec/gnubin:$PATH"
  export MANPATH="/usr/local/opt/coreutils/libexec/gnuman:$MANPATH"
fi

# Ruby gems bin (if Ruby is installed)
if command -v ruby &>/dev/null; then
  export PATH="$(ruby -e 'print Gem.user_dir')/bin:$PATH"
fi

# OpenJDK (if installed)
export PATH="/usr/local/opt/openjdk/bin:$PATH"

export ZSH="$HOME/.oh-my-zsh"
export LANG=en_US.UTF-8
export HOMEBREW_NO_ENV_HINTS=TRUE

# ──────────────────────────────────────────────────────────────────────────────
# 2) HISTORY
# ──────────────────────────────────────────────────────────────────────────────
export HISTFILE=~/.zsh_history
export HISTSIZE=10000
export SAVEHIST=10000

setopt EXTENDED_HISTORY HIST_IGNORE_ALL_DUPS HIST_FIND_NO_DUPS \
       INC_APPEND_HISTORY SHARE_HISTORY

# ──────────────────────────────────────────────────────────────────────────────
# 3) SHELL OPTIONS
# ──────────────────────────────────────────────────────────────────────────────
setopt autocd correct prompt_subst

# ──────────────────────────────────────────────────────────────────────────────
# 4) PLUGINS
# ──────────────────────────────────────────────────────────────────────────────
plugins=(
  git
  fzf
  zoxide
  zsh-autosuggestions
  zsh-syntax-highlighting
  history-substring-search
)

ZSH_THEME=""
source $ZSH/oh-my-zsh.sh

eval "$(/opt/homebrew/bin/brew shellenv)"

# ──────────────────────────────────────────────────────────────────────────────
# 5) PROMPT (Starship)
# ──────────────────────────────────────────────────────────────────────────────
if command -v starship &>/dev/null; then
  eval "$(starship init zsh)"
fi
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
