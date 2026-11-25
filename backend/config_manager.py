"""
Gestion locale des profils, du verrouillage, des journaux et des archives Guardian.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import psutil
from utils.common import application_directory


class InstanceLock:
    """Empêche deux instances ou opérations simultanées dans Guardian."""

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._handle = None

    def acquire(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists():
            try:
                previous_pid = int(self.lock_path.read_text(encoding="utf-8").strip())
                if psutil.pid_exists(previous_pid):
                    return False
            except (OSError, ValueError, UnicodeDecodeError):
                pass
            try:
                self.lock_path.unlink()
            except OSError:
                return False
        try:
            self._handle = open(
                self.lock_path,
                "x",
                encoding="utf-8",
                newline="\n",
            )
            self._handle.write(str(os.getpid()))
            self._handle.flush()
            os.fsync(self._handle.fileno())
            return True
        except FileExistsError:
            return False

    def release(self) -> None:
        if self._handle is not None:
            try:
                self._handle.close()
            finally:
                self._handle = None
        try:
            self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def get_application_directory() -> Path:
    """Retourne le dossier réel de l'application, y compris en exécution compilée."""
    return application_directory()


def get_data_directory() -> Path:
    """Retourne le dossier privé des données Guardian."""
    data_directory = get_application_directory() / "GuardianData"
    data_directory.mkdir(parents=True, exist_ok=True)
    return data_directory


def atomic_write_text(path: Path, content: str) -> None:
    """Écrit un texte dans un fichier temporaire puis le rend visible seulement une fois complet."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_write_json(path: Path, data: Any) -> None:
    """Écrit une configuration JSON de manière fiable."""
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def read_json(path: Path, default: Any) -> Any:
    """Lit un JSON, avec une valeur de repli si le fichier est absent ou endommagé."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def append_log(path: Path, message: str) -> None:
    """Ajoute une ligne au journal après avoir écrit une copie complète."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "r", encoding="utf-8", newline="\n") as handle:
            existing = handle.read()
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        existing = ""

    from datetime import datetime

    line = f"{datetime.now().isoformat(timespec='seconds')} — {message}\n"
    atomic_write_text(path, existing + line)


def load_profile(profile_name: str = "default") -> dict:
    """Charge le profil demandé ou construit un profil raisonnable."""
    profile_path = get_data_directory() / "profiles" / f"{profile_name}.json"
    default = {
        "profile": profile_name,
        "retention_count": 5,
        "preferred_usb": None,
        "custom_directories": [],
    }
    return read_json(profile_path, default)


def save_profile(profile: dict, profile_name: str = "default") -> Path:
    """Sauvegarde un profil complet."""
    profile_path = get_data_directory() / "profiles" / f"{profile_name}.json"
    atomic_write_json(profile_path, profile)
    return profile_path


def cleanup_old_archives(base_directory: Path, retention_count: int = 5) -> list[Path]:
    """Supprime les anciennes sauvegardes en conservant toujours au moins une copie valide."""
    if retention_count < 1:
        retention_count = 1

    try:
        archives = [
            path
            for path in base_directory.iterdir()
            if path.is_dir() and path.name.startswith("Sauvegarde_")
        ]
    except (FileNotFoundError, PermissionError, OSError):
        return []

    archives.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    valid_archives: list[Path] = []
    for archive in archives:
        guardian_marker = archive / "guardian-valid.marker"
        if guardian_marker.is_file():
            valid_archives.append(archive)

    if not valid_archives:
        valid_archives = archives[:1]

    removed: list[Path] = []
    kept_names = {path.name for path in valid_archives[:retention_count]}
    for archive in archives:
        if archive.name in kept_names:
            continue
        try:
            shutil.rmtree(archive)
            removed.append(archive)
        except (OSError, PermissionError):
            continue
    return removed