"""
Détection des supports de sauvegarde amovibles pour Guardian.
"""

from __future__ import annotations

import os
import platform
import sys
from fractions import Fraction
from pathlib import Path
from typing import Iterable

import psutil


def _windows_drive_type(path: str) -> int:
    """Demande à Windows le type du lecteur indiqué."""
    if sys.platform != "win32":
        return 0

    try:
        import ctypes

        return int(ctypes.windll.kernel32.GetDriveTypeW(path))
    except Exception:
        return 0


def _linux_removable_devices() -> set[str]:
    """Retourne les noms des périphériques amovibles visibles sous Linux."""
    removable: set[str] = set()
    sys_block = Path("/sys/block")

    if not sys_block.exists():
        return removable

    for device in sys_block.iterdir():
        try:
            if (device / "removable").read_text(encoding="utf-8").strip() != "1":
                continue
            for partition in device.iterdir():
                if partition.name.startswith(device.name):
                    removable.add(partition.name)
        except (OSError, UnicodeDecodeError):
            continue

    return removable


def _partition_is_removable(partition: psutil._common.sdiskpart) -> bool:
    """Détermine si une partition est amovible sur Windows ou Linux."""
    mountpoint = partition.mountpoint
    if sys.platform == "win32":
        return _windows_drive_type(mountpoint) == 2

    options = partition.opts.lower()
    removable_names = _linux_removable_devices()
    device_name = Path(partition.device).name
    return (
        "removable" in options
        or "media" in mountpoint.lower()
        or "mnt" in mountpoint.lower()
        or device_name in removable_names
    )


def detect_usb_devices() -> list[dict]:
    """Liste les supports amovibles utilisables avec leur espace disponible."""
    devices: list[dict] = []

    try:
        partitions: Iterable[psutil._common.sdiskpart] = psutil.disk_partitions(all=False)
    except Exception:
        partitions = ()

    for partition in partitions:
        try:
            if not _partition_is_removable(partition):
                continue

            mountpoint = partition.mountpoint
            if not mountpoint or not os.path.isdir(mountpoint):
                continue

            usage = psutil.disk_usage(mountpoint)
            devices.append(
                {
                    "mountpoint": str(Path(mountpoint)),
                    "device": partition.device,
                    "filesystem": partition.fstype or "Inconnu",
                    "total": int(usage.total),
                    "used": int(usage.used),
                    "free": int(usage.free),
                }
            )
        except (OSError, PermissionError, psutil.Error):
            continue

    return devices


def find_usb_for_backup(preferred_mountpoint: str | None = None) -> dict | None:
    devices = detect_usb_devices()
    return select_backup_device(devices, preferred_mountpoint)["selected"]


def select_backup_device(
    devices: list[dict],
    preferred_mountpoint: str | None = None,
) -> dict:
    """Recommande la clé existante, sinon la moins utilisée, sans départager une égalité."""
    if not devices:
        return {"selected": None, "requires_choice": False, "reason": "none"}

    if preferred_mountpoint:
        preferred = os.path.normcase(os.path.abspath(preferred_mountpoint))
        for device in devices:
            if os.path.normcase(os.path.abspath(device["mountpoint"])) == preferred:
                return {"selected": device, "requires_choice": False, "reason": "preferred"}

    existing_archives = [
        device
        for device in devices
        if (
            Path(device["mountpoint"])
            / "Sauvegardes"
            / "guardian-valid.marker"
        ).is_file()
    ]
    if len(existing_archives) == 1:
        return {
            "selected": existing_archives[0],
            "requires_choice": False,
            "reason": "existing_backup",
        }
    if len(existing_archives) > 1:
        return {"selected": None, "requires_choice": True, "reason": "multiple_backups"}
    if len(devices) == 1:
        return {"selected": devices[0], "requires_choice": False, "reason": "only_device"}

    def free_fraction(device: dict) -> Fraction:
        return Fraction(int(device["free"]), max(int(device["total"]), 1))

    greatest_free_fraction = max(free_fraction(device) for device in devices)
    least_used = [
        device for device in devices
        if free_fraction(device) == greatest_free_fraction
    ]
    if len(least_used) == 1:
        return {"selected": least_used[0], "requires_choice": False, "reason": "least_used"}
    return {"selected": None, "requires_choice": True, "reason": "tie"}


def get_environment_name() -> str:
    """Retourne un nom d'environnement simple pour les journaux."""
    system = platform.system().lower()
    if system == "windows":
        return "Windows 11"
    if system == "linux":
        return "Linux"
    return platform.system()