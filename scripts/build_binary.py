#!/usr/bin/env python3
"""Build script for creating pem binaries using PyInstaller with UV best practices."""

import logging
import os
import shutil
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


def clean_build() -> None:
    """Clean previous build artifacts."""
    logger.info("🧹 Cleaning previous build artifacts...")
    paths_to_clean = ["build", "dist", "*.egg-info", "__pycache__", ".mypy_cache", ".pytest_cache"]

    for pattern in paths_to_clean:
        for path in Path().glob(pattern):
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                    logger.info(f"  Removed directory: {path}")
                else:
                    os.remove(path)
                    logger.info(f"  Removed file: {path}")


def check_dependencies() -> None:
    """Check if required dependencies are available."""
    logger.info("🔍 Checking dependencies...")

    # Check if we're in a UV environment
    try:
        run_command(["uv", "--version"])
        logger.info("  ✅ UV is available")
    except subprocess.CalledProcessError:
        logger.exception("  ❌ UV is not available")
        sys.exit(1)

    # Check if PyInstaller is available in build group
    try:
        run_command(["uv", "run", "--group", "build", "pyinstaller", "--version"])
        logger.info("  ✅ PyInstaller is available")
    except subprocess.CalledProcessError:
        logger.info("  ❌ PyInstaller is not available. Installing build dependencies...")
        run_command(["uv", "sync", "--group", "build"])


def prepare_standalone_files() -> Path:
    """Prepare standalone files for binary creation."""
    logger.info("📦 Preparing standalone files...")

    # Copy modules to standalone location for PyInstaller
    standalone_dir = Path("./build_standalone")
    if standalone_dir.exists():
        shutil.rmtree(standalone_dir)
    standalone_dir.mkdir()

    # Copy pem package
    shutil.copytree("pem", standalone_dir / "pem")

    # Create standalone CLI
    cli_content = '''#!/usr/bin/env python3
"""Standalone entry point for PEM binary."""

import os
import sys

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from pem.cli import run
    run()
'''

    with open(standalone_dir / "cli_standalone.py", "w") as f:
        f.write(cli_content)

    return standalone_dir


def test_binary() -> None:
    """Test the created binary."""
    logger.info("🧪 Testing binary...")
    binary_path = Path("./dist/pem")

    if not binary_path.exists():
        logger.error("  ❌ Binary not found")
        return

    try:
        # Test help command - binary_path is controlled by us, so it's safe
        result = subprocess.run([str(binary_path), "--help"], capture_output=True, check=True, text=True)
        if "Usage:" in result.stdout:
            logger.info("  ✅ Binary help command works")
        else:
            logger.warning("  ⚠️ Binary help output unexpected")

        # Test status command - binary_path is controlled by us, so it's safe
        result = subprocess.run([str(binary_path), "status"], capture_output=True, check=False, text=True)
        logger.info("  ✅ Binary status command executed")

        logger.info(f"  📍 Binary location: {binary_path.absolute()}")

    except subprocess.CalledProcessError as e:
        logger.exception(f"  ❌ Binary test failed: {e}")
    except Exception as e:
        logger.exception(f"  ❌ Unexpected error during binary test: {e}")


def create_binary() -> None:
    """Create standalone binary using PyInstaller."""
    logger.info("🏗️ Creating standalone binary...")

    # Prepare standalone files
    standalone_dir = prepare_standalone_files()

    # Build command with comprehensive options for performance
    cmd = [
        "uv",
        "run",
        "--group",
        "build",
        "pyinstaller",
        "--onefile",  # Create a one-file bundled executable
        "--name",
        "pem",  # Name of the executable
        "--console",  # Console application
        "--clean",  # Clean PyInstaller cache
        "--noconfirm",  # Replace output directory without asking
        "--optimize",
        "2",  # Bytecode optimization level
        "--strip",  # Strip debug information (Unix only)
        "--distpath",
        "./dist",  # Output directory
        "--specpath",
        "./build",  # Spec file directory
        # Performance optimizations
        "--exclude-module",
        "tkinter",  # Exclude unused GUI modules
        "--exclude-module",
        "matplotlib",
        "--exclude-module",
        "numpy",
        "--exclude-module",
        "pandas",
        "--exclude-module",
        "PIL",
        "--exclude-module",
        "PyQt5",
        "--exclude-module",
        "PyQt6",
        "--exclude-module",
        "PySide2",
        "--exclude-module",
        "PySide6",
        "--exclude-module",
        "jupyter",
        "--exclude-module",
        "IPython",
        # Required hidden imports
        "--hidden-import",
        "aiosqlite",  # Required for database connectivity
        "--hidden-import",
        "sqlalchemy.dialects.sqlite.aiosqlite",
        "--hidden-import",
        "apscheduler.schedulers.asyncio",
        "--hidden-import",
        "apscheduler.executors.pool",
        "--hidden-import",
        "apscheduler.jobstores.memory",
        "--hidden-import",
        "apscheduler.jobstores.sqlalchemy",
        # Data files
        "--add-data",
        f"{standalone_dir / 'pem'}:pem",  # Include pem package
        str(standalone_dir / "cli_standalone.py"),  # Entry point
    ]

    try:
        result = run_command(cmd)
        if result.returncode == 0:
            logger.info("  ✅ Binary created successfully")
            test_binary()
        else:
            logger.error("  ❌ Binary creation failed")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.exception(f"  ❌ Binary creation failed: {e}")
        sys.exit(1)
    finally:
        # Cleanup standalone files
        if standalone_dir.exists():
            shutil.rmtree(standalone_dir)


def main() -> None:
    """Main build function."""
    logger.info("🚀 Starting PEM binary build process...")

    # Ensure we're in the project root
    if not Path("pyproject.toml").exists():
        logger.error("❌ pyproject.toml not found. Run this script from the project root.")
        sys.exit(1)

    try:
        clean_build()
        check_dependencies()
        create_binary()
        logger.info("🎉 Build process completed successfully!")
    except KeyboardInterrupt:
        logger.info("⚠️ Build process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ Build process failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
