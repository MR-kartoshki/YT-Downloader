#!/usr/bin/env python3
"""
YT Downloader - Build Script
Builds a standalone .exe using PyInstaller
"""

import subprocess
import sys
import shutil
from pathlib import Path


def run_command(cmd, description):
    """Run a shell command and handle errors."""
    print(f"\n{description}...", end=" ", flush=True)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            print("✓")
            return True
        else:
            print(f"✗\n{result.stderr}")
            return False
    except Exception as e:
        print(f"✗\n{e}")
        return False


def main():
    print("\n" + "=" * 50)
    print("YT Downloader - Build Script")
    print("=" * 50)

    # Check Python version
    if sys.version_info < (3, 11):
        print(f"\nERROR: Python 3.11+ required (you have {sys.version_info.major}.{sys.version_info.minor})")
        sys.exit(1)

    # Check if PyInstaller is installed
    print("\nChecking dependencies...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", "pyinstaller"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Installing build dependencies (this may take a minute)...")
        if not run_command(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            "Installing packages",
        ):
            print("\nERROR: Failed to install dependencies")
            sys.exit(1)

    # Build
    print("\nBuilding executable...")
    print("(This will take 2-5 minutes on first build)\n")

    # Note: --onefile can't be used with .spec files, so we build directly from main.py
    if not run_command(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "main.py",
            "--onefile",
            "--windowed",
            "--name", "ytdownloader",
            "--icon", "image.ico",
            "--add-data", "image.ico:.",
            "--collect-all", "requests",
            "--collect-all", "certifi",
            "--collect-all", "yt_dlp",
            "--hidden-import=yt_dlp",
            "--hidden-import=yt_dlp.extractor",
            "--hidden-import=yt_dlp.postprocessor",
        ],
        "Running PyInstaller (creating single .exe file)",
    ):
        print("\nERROR: Build failed")
        sys.exit(1)

    # Cleanup
    print("\nCleaning up build artifacts...")
    for item in ["build", "__pycache__", "*.spec"]:
        if "*" in item:
            for p in Path(".").glob(item):
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
        else:
            shutil.rmtree(item, ignore_errors=True)

    # Success
    exe_path = Path("dist/ytdownloader/ytdownloader.exe")
    if exe_path.exists():
        print("\n" + "=" * 50)
        print("SUCCESS! Build complete ✓")
        print("=" * 50)
        print(f"\nYour executable is ready at:")
        print(f"  {exe_path.resolve()}")
        print(f"\nTo run it:")
        print(f"  1. Open the dist/ytdownloader/ folder")
        print(f"  2. Double-click ytdownloader.exe")
        print(f"\nTo share it:")
        print(f"  1. Copy the entire dist/ytdownloader/ folder")
        print(f"  2. Share with others")
        print(f"  3. They just need to double-click ytdownloader.exe")
        print()
    else:
        print("\nERROR: Build succeeded but exe not found")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBuild cancelled")
        sys.exit(1)
