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

Run comprehensive integration tests using Docker containers that simulate real OS environments:

```bash
# Verify setup first
./integration-tests/verify-setup.sh

# Run all integration tests
make integration-test

# Or run specific tests
make integration-test-ubuntu          # Ubuntu 22.04
make integration-test-ubuntu-minimal  # Ubuntu 20.04 minimal
make integration-test-macos-sim       # macOS simulation
make integration-test-alpine          # Unsupported OS test
```

**Prerequisites**: Docker installed and running

Integration tests validate:
- ✅ Complete installation process
- ✅ Cross-platform compatibility  
- ✅ Symlink creation and management
- ✅ Git configuration substitution
- ✅ Package installation workflows
- ✅ Error handling for unsupported systems

## Migration from Chezmoi

If you're migrating from the old chezmoi-based setup:

1. Backup your current dotfiles
2. Run the new installation script
3. Set your environment variables
4. Review and adjust any custom configurations

## Notes

- The installation is idempotent - you can run it multiple times safely
- Platform detection is automatic
- Services are configured appropriately for each platform
- All symlinks point to the repository, making it easy to track changes