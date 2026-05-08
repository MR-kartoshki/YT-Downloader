#!/usr/bin/env python3
"""
YT Downloader - Build Script
Builds a standalone executable using PyInstaller
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
            print("OK")
            return True
        else:
            print("FAILED")
            if result.stderr:
                print(result.stderr)
            return False
    except Exception as e:
        print("FAILED")
        print(e)
        return False


def get_icon_arg() -> list[str]:
    """
    Return ['--icon', '<path>'] with a platform-appropriate icon file.
    On macOS, converts image.ico -> image.icns using Pillow.
    Returns [] if no icon is available.
    """
    ico = Path("image.ico")
    if not ico.exists():
        return []

    if sys.platform == "darwin":
        icns = Path("image.icns")
        if not icns.exists():
            try:
                from PIL import Image
                img = Image.open(ico).convert("RGBA")
                img.save(str(icns))
                print(f"  Converted image.ico -> image.icns (OK)")
            except Exception as e:
                print(f"  Warning: icon conversion failed ({e}), building without icon.")
                return []
        return ["--icon", str(icns)]

    return ["--icon", str(ico)]


def find_output() -> Path | None:
    """Return the built executable/app path, handling all platform variants."""
    candidates = [
        Path("dist/ytdownloader.exe"),   # Windows --onefile
        Path("dist/ytdownloader.app"),   # macOS --windowed
        Path("dist/ytdownloader"),       # Linux / macOS --onefile
    ]
    return next((p for p in candidates if p.exists()), None)


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

    # macOS requires --onedir for a proper .app bundle; --onefile + --windowed
    # is deprecated in PyInstaller 6 and will error in v7.
    bundle_mode = "--onedir" if sys.platform == "darwin" else "--onefile"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "main.py",
        bundle_mode,
        "--windowed",
        "-y",                  # overwrite existing dist/ output without prompting
        "--name", "ytdownloader",
        "--add-data", "image.ico" + (";" if sys.platform == "win32" else ":") + ".",
        "--collect-all", "requests",
        "--collect-all", "certifi",
        "--collect-all", "yt_dlp",
        "--hidden-import=yt_dlp",
        "--hidden-import=yt_dlp.extractor",
        "--hidden-import=yt_dlp.postprocessor",
    ] + get_icon_arg()

    if not run_command(cmd, "Running PyInstaller (creating single executable)"):
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
    output = find_output()
    if output:
        print("\n" + "=" * 50)
        print("SUCCESS! Build complete")
        print("=" * 50)
        print(f"\nYour executable is ready at:")
        print(f"  {output.resolve()}")
        print()
    else:
        print("\nERROR: Build succeeded but output not found")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBuild cancelled")
        sys.exit(1)
