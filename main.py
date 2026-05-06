import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from core.dependency_checker import check_and_install_dependencies
from core.state import AppState
from ui_main import MainWindow


def main():
    # Check/install missing dependencies before starting GUI
    if not check_and_install_dependencies():
        print("❌ Failed to install dependencies. Exiting.")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("YT Downloader")
    app.setApplicationVersion("1.0.0")

    state = AppState()
    window = MainWindow(state)
    window.show()

    # Fix 5: defer bootstrap until the event loop is running so the UI paints first
    QTimer.singleShot(0, window.start_bootstrap)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
