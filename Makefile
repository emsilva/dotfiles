TESTS ?= test
.PHONY: test

test:
	bats $(TESTS)
