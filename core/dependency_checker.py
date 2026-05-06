import subprocess
import sys


REQUIRED_PACKAGES = {
    "PySide6": "PySide6",
    "yt_dlp": "yt-dlp",
    "requests": "requests",
}


def check_and_install_dependencies():
    """
    Check if all required packages are installed.
    If any are missing, auto-install them via pip.
    Returns True if all deps are available (or were just installed).
    Returns False if installation failed.
    """
    missing = {}
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            missing[import_name] = pip_name

    if not missing:
        return True

    print("\n⚠️  Missing required packages:", ", ".join(missing.values()))
    print("Installing via pip...\n")

    for import_name, pip_name in missing.items():
        try:
            print(f"Installing {pip_name}...", end=" ", flush=True)
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pip_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("✓")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed: {e}")
            return False
        except Exception as e:
            print(f"✗ Error: {e}")
            return False

    print("\n✓ All dependencies installed. Starting app...\n")
    return True
