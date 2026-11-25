"""
Vérifications rassurantes avant une copie de souvenirs.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import psutil


def get_battery_status() -> dict:
    """Retourne l'état de la batterie sans afficher de termes techniques."""
    battery = psutil.sensors_battery()
    if battery is None:
        return {"available": False, "percent": None, "plugged": None, "warning": False}

    percent = int(battery.percent)
    return {
        "available": True,
        "percent": percent,
        "plugged": bool(battery.power_plugged),
        "warning": percent < 20 and not battery.power_plugged,
    }


def prevent_sleep() -> object | None:
    """Demande au système de ne pas mettre l'ordinateur en veille pendant la copie."""
    if sys.platform == "win32":
        try:
            import ctypes

            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_DISPLAY_REQUIRED = 0x00000002
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
            return "windows"
        except Exception:
            return None
    return "system"


def allow_sleep(previous_state: object | None) -> None:
    """Restaure le comportement normal de veille lorsque possible."""
    if previous_state == "windows" and sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        except Exception:
            pass


def inspect_large_files(files: Iterable[dict], filesystem: str = "") -> list[dict]:
    """Signale les fichiers qui dépassent la limite historique des supports courants."""
    limit = 4 * 1024 * 1024 * 1024
    warnings: list[dict] = []
    for file_info in files:
        if int(file_info.get("size", 0)) > limit:
            warnings.append(
                {
                    "path": file_info.get("path", ""),
                    "size": int(file_info.get("size", 0)),
                    "message": "Ce fichier est très volumineux et peut nécessiter un autre support.",
                }
            )
    return warnings


def get_system_status(largest_files: Iterable[dict] = (), filesystem: str = "") -> dict:
    """Regroupe les points de vigilance avant la copie."""
    return {
        "battery": get_battery_status(),
        "large_file_warnings": inspect_large_files(largest_files, filesystem),
        "platform": sys.platform,
    }