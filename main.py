import sys
import os

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pyqtgraph as pg

# Configure pyqtgraph before creating QApplication
pg.setConfigOption("background", "#1a1a2e")
pg.setConfigOption("foreground", "#cdd6f4")
pg.setConfigOptions(antialias=False)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ui.main_window import MainWindow


def main():
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("AI 音檔分割工具")
    app.setOrganizationName("AudioCutterAI")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
