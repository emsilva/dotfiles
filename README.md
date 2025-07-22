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
./install.sh
```

## Updating Your Dotfiles

After making changes to your dotfiles, use the update script to commit and push changes:

```bash
cd ~/dotfiles
./update.sh
```

### AI-Enhanced Commit Messages

For more intelligent commit messages, set an OpenAI API key:

```bash
export OPENAI_API_KEY="your-api-key"
./update.sh
```

The update script automatically:
- Stages all changes
- Analyzes files to generate contextual commit messages
- Uses AI for complex changes (if API key provided)
- Pushes to remote repository

**Example commit messages:**
- Config changes: "Update .zshrc configuration"
- Script improvements: "Improve scripts/ubuntu.sh functionality"
- New tests: "Add test coverage for recent changes"

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
├── install.sh           # Main installation script
├── update.sh            # Update and commit script
├── packages.yml         # Package definitions
├── .env.example         # Environment variable template
├── dotfiles/            # Actual dotfiles
│   ├── .vimrc
│   ├── .zshrc
│   ├── .gitconfig
│   └── .config/
├── scripts/             # Platform-specific scripts
│   ├── macos.sh        # macOS setup
│   └── ubuntu.sh       # Ubuntu setup
└── README.md
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
