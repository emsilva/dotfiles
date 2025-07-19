# Integration Tests

This directory contains Docker-based integration tests that simulate real OS environments to test the dotfiles installation.

## Prerequisites

- Docker installed and running
- At least 2GB of free disk space for Docker images

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
make integration-test-alpine          # Alpine (unsupported OS) test
```

Clean up Docker images:
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

### Alpine Linux (Dockerfile.alpine)
- **Purpose**: Test unsupported OS handling
- **Expected**: Should fail gracefully with proper error message
- **Validates**: Error handling, OS detection edge cases

## Test Process

Each test:
1. **Builds** a Docker image with the target OS
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
docker build -f integration-tests/Dockerfile.ubuntu -t dotfiles-test-ubuntu .

# Run interactively
docker run -it dotfiles-test-ubuntu bash

# Inside the container, run:
./install.sh
./integration-tests/validate.sh

# Inspect the results
ls -la ~/.vimrc ~/.zshrc ~/.gitconfig
cat ~/.gitconfig
```

## Troubleshooting

**Build fails with permission errors:**
- Ensure Docker daemon is running
- Try: `sudo usermod -aG docker $USER` (then log out/in)

**Tests timeout:**
- Increase timeout: `make integration-test TIMEOUT=600`
- Check Docker resources (CPU/memory limits)

**Validation fails:**
- Check container logs: `docker logs <container_id>`
- Run interactively to debug: `docker run -it dotfiles-test-ubuntu bash`

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
  services:
    - docker:dind
```