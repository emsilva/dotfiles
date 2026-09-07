# Reconciliation policy

The shared line continues the existing public GitHub history. Private historical
commits and machine snapshots remain in private recovery archives, outside GitHub.

The publication cleanup remains in effect: desktop-environment rice, cswap
service activation, private SSH/lint configuration and third-party skill copies
are not restored to management. Existing installed files are retained.

Later authored ship and session-handoff updates are carried forward, including
the retirement of choosing-a-model. Independent shell additions are combined.
Herdr uses the Linux reference configuration on all machines, including colors,
workspace bindings and the preview update channel; machine-profile Herdr overrides
are ignored. Other applications' active models, permissions, notifications,
Git identity and unmanaged Codex state are preserved.

Migration validation must render against both actual machines, inspect the full
change, apply on the Linux desktop first, then verify the Mac. A fresh SSH login,
shell startup, configuration parsing, and installed-state comparison are required.
Graphical behavior and provider/model quality require separate checks and must
not be claimed from a format or shell test. Publishing the reviewed commit and
switching the active source checkouts to GitHub happen only after validation.

The real Linux Neovim startup check exposed Lazy's automatic lockfile rewrite
when missing plugins are installed. The generated lockfile is therefore owned
by Lazy, excluded from chezmoi management, and included in private backups.
Plugin declarations remain shared; no plugin downgrade is performed.
