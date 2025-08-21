# Makefile for PEM project using UV best practices
.PHONY: help install dev-install test lint format build binary release clean

# Default target
help:
	@echo "PEM Project - Available commands:"
	@echo "  install      - Install the project and dependencies"
	@echo "  dev-install  - Install development dependencies"
	@echo "  test         - Run tests with coverage"
	@echo "  lint         - Run linting checks"
	@echo "  format       - Format code with ruff"
	@echo "  build        - Build Python package"
	@echo "  binary       - Build standalone binary"
	@echo "  release      - Run full release process"
	@echo "  clean        - Clean build artifacts"

# Install project and dependencies
install:
	uv sync

# Install development dependencies
dev-install:
	uv sync --group dev --group build --group release

# Run tests with coverage
test:
	uv run --group dev pytest --cov=pem --cov-report=term-missing --cov-report=html

# Run linting checks
lint:
	uv run --group dev ruff check pem/
	uv run --group dev mypy pem/

# Format code
format:
	uv run --group dev ruff format pem/

# Build Python package
build:
	uv build

# Build standalone binary
binary:
	python scripts/build_binary.py

# Run full release process
release:
	python scripts/release.py

# Release to test PyPI
test-release:
	python scripts/release.py --test-pypi

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf build_standalone/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Quick development workflow
dev: dev-install lint test

# CI/CD workflow
ci: install lint test build
