# dotfiles

Portable, cross-platform dotfiles managed with [chezmoi](https://chezmoi.io) —
shell, terminal, editor, and AI-tooling config that works on laptops, servers,
and dev containers.

## What's included

- **zsh** — portable `.zshrc` (interactive-guarded, multi-distro) + [antidote](https://github.com/mattmc3/antidote) plugins
- **tmux** — `.tmux.conf` + a cheatsheet
- **starship** — prompt
- **neovim** — [LazyVim](https://www.lazyvim.org/)
- **kitty** — terminal
- **eza** — theme
- **git** — identity supplied per machine via chezmoi data (see below), never hardcoded
- **Claude Code / Codex** — curated `~/.claude` and `~/.codex` config: doctrine files, authored skills, statusline
- **paru / yay** — AUR helper config (Arch)

## Apply

These are my personal settings — including permissive Claude Code permission
defaults tuned for unattended agents — so preview before applying:

```sh
chezmoi init emsilva/dotfiles   # clone only
chezmoi diff                    # see what would change
chezmoi apply                   # apply
```

Git identity is deliberately not baked in. Tell chezmoi who you are first, in
`~/.config/chezmoi/chezmoi.toml`:

```toml
[data]
    gitName  = "Your Name"
    gitEmail = "you@example.com"
```

## Notes

- `~/.zprofile` (machine-local secrets/env) is intentionally **not** tracked.
- `txt2zpl` reads `$ZPL_PRINTER` — set it in `~/.zprofile` if you use a label printer.
- History honors a pre-set `$HISTFILE` (e.g. a dev container's persistent-history volume).
- tmux plugins load via [TPM](https://github.com/tmux-plugins/tpm); clone it once:
  `git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm`
