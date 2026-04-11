"""
icon_helper.py — loads heroicons SVG files as colored QIcons.

Icons live in <project_root>/icons/*.svg  (heroicons 2.2.0, MIT license).
Usage:
    icon = get_icon("plus", "#c8c8c8", size=16)
    button.setIcon(icon)
    button.setIconSize(QSize(16, 16))
"""
import os
from functools import lru_cache

from PyQt5.QtCore import Qt, QByteArray, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPainter

try:
    from PyQt5.QtSvg import QSvgRenderer
    _SVG_OK = True
except ImportError:
    _SVG_OK = False

from src.utils.static_paths import ICONS as _ICONS_DIR


@lru_cache(maxsize=128)
def get_icon(name: str, color: str = "#888888", size: int = 16) -> QIcon:
    """Return a QIcon for the named heroicon, tinted with *color*."""
    if not _SVG_OK:
        return QIcon()
    path = os.path.join(_ICONS_DIR, f"{name}.svg")
    if not os.path.exists(path):
        return QIcon()
    try:
        svg_data = open(path, encoding="utf-8").read()
        svg_data = svg_data.replace("currentColor", color)
        renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
        return QIcon(pix)
    except Exception:
        return QIcon()


def apply_icon(btn, name: str, color: str = "#888888", size: int = 15):
    """Convenience: set icon on a QPushButton."""
    icon = get_icon(name, color, size)
    if not icon.isNull():
        btn.setIcon(icon)
        btn.setIconSize(QSize(size, size))
