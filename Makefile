TESTS ?= test
.PHONY: test integration-test integration-test-ubuntu integration-test-macos-sim integration-test-alpine integration-test-clean help

test:
	bats $(TESTS)

integration-test:
	@echo "Running comprehensive integration tests..."
	./integration-tests/run-tests.sh

integration-test-ubuntu:
	@echo "Running Ubuntu integration test..."
	podman build -f integration-tests/Dockerfile.ubuntu -t dotfiles-test-ubuntu .
	podman run --rm dotfiles-test-ubuntu

integration-test-ubuntu-minimal:
	@echo "Running Ubuntu minimal integration test..."
	podman build -f integration-tests/Dockerfile.ubuntu-minimal -t dotfiles-test-ubuntu-minimal .
	podman run --rm dotfiles-test-ubuntu-minimal

integration-test-macos-sim:
	@echo "Running macOS simulation integration test..."
	podman build -f integration-tests/Dockerfile.macos-sim -t dotfiles-test-macos-sim .
	podman run --rm dotfiles-test-macos-sim

integration-test-alpine:
	@echo "Running Alpine (unsupported OS) integration test..."
	podman build -f integration-tests/Dockerfile.alpine -t dotfiles-test-alpine .
	podman run --rm dotfiles-test-alpine || echo "Expected failure for unsupported OS"

integration-test-clean:
	@echo "Cleaning up integration test Podman images..."
	podman rmi -f $$(podman images "dotfiles-test-*" -q) 2>/dev/null || true

help:
	@echo "Available targets:"
	@echo "  test                       - Run unit tests with bats"
	@echo "  integration-test           - Run all integration tests (requires Docker)"
	@echo "  integration-test-ubuntu    - Run Ubuntu integration test only"
	@echo "  integration-test-ubuntu-minimal - Run Ubuntu minimal test only"
	@echo "  integration-test-macos-sim - Run macOS simulation test only"
	@echo "  integration-test-alpine    - Run Alpine (unsupported) test only"
	@echo "  integration-test-clean     - Clean up Podman images"
	@echo "  help                       - Show this help message"
	@echo ""
	@echo "Prerequisites for integration tests:"
	@echo "  - Podman installed and running"
	@echo "  - Run './integration-tests/verify-setup.sh' to check setup"
