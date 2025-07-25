# Cross-Platform Dotfiles

> 🔧 Simplified dotfiles that work on both macOS and Ubuntu with no external dependencies.

## Features

- **Cross-platform**: Works on macOS and Ubuntu
- **Simple**: No complex templating or external tools required
- **Environment-based**: Use environment variables for sensitive configuration
- **Package management**: Unified package definitions with platform-specific installation
- **Symlink-based**: Easy to understand and modify

## Quick Setup

```bash
git clone https://github.com/emsilva/dotfiles.git ~/dotfiles
cd ~/dotfiles
./dotfiles-install.sh
```

After installation, dotfiles management commands are available globally. The included `.zshrc` configuration automatically adds `~/.local/bin` to your PATH:

```bash
# Commands work from anywhere after installation
dotfiles-add ~/.config/starship.toml
dotfiles-status
dotfiles-sync
```

> **Note**: If you're not using the provided `.zshrc`, make sure `~/.local/bin` is in your PATH to access the global commands.

## Syncing Your Dotfiles

After making changes to your dotfiles, use the sync script to commit and push changes:

```bash
# Can be run from anywhere after installation
dotfiles-sync

# Or from the dotfiles directory
cd ~/dotfiles
./dotfiles-sync.sh
```

### AI-Enhanced Commit Messages

For more intelligent commit messages, set an OpenAI API key:

```bash
export OPENAI_API_KEY="your-api-key"
dotfiles-sync  # Can be run from anywhere
```

The sync script automatically:
- Stages all changes
- Analyzes files to generate contextual commit messages
- Uses AI for complex changes (if API key provided)
- Pushes to remote repository

**Example commit messages:**
- Config changes: "Update .zshrc configuration"
- Script improvements: "Improve scripts/ubuntu.sh functionality"
- New tests: "Add test coverage for recent changes"

## Managing Your Dotfiles

This system uses a **selective approach** - only files you explicitly add are managed.

### Adding Files to Management

```bash
# Add a single file (works from anywhere after installation)
dotfiles-add ~/.config/starship.toml

# Add a directory 
dotfiles-add ~/.config/nvim

# Preview changes without applying
dotfiles-add --dry-run ~/.vimrc

# Or use the full script path from dotfiles directory
./dotfiles-add.sh ~/.config/starship.toml
```

### Removing Files from Management

```bash
# Stop managing a file (restores original)
dotfiles-remove .config/starship.toml

# Keep a backup when removing
dotfiles-remove --keep-backup .vimrc

# Or from dotfiles directory
./dotfiles-remove.sh .config/starship.toml
```

### Viewing Managed Files

```bash
# List all managed files
dotfiles-list

# Show detailed information
dotfiles-list --verbose

# Check status of managed files
dotfiles-status

# Fix any symlink issues
dotfiles-status --fix

# Or from dotfiles directory
./dotfiles-list.sh
./dotfiles-status.sh
```

### Migration from Old System

If upgrading from the previous version:

```bash
# Migrate existing symlinks to new system (from dotfiles directory)
./dotfiles-migrate.sh

# Or run globally (if already installed)
dotfiles-migrate

# Preview migration changes
./dotfiles-migrate.sh --dry-run
```

## Configuration

### Environment Variables

Copy the example environment file and set your values:

```bash
cp .env.example .env.local
# Edit .env.local with your email addresses
```

Then source it in your shell:

```bash
# Add to your .bashrc or .zshrc
source ~/dotfiles/.env.local
```

### Git Configuration

The git configuration uses environment variables:
- `GIT_EMAIL_PERSONAL`: Your personal email address
- `GIT_EMAIL_WORK`: Your work email address

If not set, it defaults to GitHub noreply emails.

## Package Management

Packages are defined in `packages.yml` with platform-specific sections:

- **common**: Packages available on both platforms
- **macos**: macOS-specific Homebrew packages
- **ubuntu**: Ubuntu-specific apt packages

## Directory Structure

