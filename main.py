import sys
import os
import glob

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from src.ui.main_window import MainWindow
from src.db.database import Database


def clean_pyc_cache():
    """Clean .pyc cache to ensure fresh module imports."""
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
    # Clean cache before starting
    clean_pyc_cache()
    
    os.makedirs("workspace", exist_ok=True)
    os.makedirs(".cache", exist_ok=True)

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app.setApplicationName("Quadrogent")

    db = Database()
    window = MainWindow(db)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
