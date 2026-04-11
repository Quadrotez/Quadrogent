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

    # Register and apply custom fonts
    from PyQt5.QtGui import QFontDatabase, QFont
    import glob as _glob
    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "fonts")
    for fp in sorted(_glob.glob(os.path.join(fonts_dir, "*.ttf"))):
        QFontDatabase.addApplicationFont(fp)
    # Set Roboto as the default application font
    app_font = QFont("Roboto", 12)
    app.setFont(app_font)

    # Set window/taskbar icon (critical for KDE Plasma and other WMs)
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "images", "logo.png")
    if os.path.exists(logo_path):
        app.setWindowIcon(QIcon(logo_path))

    db = Database()

    # Apply persisted theme before showing window
    from src.ui.theme import apply_theme
    apply_theme(app, db)
    window = MainWindow(db)
    window.setWindowIcon(QIcon(logo_path) if os.path.exists(logo_path) else QIcon())
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
