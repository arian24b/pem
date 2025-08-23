#!/usr/bin/env python3
"""Release script for PEM project using UV best practices."""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    logger.info(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=False)


def check_environment() -> None:
    """Check if the environment is ready for release."""
    logger.info("🔍 Checking release environment...")

    # Check if we're in the project root
    if not Path("pyproject.toml").exists():
        logger.error("❌ pyproject.toml not found. Run this script from the project root.")
        sys.exit(1)

    # Check if UV is available
    try:
        run_command(["uv", "--version"])
        logger.info("  ✅ UV is available")
    except subprocess.CalledProcessError:
        logger.exception("  ❌ UV is not available")
        sys.exit(1)

    # Check if Git is clean
    try:
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        if result.stdout.strip():
            logger.warning("⚠️ Git working directory is not clean")
            logger.info("   Uncommitted changes found. Consider committing first.")
        else:
            logger.info("  ✅ Git working directory is clean")
    except subprocess.CalledProcessError:
        logger.warning("⚠️ Git status check failed")


def run_tests() -> None:
    """Run the test suite."""
    logger.info("🧪 Running test suite...")

    try:
        run_command(["uv", "run", "--group", "dev", "pytest", "--cov=pem", "--cov-report=term-missing"])
        logger.info("  ✅ All tests passed")
    except subprocess.CalledProcessError:
        logger.exception("  ❌ Tests failed")
        sys.exit(1)


def run_linting() -> None:
    """Run code quality checks."""
    logger.info("🔍 Running code quality checks...")

    # Run ruff for linting and formatting
    try:
        run_command(["uv", "run", "--group", "dev", "ruff", "check", "pem/"])
        logger.info("  ✅ Ruff linting passed")
    except subprocess.CalledProcessError:
        logger.exception("  ❌ Ruff linting failed")
        sys.exit(1)

    try:
        run_command(["uv", "run", "--group", "dev", "ruff", "format", "--check", "pem/"])
        logger.info("  ✅ Ruff formatting check passed")
    except subprocess.CalledProcessError:
        logger.exception("  ❌ Ruff formatting check failed")
        sys.exit(1)

    # Run mypy for type checking
    try:
        run_command(["uv", "run", "--group", "dev", "mypy", "pem/"])
        logger.info("  ✅ MyPy type checking passed")
    except subprocess.CalledProcessError:
        logger.exception("  ❌ MyPy type checking failed")
        sys.exit(1)


def build_package() -> None:
    """Build the Python package."""
    logger.info("📦 Building package...")

    try:
        run_command(["uv", "build"])
        logger.info("  ✅ Package built successfully")
    except subprocess.CalledProcessError:
        logger.exception("  ❌ Package build failed")
        sys.exit(1)


def build_binary() -> None:
    """Build the standalone binary."""
    logger.info("🔧 Building standalone binary...")

    try:
        run_command(["python", "scripts/build_binary.py"])
        logger.info("  ✅ Binary built successfully")
    except subprocess.CalledProcessError:
        logger.exception("  ❌ Binary build failed")
        sys.exit(1)


def publish_package(test_pypi: bool = False, token: str | None = None) -> None:
    """Publish the package to PyPI."""
    repository = "Test PyPI" if test_pypi else "PyPI"
    logger.info(f"🚀 Publishing package to {repository}...")

    cmd = ["uv", "publish"]

    if test_pypi:
        cmd.extend(["--repository-url", "https://test.pypi.org/legacy/"])

    if token:
        cmd.extend(["--token", token])
    else:
        logger.info("  No token provided. You'll be prompted for credentials.")

    try:
        run_command(cmd)
        logger.info(f"  ✅ Package published to {repository} successfully")
    except subprocess.CalledProcessError:
        logger.exception(f"  ❌ Package publication to {repository} failed")
        sys.exit(1)


def create_github_release() -> None:
    """Create a GitHub release (requires gh CLI)."""
    logger.info("📝 Creating GitHub release...")

    try:
        # Get the current version from pyproject.toml
        result = subprocess.run(
            ["python", "-c", "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"],
            capture_output=True,
            text=True,
            check=True,
        )
        version = result.stdout.strip()

        # Create GitHub release
        run_command(
            [
                "gh",
                "release",
                "create",
                f"v{version}",
                "--title",
                f"Release v{version}",
                "--notes",
                f"Release version {version}",
                "./dist/pem",  # Attach the binary
            ],
        )
        logger.info(f"  ✅ GitHub release v{version} created successfully")

    except subprocess.CalledProcessError as e:
        logger.exception(f"  ❌ GitHub release creation failed: {e}")
        logger.info("  💡 Make sure you have 'gh' CLI installed and authenticated")


def main() -> None:
    """Main release function."""
    parser = argparse.ArgumentParser(description="Release PEM project")
    parser.add_argument("--test-pypi", action="store_true", help="Publish to Test PyPI instead of PyPI")
    parser.add_argument("--token", help="PyPI API token")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--skip-lint", action="store_true", help="Skip linting checks")
    parser.add_argument("--skip-build", action="store_true", help="Skip building")
    parser.add_argument("--skip-publish", action="store_true", help="Skip publishing")
    parser.add_argument("--skip-github", action="store_true", help="Skip GitHub release")
    parser.add_argument("--build-only", action="store_true", help="Only build, don't publish")

    args = parser.parse_args()

    logger.info("🚀 Starting PEM release process...")

    try:
        # Environment checks
        check_environment()

        # Quality assurance
        if not args.skip_tests:
            run_tests()

        if not args.skip_lint:
            run_linting()

        # Building
        if not args.skip_build:
            build_package()
            build_binary()

        # Publishing (if not build-only mode)
        if not args.build_only and not args.skip_publish:
            publish_package(test_pypi=args.test_pypi, token=args.token)

        # GitHub release
        if not args.build_only and not args.skip_github:
            create_github_release()

        logger.info("🎉 Release process completed successfully!")

    except KeyboardInterrupt:
        logger.info("⚠️ Release process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ Release process failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
