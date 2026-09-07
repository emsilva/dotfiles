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

## Daily operations

Install [go-task](https://taskfile.dev/installation/), Python 3.11+, chezmoi, Git,
and zsh. From the source checkout (`chezmoi cd`):

```sh
task status       # source/installed drift, visible containers and TCP listeners
task preview      # review rendered changes
task test         # isolated rendering, backup and divergence tests
task apply        # test, private backup, then apply
```

`task up` and `task deploy` apply this machine's configuration. This repository
owns no daemons or infrastructure: `task down` retains the configuration and
reports that there are no project services to stop. Existing application
sessions are not restarted. `task build` runs tests and a dry run.

After making source edits, review and commit them locally. Publish changes to
GitHub explicitly. On the other machine, `task sync` requires clean source and
installed state, checks out no branches, and only fast-forwards `main`. It
refuses divergence and unpublished local commits. Then use `task preview` and
`task apply`. Avoid `chezmoi update` here: it combines a rebase and application.
A source edit made through another working copy still needs to be previewed
against the destination before applying.

## Machine preferences

GitHub is authoritative for portable defaults and authored workflows. Keep
machine-specific overrides in **unmanaged**
`~/.config/chezmoi/machine.json` (permissions `0600`):

```json
{
  "git": { "name": "Your Name", "email": "you@example.com" },
  "codespace": "your-optional-codespace-name",
  "claudeSettings": { "effortLevel": "high" }
}
```

Claude settings merge recursively into `.chezmoitemplates/` defaults; arrays and
scalar values replace the corresponding default. Use the smallest overrides needed.
Absent profile keys use shared defaults. Remove a key from the shared defaults
if it should exist only on selected machines. Legacy chezmoi `gitName/gitEmail`
data remain supported when the profile does not supply identity.

Herdr uses one shared configuration from `.chezmoitemplates/herdr.json` on every
machine, including the `preview` update channel. Legacy `herdr` keys in a machine
profile are ignored and can be removed. Applying dotfiles does not upgrade the
installed binary or restart Herdr; binary installation is a separate operation.

For separate work and personal commit identities, Git 2.36+ can select an
identity by repository directory or remote URL. Add these optional fields to
the private machine profile's `git` object:

```json
{
  "name": "Your Name",
  "email": "personal@example.com",
  "workEmail": "you@company.example",
  "workDirectories": ["~/code/work/"],
  "workRemotePatterns": [
    "https://github.com/work-org/**",
    "git@github.com:work-org/**",
    "ssh://git@github.com/work-org/**"
  ],
  "personalRemotePatterns": [
    "https://github.com/personal-owner/**",
    "git@github.com:personal-owner/**",
    "ssh://git@github.com/personal-owner/**"
  ]
}
```

`email` is the default/personal identity. `workEmail` overrides it in matching
work directories (including linked worktrees) or repositories with a matching
remote. Use the physical directory path if a work directory has symlink aliases.
Personal remote rules run last, so a personal repository can live in a
work directory. Git checks every remote, including forks and upstreams; if both
work and personal patterns match, personal wins. Omitted rules do nothing, and
an omitted `workEmail` falls back to the default email.

The template generates `.gitconfig` and identity-only includes under
`~/.config/git/`. Repository-local `user.name`/`user.email` and Git author/committer
environment variables still take precedence. Inspect with `git var GIT_AUTHOR_IDENT`
and `git config --show-origin --get user.email`. These rules affect future commits;
they do not rewrite history or change GitHub authentication.

Claude's current runtime `model` is read from the selected destination and
preserved on apply. A profile model is a fallback when installing on a new
machine. Invalid profile or installed Claude JSON stops rendering. Codex's
runtime config, credentials, trust state, histories, third-party skills and
plugins remain unmanaged. Never bulk-add those directories.

Git's `.gitignore` also excludes raw and chezmoi-encoded credentials, private
machine profiles, host shell overrides, and recovery archives if they are
accidentally copied into the source checkout. `task test` checks this with a real
`git add --all` and verifies that intended source files and templates remain
trackable. These rules do not inspect file contents, remove previously tracked
files, or prevent `git add --force`. `.chezmoiignore` and the `private_` filename
prefix do not provide Git publication protection.

`csalive [name]` accepts an explicit Codespace, then `DOTFILES_CODESPACE`, then
the optional machine profile default. It refuses to guess when none is set.
The optional `~/.local/bin/herdr-shell.zsh` greeting and its helper programs are
machine-local dependencies; they are not installed by this repository.

Put other host-only shell additions in `~/.zshrc.local`. The shared zsh config
sources this optional file before syntax highlighting. It is deliberately
unmanaged and included in `task backup`; keep private paths and host-specific
startup commands there instead of editing the installed `.zshrc`.

`task backup` saves source (including local edits), Git history, installed
managed files and the machine profile under
`~/.local/state/dotfiles/backups/<timestamp>/`. These private archives include
sensitive local data and must never be committed. Archives are read back and
checksummed, and the Git bundle is verified. Symlink topology is retained in
`installed.tar.gz`; `machine-config.tar.gz` separately preserves the resolved
private preferences, including symlinked profile files. For recovery, inspect the
manifest, restore chosen files from `installed.tar.gz`, and recover source and
history separately. Do not extract an entire backup blindly over your home.

Retired desktop-environment settings, cswap services, private SSH drop-ins and
private lint helpers remain installed but unmanaged. Retirement from the
source repository does not delete their live files.

Neovim plugin declarations are shared. Lazy's generated
`~/.config/nvim/lazy-lock.json` stays machine-local: startup can rewrite it from
installed plugin commits. `task backup` includes it for recovery. This preserves
each host's installed plugin versions; matching plugin versions across machines
would require a separate, deliberate plugin restore/update.
