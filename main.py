import sys
import os

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from src.ui.main_window import MainWindow
from src.db.database import Database


def main():
    os.makedirs("uploads", exist_ok=True)
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
