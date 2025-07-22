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
# Base plugins that work on both platforms
plugins=(
  git
  history-substring-search
)

# Platform-specific plugin configuration
if [[ "$(uname)" == "Darwin" ]]; then
  # macOS - add plugins if they exist via Homebrew
  if [[ -d /opt/homebrew/share/zsh-autosuggestions ]] || [[ -d ~/.oh-my-zsh/plugins/zsh-autosuggestions ]]; then
    plugins+=(zsh-autosuggestions)
  fi
  if [[ -d /opt/homebrew/share/zsh-syntax-highlighting ]] || [[ -d ~/.oh-my-zsh/plugins/zsh-syntax-highlighting ]]; then
    plugins+=(zsh-syntax-highlighting)
  fi
  # fzf and zoxide are handled by oh-my-zsh plugins on macOS
  if command -v fzf &>/dev/null; then
    plugins+=(fzf)
  fi
  if command -v zoxide &>/dev/null; then
    plugins+=(zoxide)
  fi
fi
# Note: Ubuntu plugins are handled manually after oh-my-zsh loads

ZSH_THEME=""
source $ZSH/oh-my-zsh.sh

# Platform-specific Homebrew setup
if [[ "$(uname)" == "Darwin" ]]; then
  if [[ -f "/opt/homebrew/bin/brew" ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -f "/usr/local/bin/brew" ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
fi

# Manual plugin loading for Ubuntu (since oh-my-zsh plugins may not work)
if [[ "$(uname)" == "Linux" ]]; then
  # Load zsh-autosuggestions if installed via apt
  if [[ -f /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh ]]; then
    source /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh
  fi
  
  # Load zsh-syntax-highlighting if installed via apt (must be last)
  if [[ -f /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]]; then
    source /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
  fi
  
  # Initialize fzf if available
  if command -v fzf &>/dev/null; then
    if [[ -f /usr/share/doc/fzf/examples/key-bindings.zsh ]]; then
      source /usr/share/doc/fzf/examples/key-bindings.zsh
    fi
    if [[ -f /usr/share/doc/fzf/examples/completion.zsh ]]; then
      source /usr/share/doc/fzf/examples/completion.zsh
    fi
    export FZF_DEFAULT_OPTS='--height 40% --layout=reverse --border'
  fi
  
  # Initialize zoxide if available
  if command -v zoxide &>/dev/null; then
    eval "$(zoxide init zsh)"
  fi
fi

# ──────────────────────────────────────────────────────────────────────────────
# 5) COLORS & PROMPT
# ──────────────────────────────────────────────────────────────────────────────
# LS_COLORS setup (cross-platform)
if [[ "$(uname)" == "Darwin" ]]; then
  # macOS: Use ls_colors from trapd00r tap if available
  if command -v gdircolors &>/dev/null && [[ -f "$(brew --prefix)/share/LS_COLORS" ]]; then
    eval "$(gdircolors "$(brew --prefix)/share/LS_COLORS")"
  elif command -v dircolors &>/dev/null; then
    eval "$(dircolors -b)"
  fi
elif [[ "$(uname)" == "Linux" ]]; then
  # Ubuntu: Use cloned repository method
  if [[ -f ~/.local/share/LS_COLORS/lscolors.sh ]]; then
    source ~/.local/share/LS_COLORS/lscolors.sh
  elif [[ -f ~/.dircolors ]]; then
    eval "$(dircolors ~/.dircolors)"
  elif command -v dircolors &>/dev/null; then
    eval "$(dircolors -b)"
  fi
fi

# Starship prompt
if command -v starship &>/dev/null; then
  eval "$(starship init zsh)"
fi
