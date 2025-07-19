# Dotfiles

This repository contains my personal configuration files managed by [chezmoi](https://www.chezmoi.io/). Chezmoi applies the files to a host system so that everything from the shell environment to editor settings can be reproduced quickly.

## Overview

The dotfiles cover two major areas:

1. **Shell and system configuration** – Zsh setup, Git settings, and macOS defaults.
2. **Editor configuration** – Vim and Doom Emacs settings.

Scripts in `bin/` automate installing packages and customising macOS.

## Repository structure

```
.
├── bin/                       # setup scripts
├── dot_config/chezmoi/        # chezmoi configuration
├── dot_doom.d/                # Doom Emacs configuration
├── dot_local/share/iterm2/    # iTerm2 preferences
├── dot_p10k.zsh               # Powerlevel10k prompt configuration
├── dot_vimrc                  # Vim configuration
└── dot_zshrc                  # Zsh configuration
```

## Key components

### Chezmoi configuration
`dot_config/chezmoi/chezmoi.toml` defines commands used by chezmoi when editing and diffing files.

### Shell environment
`dot_zshrc` loads oh‑my‑zsh, sets `PATH`, and manages plugins with zplug. The prompt style is configured in `dot_p10k.zsh`.

### Git configuration templates
`dot_gitconfig.tmpl` and `dot_gitconfig-work.tmpl` include placeholders that pull email addresses from 1Password when chezmoi applies them.

### Doom Emacs
`dot_doom.d/` contains Doom Emacs modules in `init.el` and personal tweaks in `config.el`.

### macOS setup scripts
`bin/executable_set-me-up.sh` installs Homebrew packages and clones additional repositories. `bin/executable_macos-sane-defaults.sh` configures macOS defaults such as Finder and Dock behaviour.

### iTerm2 settings
Settings for iTerm2 live under `dot_local/share/iterm2/com.googlecode.iterm2.plist` so they can be linked on a new machine.

## Running tests

Install [bats](https://bats-core.readthedocs.io/) and run:

```bash
make test
```

This runs the Bats tests located in the `test/` directory.
