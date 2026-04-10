import sys
import os
import glob

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from src.ui.main_window import MainWindow
from src.db.database import Database


def clean_pyc_cache():
    for pattern in ['**/*.pyc', '**/__pycache__']:
        for path in glob.glob(pattern, recursive=True):
            try:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path)
            except Exception:
                pass


def main():
    clean_pyc_cache()

    os.makedirs("workspace", exist_ok=True)
    os.makedirs(".cache", exist_ok=True)

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app.setApplicationName("Quadrogent")

    # Set window/taskbar icon (critical for KDE Plasma and other WMs)
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "logo.png")
    if os.path.exists(logo_path):
        app.setWindowIcon(QIcon(logo_path))

    db = Database()
    window = MainWindow(db)
    window.setWindowIcon(QIcon(logo_path) if os.path.exists(logo_path) else QIcon())
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
