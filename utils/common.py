"""
Fonctions communes aux variantes d'environnement Guardian.
"""

from __future__ import annotations

import sys
from pathlib import Path


def application_directory() -> Path:
    """Résout les chemins en Python direct et dans l'exécutable compilé."""
    compiled_info = globals().get("__compiled__")
    original_executable = getattr(compiled_info, "original_argv0", None)
    if original_executable:
        original_path = Path(original_executable)
        if original_path.is_absolute():
            return original_path.resolve().parent
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def frontend_directory() -> Path:
    """Retourne le dossier frontend embarqué."""
    compiled_info = globals().get("__compiled__")
    runtime_directory = getattr(compiled_info, "python_runtime_dir", None)
    containing_directory = getattr(compiled_info, "containing_dir", None)
    for directory in (runtime_directory, containing_directory):
        if not directory:
            continue
        bundled_frontend = Path(directory) / "frontend"
        if bundled_frontend.is_dir():
            return bundled_frontend
    return application_directory() / "frontend"


def legal_file(bundled_name: str, source_name: str) -> Path | None:
    """Retourne un texte juridique embarqué ou situé à la racine du projet."""
    for candidate in (
        frontend_directory() / bundled_name,
        application_directory() / source_name,
    ):
        if candidate.is_file():
            return candidate
    return None


def license_file() -> Path | None:
    return legal_file("LICENSE.txt", "LICENSE")


def notices_file() -> Path | None:
    return legal_file("THIRD_PARTY_NOTICES.txt", "THIRD_PARTY_NOTICES.md")