```
~/dotfiles/
├── dotfiles-install.sh  # Main installation script
├── dotfiles-sync.sh     # Sync and commit script
├── dotfiles-add.sh      # Add files to management
├── dotfiles-remove.sh   # Remove files from management
├── dotfiles-list.sh     # List managed files
├── dotfiles-status.sh   # Check symlink status
├── packages.yml         # Package definitions
├── .env.example         # Environment variable template
├── .dotfiles-manifest   # Tracks managed files
├── dotfiles/            # Actual dotfiles
│   ├── .vimrc
│   ├── .zshrc
│   ├── .gitconfig
│   └── .config/
├── scripts/             # Platform-specific scripts
│   ├── macos.sh        # macOS setup
│   └── ubuntu.sh       # Ubuntu setup
├── test/               # Unit tests
└── integration-tests/  # Container-based tests
```

## Platform-Specific Features

### macOS
- Homebrew package installation
- macOS defaults configuration
- iTerm2 setup
- Dock configuration
- Hot corners setup

### Ubuntu
- APT package installation
- Visual Studio Code installation
- Service configuration (systemd)
- fd symlink creation

## Testing

### Unit Tests

Run unit tests to ensure setup scripts work correctly:

```bash
make test
```

### Integration Tests

Run comprehensive integration tests using Podman containers that simulate real OS environments:

```bash
# Verify setup first
./integration-tests/verify-setup.sh

# Run all integration tests
make integration-test

# Or run specific tests
make integration-test-ubuntu          # Ubuntu 22.04
make integration-test-ubuntu-minimal  # Ubuntu 20.04 minimal
make integration-test-macos-sim       # macOS simulation
```

**Prerequisites**: Podman installed and running

Integration tests validate:
- ✅ Complete installation process
- ✅ Cross-platform compatibility  
- ✅ Symlink creation and management
- ✅ Git configuration substitution
- ✅ Package installation workflows
- ✅ Error handling for unsupported systems


## TODOs / Improvement Opportunities


### 🟡 Medium Priority (Enhancements)
- [ ] **Standardize Plugin Management**
  - [x] Consolidate all zsh plugins through oh-my-zsh (removed zplug dependency)
  - [ ] Review plugin conflicts and dependencies
  
- [x] **Fix Hardcoded Paths**
  - [x] Replace hardcoded Ruby gem paths in `.zshrc` with dynamic detection
  - [ ] Make Python/Node paths more flexible across versions
  
- [ ] **Improve Error Recovery**
  - [ ] Add backup mechanism for existing dotfiles before overwriting
  - [ ] Implement rollback functionality for failed installations
  - [ ] Better handling of partial installation failures

- [ ] **Enhanced User Experience**
  - [ ] Add interactive mode for selective component installation  
  - [ ] Implement progress bars for long-running operations
  - [ ] Add shell reload functionality post-installation

### 🟢 Low Priority (Nice to Have)
- [ ] **Advanced Features**
  - [ ] Profile management (work vs personal environments)
  - [ ] Update checker for dotfiles repository
  - [ ] Plugin architecture for extensibility
  - [ ] GUI configuration interface

- [ ] **Code Quality**
  - [x] Standardize indentation in `.vimrc` (completed)
  - [ ] Add package caching for faster reinstalls
  - [ ] Implement parallel package installation where safe

- [ ] **Security Enhancements**
  - [ ] Add GPG verification for downloaded packages
  - [ ] Implement checksum validation for critical downloads
  - [ ] Add security scanning for installed packages

- [ ] **Documentation**
  - [ ] Add troubleshooting guide for common issues
  - [ ] Create video walkthrough for setup process
  - [ ] Document advanced customization options

- [ ] **Testing**
  - [ ] Add performance benchmarks for installation time
  - [ ] Create tests for different Ubuntu versions (18.04, 20.04, 22.04)
  - [ ] Add macOS version compatibility testing

## Notes

- The installation is idempotent - you can run it multiple times safely
- Platform detection is automatic
- Services are configured appropriately for each platform
- All symlinks point to the repository, making it easy to track changes
