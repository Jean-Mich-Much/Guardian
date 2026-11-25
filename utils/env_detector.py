"""
Détection du système d'exploitation et de l'environnement graphique.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def detect_environment() -> dict:
    """Détermine le module principal adapté à l'ordinateur."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()

    if sys.platform == "win32":
        return {
            "platform": "windows",
            "desktop": desktop or "windows",
            "session": session or "native",
            "module": "main_win_11",
        }

    if "kde" in desktop or "plasma" in desktop:
        if "wayland" in session:
            return {
                "platform": "linux",
                "desktop": "kde",
                "session": "wayland",
                "module": "main_wayland_kde",
            }

    if "gnome" in desktop:
        if "wayland" in session:
            return {
                "platform": "linux",
                "desktop": "gnome",
                "session": "wayland",
                "module": "main_wayland_gnome",
            }

    return {
        "platform": "linux",
        "desktop": desktop or "linux",
        "session": session or "x11",
        "module": "main_wayland_gnome" if "wayland" in session else "main",
    }
