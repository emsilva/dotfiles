# Integration Tests

This directory contains Podman-based integration tests that simulate real OS environments to test the dotfiles installation.

## Prerequisites

- Podman installed and running
- At least 2GB of free disk space for Podman images

## Quick Start

Run all integration tests:
```bash
make integration-test
```

Or run individual tests:
```bash
make integration-test-ubuntu          # Ubuntu 22.04 full test
make integration-test-ubuntu-minimal  # Ubuntu 20.04 minimal test  
make integration-test-macos-sim       # macOS simulation test
```

Clean up Podman images:
```bash
make integration-test-clean
```

## Test Environments

### Ubuntu 22.04 (Dockerfile.ubuntu)
- **Purpose**: Test full Ubuntu installation with most packages pre-installed
- **Expected**: Should pass completely
- **Validates**: Package installation, symlink creation, git config substitution

### Ubuntu 20.04 Minimal (Dockerfile.ubuntu-minimal)
- **Purpose**: Test installation on minimal Ubuntu with only basic packages
- **Expected**: Should pass, demonstrates robustness
- **Validates**: Dependency handling, error recovery

### macOS Simulation (Dockerfile.macos-sim)
- **Purpose**: Test macOS behavior using mocked commands on Linux
- **Expected**: Should pass with mock brew/defaults commands
- **Validates**: OS detection, macOS-specific script logic


## Test Process

Each test:
1. **Builds** a Podman image with the target OS
2. **Copies** the dotfiles repository into the container
3. **Runs** `./install.sh` to perform installation
4. **Executes** `./integration-tests/validate.sh` for post-installation validation
5. **Reports** success/failure with detailed logs

## Validation Checks

The validation script (`validate.sh`) verifies:

- ✅ Symlinks created correctly
- ✅ Symlinks point to dotfiles directory
- ✅ Git configuration substituted with environment variables
- ✅ Required directories created (~/org, ~/code/work)
- ✅ Config directories exist (~/.config, ~/.local/share)
- ✅ File contents are non-empty
- ✅ Basic commands work (git, vim)
- ✅ Environment variables are set correctly

## Manual Testing

To run a test manually and inspect the container:

```bash
# Build the image
podman build -f integration-tests/Dockerfile.ubuntu -t dotfiles-test-ubuntu .

# Run interactively
podman run -it dotfiles-test-ubuntu bash

# Inside the container, run:
./install.sh
./integration-tests/validate.sh

# Inspect the results
ls -la ~/.vimrc ~/.zshrc ~/.gitconfig
cat ~/.gitconfig
```

## Troubleshooting

**Build fails with permission errors:**
- Ensure Podman is properly configured for rootless operation
- Try: `podman system migrate` to update configuration

**Tests timeout:**
- Increase timeout: `make integration-test TIMEOUT=600`
- Check Podman resources (CPU/memory limits)

**Validation fails:**
- Check container logs: `podman logs <container_id>`
- Run interactively to debug: `podman run -it dotfiles-test-ubuntu bash

## Adding New Tests

To add a new test environment:

1. Create `Dockerfile.newtest` in this directory
2. Add test configuration to `run-tests.sh` TESTS array
3. Add Makefile target for individual test
4. Update this documentation

## CI/CD Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Run Integration Tests
  run: make integration-test
```

```yaml
# GitLab CI example
integration-test:
  script:
    - make integration-test
  variables:
    CONTAINER_ENGINE: podman
```