"""Central module for resolving paths to static assets."""
import os

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
STATIC  = os.path.join(_ROOT, "static")
ICONS   = os.path.join(STATIC, "icons")
IMAGES  = os.path.join(STATIC, "images")
FONTS   = os.path.join(STATIC, "fonts")

def icon(name: str) -> str:
    """Return absolute path to icons/name.svg"""
    return os.path.join(ICONS, f"{name}.svg")

def image(name: str) -> str:
    return os.path.join(IMAGES, name)

def font(name: str) -> str:
    return os.path.join(FONTS, name)
