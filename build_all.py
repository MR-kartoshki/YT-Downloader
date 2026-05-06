#!/usr/bin/env python3
"""
YT Downloader - Multi-Platform Build Script
Builds executables for Windows, Linux (via Docker), and provides macOS instructions.
"""

import subprocess
import sys
import shutil
import platform
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
            print(f"FAILED\n{result.stderr}")
            return False
    except Exception as e:
        print(f"FAILED\n{e}")
        return False


def get_icon_arg() -> list[str]:
    """Return icon arguments for PyInstaller."""
    ico = Path("image.ico")
    if not ico.exists():
        return []

    system = platform.system()
    if system == "Darwin":
        icns = Path("image.icns")
        if not icns.exists():
            try:
                from PIL import Image
                img = Image.open(ico).convert("RGBA")
                img.save(str(icns))
                print(f"  Converted image.ico → image.icns")
            except Exception as e:
                print(f"  Warning: icon conversion failed ({e})")
                return []
        return ["--icon", str(icns)]

    return ["--icon", str(ico)]


def build_platform(target_platform):
    """Build executable for the specified platform."""
    print(f"\n{'=' * 60}")
    print(f"Building for {target_platform}")
    print(f"{'=' * 60}")

    # Check Python version
    if sys.version_info < (3, 11):
        print(f"ERROR: Python 3.11+ required (you have {sys.version_info.major}.{sys.version_info.minor})")
        return False

    # Check dependencies
    print("\nChecking dependencies...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", "pyinstaller"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Installing dependencies...")
        if not run_command(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            "Installing packages",
        ):
            print("ERROR: Failed to install dependencies")
            return False

    # Determine build settings
    if target_platform == "macos":
        bundle_mode = "--onedir"
        binary_name = "ytdownloader.app"
    elif target_platform == "windows":
        bundle_mode = "--onefile"
        binary_name = "ytdownloader.exe"
    else:  # linux
        bundle_mode = "--onefile"
        binary_name = "ytdownloader"

    # Build
    print("\nBuilding executable...")
    print("(This will take 2-5 minutes)\n")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "main.py",
        bundle_mode,
        "--windowed",
        "-y",
        "--name", "ytdownloader",
        "--add-data", "image.ico:.",
        "--collect-all", "requests",
        "--collect-all", "certifi",
        "--collect-all", "yt_dlp",
        "--hidden-import=yt_dlp",
        "--hidden-import=yt_dlp.extractor",
        "--hidden-import=yt_dlp.postprocessor",
    ] + get_icon_arg()

    if not run_command(cmd, "Running PyInstaller"):
        print("ERROR: Build failed")
        return False

    # Cleanup
    print("\nCleaning up build artifacts...")
    for item in ["build", "__pycache__", "*.spec"]:
        if "*" in item:
            for p in Path(".").glob(item):
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
        else:
            shutil.rmtree(item, ignore_errors=True)

    # Find output
    candidates = [
        Path("dist/ytdownloader.exe"),
        Path("dist/ytdownloader.app"),
        Path("dist/ytdownloader"),
    ]
    output = next((p for p in candidates if p.exists()), None)

    if output:
        print(f"\nSUCCESS: {target_platform.upper()} build complete")
        print(f"Output: {output.resolve()}")
        return True
    else:
        print(f"\nERROR: Build succeeded but output not found")
        return False


def check_docker():
    """Check if Docker is available."""
    result = subprocess.run(
        ["docker", "--version"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def build_linux_docker():
    """Build Linux executable using Docker."""
    print(f"\n{'=' * 60}")
    print("Building for Linux (via Docker)")
    print(f"{'=' * 60}")

    if not check_docker():
        print("\nWARNING: Docker is not installed or not available")
        print("Cannot build Linux executable without Docker")
        print("To install Docker, visit: https://www.docker.com/products/docker-desktop")
        return False

    print("\nPreparing Docker build...")

    # Create a simple Dockerfile
    dockerfile_content = """FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN python -m pip install --no-cache-dir -r requirements.txt
RUN python build.py
"""

    dockerfile_path = Path("Dockerfile.build")
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)

    # Build Docker image
    if not run_command(
        ["docker", "build", "-f", "Dockerfile.build", "-t", "ytdownloader-linux-build", "."],
        "Building Docker image"
    ):
        dockerfile_path.unlink()
        return False

    # Run build in Docker
    print("\nRunning build in Docker container...")
    if not run_command(
        ["docker", "run", "--rm", "-v", f"{Path('.').resolve()}:/app", "ytdownloader-linux-build"],
        "Running build"
    ):
        dockerfile_path.unlink()
        return False

    # Cleanup
    dockerfile_path.unlink()
    print("\nSUCCESS: Linux build complete")
    return True


def main():
    print("\n" + "=" * 60)
    print("YT Downloader - Multi-Platform Build Script")
    print("=" * 60)

    current_system = platform.system()

    # Determine which platforms to build
    platforms_to_build = []

    print(f"\nCurrent system: {current_system}")
    print("\nBuild options:")
    print("1. Current platform only (fastest)")
    print("2. Windows + Linux (requires Docker for Linux)")
    print("3. All platforms (Windows, Linux, macOS - requires Mac for macOS)")

    choice = input("\nSelect build option (1-3, default: 1): ").strip() or "1"

    if choice == "1":
        if current_system == "Windows":
            platforms_to_build = ["windows"]
        elif current_system == "Darwin":
            platforms_to_build = ["macos"]
        else:
            platforms_to_build = ["linux"]
    elif choice == "2":
        platforms_to_build = ["windows", "linux"]
    elif choice == "3":
        platforms_to_build = ["windows", "linux", "macos"]
    else:
        print("Invalid choice")
        sys.exit(1)

    # Build each platform
    results = {}

    for platform_target in platforms_to_build:
        if platform_target == "linux" and current_system != "Linux":
            if platform_target in ["windows", "linux"]:
                success = build_linux_docker()
            else:
                print(f"\nSkipping {platform_target}: Not available on {current_system}")
                print("To build for this platform, use a machine with that OS or GitHub Actions")
                success = None
        elif platform_target == "macos" and current_system != "Darwin":
            print(f"\nSkipping {platform_target}: macOS builds require a Mac machine")
            print("To build for macOS, use a Mac or GitHub Actions workflow")
            success = None
        else:
            success = build_platform(platform_target)

        results[platform_target] = success

    # Summary
    print(f"\n{'=' * 60}")
    print("Build Summary")
    print(f"{'=' * 60}")
    for platform_target, success in results.items():
        status = "SUCCESS" if success else ("SKIPPED" if success is None else "FAILED")
        print(f"{platform_target.upper():10} {status}")

    print(f"\n{'=' * 60}")
    print("\nFor automated multi-platform releases, use GitHub Actions:")
    print("  1. Push a version tag: git tag v1.0.0 && git push origin v1.0.0")
    print("  2. GitHub Actions will automatically build for all platforms")
    print("  3. Releases will appear on: https://github.com/YourUsername/YT-Downloader/releases")
    print()

    # Exit with error if any builds failed
    if any(v is False for v in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBuild cancelled")
        sys.exit(1)
