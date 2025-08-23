#!/usr/bin/env python3
"""Entry point for PEM binary builds.
This module serves as the entry point for PyInstaller builds.
"""

import os
import sys

# Add the current directory to Python path to resolve imports
if hasattr(sys, "_MEIPASS"):
    # Running as PyInstaller bundle
    sys.path.insert(0, sys._MEIPASS)
else:
    # Running as regular Python script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)

if __name__ == "__main__":
    try:
        from pem.cli import run

        run()
    except ImportError:
        # Fallback for when running as installed package
        import pem.cli

        pem.cli.run()
