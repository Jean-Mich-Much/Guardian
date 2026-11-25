"""
Moteur de copie incrémentale et résiliente des souvenirs.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import shutil
import sys
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from .config_manager import (
    append_log,
    atomic_write_json,
    atomic_write_text,
    cleanup_old_archives,
    read_json,
)
from .crypto_manager import encrypt_file
from .scanner import (
    _iter_scannable_files,
    category_for_file,
    is_path_excluded,
)

CACHE_FLUSH_INTERVAL_BYTES = 1024 * 1024 * 1024
CACHE_FLUSH_INTERVAL_SECONDS = 300


def calculate_sha256(path: Path, event_callback: Callable[[dict], None] | None = None) -> str:
    """Calcule l'empreinte numérique d'un fichier dans le même flux de copie."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _hide_metadata_directory(directory: Path) -> None:
    if sys.platform != "win32":
        return

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
    kernel32.GetFileAttributesW.restype = ctypes.c_uint32
    kernel32.SetFileAttributesW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
    kernel32.SetFileAttributesW.restype = ctypes.c_int
    attributes = kernel32.GetFileAttributesW(str(directory))
    if attributes == 0xFFFFFFFF:
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel32.SetFileAttributesW(str(directory), attributes | 0x2 | 0x4):
        raise ctypes.WinError(ctypes.get_last_error())


class BackupEngine:
    """Exécute une sauvegarde complète ou incrémentale avec reprise."""

    def __init__(self, event_callback: Callable[[dict], None] | None = None) -> None:
        self.event_callback = event_callback
        self.paused = threading.Event()
        self.cancelled = threading.Event()
        self.running = False
        self.current_file = ""
        self.processed = 0
        self.total = 0
        self.started_at = 0.0

    def emit(self, event_type: str, **values: object) -> None:
        payload = {"type": event_type, **values}
        if self.event_callback is not None:
            self.event_callback(payload)

    def pause(self) -> None:
        self.paused.set()
        self.emit("paused", message="La copie est en pause.")

    def resume(self) -> None:
        self.paused.clear()
        self.emit("resumed", message="La copie reprend.")

    def cancel(self) -> None:
        self.cancelled.set()
        self.emit("cancelled", message="La copie va s'arrêter proprement.")

    def _wait_if_paused(self) -> bool:
        while self.paused.is_set() and not self.cancelled.is_set():
            time.sleep(0.1)
        return not self.cancelled.is_set()

    def _copy_atomically(
        self,
        source: Path,
        destination: Path,
        password: str | None,
        log_path: Path,
    ) -> tuple[bool, str, int]:
        temporary = destination.with_name(destination.name + ".tmp")
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            append_log(log_path, f"Dossier de destination inaccessible : {destination.parent} — {error}")
            return False, "", 0

        source_size = source.stat().st_size
        self.current_file = str(source)

        if password:
            try:
                encrypted_info = encrypt_file(source, temporary, password)
                os.replace(temporary, destination)
                return True, encrypted_info["sha256"], int(destination.stat().st_size)
            except (OSError, PermissionError, ValueError) as error:
                append_log(log_path, f"Fichier impossible à protéger : {source} — {error}")
                return False, "", 0

        resumed = 0
        try:
            if temporary.exists():
                resumed = min(temporary.stat().st_size, source_size)
            with open(source, "rb") as source_handle, open(temporary, "r+b" if resumed else "wb") as target_handle:
                if resumed:
                    source_handle.seek(resumed)
                    target_handle.seek(resumed)
                    target_handle.truncate(resumed)
                while True:
                    if not self._wait_if_paused():
                        return False, "", 0
                    block = source_handle.read(1024 * 1024)
                    if not block:
                        break
                    target_handle.write(block)
            os.replace(temporary, destination)
        except (OSError, PermissionError, ValueError) as error:
            append_log(log_path, f"Fichier non copié : {source} — {error}")
            return False, "", 0

        try:
            copied_size = destination.stat().st_size
            if copied_size != source_size:
                append_log(log_path, f"Taille différente après copie : {source}")
                return False, "", copied_size
            sha256 = calculate_sha256(destination)
            source_sha256 = calculate_sha256(source)
            if sha256 != source_sha256:
                append_log(log_path, f"Vérification différente après copie : {source}")
                return False, "", copied_size
            return True, sha256, copied_size
        except (OSError, PermissionError) as error:
            append_log(log_path, f"Impossible de vérifier : {source} — {error}")
            return False, "", 0

    def run(
        self,
        source_directories: Iterable[Path],
        usb_mountpoint: Path,
        password: str | None = None,
        retention_count: int = 5,
        include_extensions: Iterable[str] | None = None,
        cache_flush_callback: Callable[[Path], str | None] | None = None,
        included_categories: Iterable[str] | None = None,
        max_file_size_bytes: int | None = None,
        excluded_paths: Iterable[Path] | None = None,
        trusted_paths: Iterable[Path] | None = None,
        blocked_paths: Iterable[Path] = (),
        explicit_paths: Iterable[Path] = (),
        known_folders: dict[str, list[Path]] | None = None,
    ) -> dict:
        """Copie toutes les sources dans une nouvelle archive datée."""
        if self.running:
            return {"success": False, "error": "Une sauvegarde est déjà en cours."}

        self.running = True
        self.cancelled.clear()
        self.paused.clear()
        self.started_at = time.time()
        archive_name = "Sauvegardes"
        archive = usb_mountpoint / archive_name
        archive.mkdir(parents=True, exist_ok=True)

        log_path = archive / "Guardian.log"
        metadata_directory = usb_mountpoint / ".guardian"
        manifest_path = metadata_directory / "guardian-index.json"
        try:
            metadata_directory.mkdir(parents=True, exist_ok=True)
            _hide_metadata_directory(metadata_directory)
        except OSError as error:
            self.running = False
            return {
                "success": False,
                "error": f"Impossible de créer l'index discret de sauvegarde : {error}",
                "safe_to_remove": False,
                "archive": str(archive),
                "copied": 0,
                "skipped": 0,
                "failed": 0,
                "elapsed": time.time() - self.started_at,
                "category_summary": {
                    "documents": 0,
                    "photos": 0,
                    "music": 0,
                    "videos": 0,
                    "other": 0,
                },
                "uncopied": [],
            }

        legacy_manifest = archive / "guardian-index.json"
        existing_index = (
            manifest_path if manifest_path.is_file()
            else legacy_manifest if legacy_manifest.is_file()
            else None
        )
        manifest_data = read_json(existing_index, None) if existing_index else {}
        if not isinstance(manifest_data, dict):
            self.running = False
            return {
                "success": False,
                "error": "L'index de sauvegarde existant est illisible ; il a été conservé.",
                "safe_to_remove": False,
                "archive": str(archive),
            }
        manifest: dict[str, dict] = {}
        for key, entry in manifest_data.items():
            if not isinstance(key, str) or not isinstance(entry, dict):
                continue
            relative = Path(*key.split("/"))
            if relative.is_absolute() or ".." in relative.parts:
                continue
            existing = archive / relative
            if existing.is_file() and not existing.is_symlink():
                manifest[key] = entry

        def record_manifest(
            destination: Path,
            source: Path,
            source_root: Path,
            source_size: int,
            source_hash: str,
            stored_size: int,
            stored_hash: str,
        ) -> None:
            try:
                source_path = str(source.resolve())
            except OSError:
                source_path = str(source)
            try:
                root_path = str(source_root.resolve())
            except OSError:
                root_path = str(source_root)
            manifest[destination.relative_to(archive).as_posix()] = {
                "size": stored_size,
                "sha256": stored_hash,
                "protected": bool(password),
                "source_path": source_path,
                "source_root": root_path,
                "source_root_is_file": source_root.is_file(),
                "source_size": source_size,
                "source_sha256": source_hash,
            }
            if known_folders is not None:
                manifest[destination.relative_to(archive).as_posix()].update({
                    "layout_version": 2,
                    "category": category_for_file(source),
                })

        files: list[tuple[Path, Path, Path]] = []
        allowed_extensions = (
            {extension.casefold() for extension in include_extensions}
            if include_extensions is not None
            else None
        )
        selected_categories = (
            {category.casefold() for category in included_categories}
            if included_categories is not None
            else None
        )
        normalized_exclusions: list[Path] = []
        for excluded_path in excluded_paths or ():
            path = Path(excluded_path).expanduser()
            try:
                normalized_exclusions.append(path.resolve(strict=False))
            except OSError:
                normalized_exclusions.append(path.absolute())

        def should_include(source: Path) -> bool:
            if (
                selected_categories is not None
                and category_for_file(source) not in selected_categories
            ):
                return False
            if is_path_excluded(source, normalized_exclusions):
                return False
            if max_file_size_bytes is not None:
                try:
                    if source.stat().st_size >= max_file_size_bytes:
                        return False
                except OSError:
                    pass
            return True

        roots = list(dict.fromkeys(Path(path) for path in source_directories))
        file_roots = [
            root for root in roots if root.is_file() and should_include(root)
        ]
        parent_labels: dict[str, str] = {}
        for source in file_roots:
            parent = source.parent
            try:
                parent_key = os.path.normcase(str(parent.resolve()))
            except OSError:
                parent_key = os.path.normcase(str(parent))
            parent_labels[parent_key] = (
                parent.name or source.drive.rstrip("\\:") or "Racine"
            )
        parent_label_counts = Counter(
            label.casefold() for label in parent_labels.values()
        )
        seen_sources: set[str] = set()
        known_roots = sorted(
            (
                (Path(path).resolve(strict=False), label)
                for label, paths in (known_folders or {}).items()
                for path in paths
            ),
            key=lambda item: len(item[0].parts),
            reverse=True,
        )

        def add_source(source: Path, relative: Path, source_root: Path) -> None:
            if not should_include(source):
                return
            try:
                source_key = os.path.normcase(str(source.resolve()))
            except OSError:
                source_key = os.path.normcase(str(source))
            if source_key in seen_sources:
                return
            seen_sources.add(source_key)
            if known_folders is not None:
                resolved_source = source.resolve(strict=False)
                relative = Path("Autres emplacements") / relative
                for known_root, label in known_roots:
                    try:
                        known_relative = resolved_source.relative_to(known_root)
                    except ValueError:
                        continue
                    relative = Path(label) / known_relative
                    break
            files.append((source, relative, source_root))

        for source in file_roots:
            if (
                allowed_extensions is not None
                and source.suffix.casefold() not in allowed_extensions
            ):
                continue
            parent = source.parent
            try:
                parent_key = os.path.normcase(str(parent.resolve()))
            except OSError:
                parent_key = os.path.normcase(str(parent))
            parent_label = parent_labels[parent_key]
            if parent_label_counts[parent_label.casefold()] > 1:
                suffix = hashlib.sha256(parent_key.encode("utf-8")).hexdigest()[:8]
                parent_label = f"{parent_label}-{suffix}"
            add_source(
                source,
                Path("Fichiers ajoutés") / parent_label / source.name,
                source,
            )

        directory_roots = [root for root in roots if root.is_dir()]
        root_names = Counter(
            (root.name or root.drive.rstrip("\\:")).casefold()
            for root in directory_roots
        )
        for source_root in directory_roots:
            if is_path_excluded(source_root, normalized_exclusions):
                continue
            root_name = source_root.name or source_root.drive.rstrip("\\:")
            if root_names[root_name.casefold()] > 1:
                root_parts = source_root.parts[1:] if source_root.anchor else source_root.parts
                root_name = str(Path(source_root.drive.rstrip("\\:") or "source", *root_parts))
            root_prefix = Path(root_name)
            for source in _iter_scannable_files(
                source_root, normalized_exclusions, trusted_paths, blocked_paths, explicit_paths
            ):
                if (
                    allowed_extensions is not None
                    and source.suffix.casefold() not in allowed_extensions
                ):
                    continue
                try:
                    relative = source.resolve().relative_to(source_root.resolve())
                    add_source(source, root_prefix / relative, source_root)
                except (OSError, ValueError):
                    continue

        def backup_priority(item: tuple[Path, Path, Path]) -> tuple[int, float]:
            source = item[0]
            rank = {
                "documents": 0,
                "photos": 1,
                "music": 2,
                "videos": 3,
                "other": 4,
            }[category_for_file(source)]
            try:
                modified = source.stat().st_mtime if rank == 3 else 0
            except OSError:
                modified = 0
            return rank, -modified

        files.sort(key=backup_priority)

        self.total = sum(
            1
            for source, _, _ in files
            if source.exists()
        )
        if self.total == 0:
            append_log(log_path, "Aucun fichier à sauvegarder n'a été trouvé.")
            cache_flush_error = (
                cache_flush_callback(usb_mountpoint)
                if cache_flush_callback is not None
                else None
            )
            error_message = "Aucun fichier à sauvegarder n'a été trouvé."
            if cache_flush_error:
                error_message += f" La synchronisation du cache a échoué : {cache_flush_error}"
            self.running = False
            return {
                "success": False,
                "error": error_message,
                "safe_to_remove": cache_flush_callback is not None and cache_flush_error is None,
                "cache_flush_error": cache_flush_error,
                "archive": str(archive),
                "copied": 0,
                "skipped": 0,
                "failed": 0,
                "elapsed": time.time() - self.started_at,
                "category_summary": {
                    "documents": 0,
                    "photos": 0,
                    "music": 0,
                    "videos": 0,
                    "other": 0,
                },
                "uncopied": [],
            }
        self.processed = 0
        copied = 0
        skipped = 0
        failed = 0
        duplicate_indexes: dict[str, str] = {}
        category_summary = {
            "documents": 0,
            "photos": 0,
            "music": 0,
            "videos": 0,
            "other": 0,
        }
        uncopied: list[str] = []
        bytes_since_cache_flush = 0
        last_cache_flush = time.monotonic()
        cache_checkpoint_error: str | None = None

        append_log(log_path, "Démarrage de la sauvegarde.")
        for source, relative, source_root in files:
            if (
                cache_flush_callback is not None
                and bytes_since_cache_flush > 0
                and (
                    bytes_since_cache_flush >= CACHE_FLUSH_INTERVAL_BYTES
                    or time.monotonic() - last_cache_flush >= CACHE_FLUSH_INTERVAL_SECONDS
                )
            ):
                cache_checkpoint_error = cache_flush_callback(usb_mountpoint)
                if cache_checkpoint_error:
                    break
                bytes_since_cache_flush = 0
                last_cache_flush = time.monotonic()

            if not self._wait_if_paused():
                append_log(log_path, "Sauvegarde arrêtée par l'utilisateur.")
                break

            try:
                source_size = source.stat().st_size
                if (
                    max_file_size_bytes is not None
                    and source_size >= max_file_size_bytes
                ):
                    skipped += 1
                    append_log(
                        log_path,
                        f"Fichier devenu trop volumineux depuis l'analyse : {source}",
                    )
                    self.processed += 1
                    self.emit(
                        "progress",
                        processed=self.processed,
                        total=self.total,
                        current=str(source),
                        percent=round(self.processed * 100 / max(self.total, 1), 1),
                    )
                    continue
                source_hash = calculate_sha256(source)
            except (OSError, PermissionError) as error:
                failed += 1
                append_log(log_path, f"Fichier inaccessible : {source} — {error}")
                continue

            try:
                free_space = shutil.disk_usage(usb_mountpoint).free
            except OSError:
                free_space = 0

            if source_size > free_space:
                skipped += 1
                uncopied.append(str(source))
                append_log(
                    log_path,
                    f"Espace insuffisant pour ce fichier : {source}",
                )
                self.processed += 1
                self.emit(
                    "progress",
                    processed=self.processed,
                    total=self.total,
                    current=str(source),
                    percent=round(self.processed * 100 / max(self.total, 1), 1),
                )
                continue

            safe_relative = relative
            category = category_for_file(source)
            category_directory = {
                "documents": "Documents",
                "photos": "Photos",
                "music": "Musique",
                "videos": "Vidéos",
                "other": "Autres",
            }[category]
            destination = (
                archive / safe_relative if known_folders is not None
                else archive / category_directory / safe_relative
            )

            destination_hash = ""
            if destination.is_file():
                try:
                    if destination.stat().st_size == source_size:
                        destination_hash = calculate_sha256(destination)
                except (OSError, PermissionError):
                    destination_hash = ""

            if known_folders is not None and (destination.exists() or destination.is_symlink()):
                old_entry = manifest.get(destination.relative_to(archive).as_posix(), {})
                old_source = old_entry.get("source_path")
                if (
                    not destination.is_file()
                    or destination.is_symlink()
                    or not isinstance(old_source, str)
                    or os.path.normcase(os.path.abspath(old_source))
                    != os.path.normcase(str(source.resolve(strict=False)))
                ):
                    failed += 1
                    uncopied.append(str(source))
                    append_log(log_path, f"Emplacement déjà occupé par un autre fichier : {destination}")
                    self.processed += 1
                    self.emit(
                        "progress", processed=self.processed, total=self.total,
                        current=str(source), percent=round(self.processed * 100 / max(self.total, 1), 1),
                    )
                    continue

            if destination_hash == source_hash:
                skipped += 1
                category_summary[category] += 1
                record_manifest(
                    destination,
                    source,
                    source_root,
                    source_size,
                    source_hash,
                    source_size,
                    source_hash,
                )
                self.processed += 1
                self.emit(
                    "progress",
                    processed=self.processed,
                    total=self.total,
                    current=str(source),
                    percent=round(self.processed * 100 / max(self.total, 1), 1),
                )
                continue

            if source_hash in duplicate_indexes:
                try:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    os.link(duplicate_indexes[source_hash], destination)
                    copied += 1
                    record_manifest(
                        destination,
                        source,
                        source_root,
                        source_size,
                        source_hash,
                        source_size,
                        source_hash,
                    )
                    self.processed += 1
                    self.emit(
                        "progress",
                        processed=self.processed,
                        total=self.total,
                        current=str(source),
                        percent=round(self.processed * 100 / max(self.total, 1), 1),
                    )
                    continue
                except (OSError, PermissionError):
                    pass

            success, copied_hash, copied_size = self._copy_atomically(
                source,
                destination,
                password,
                log_path,
            )
            if success:
                copied += 1
                bytes_since_cache_flush += copied_size
                duplicate_indexes.setdefault(copied_hash, str(destination))
                category_summary[category] += 1
                record_manifest(
                    destination,
                    source,
                    source_root,
                    source_size,
                    source_hash,
                    copied_size,
                    copied_hash,
                )
            else:
                failed += 1

            self.processed += 1
            self.emit(
                "progress",
                processed=self.processed,
                total=self.total,
                current=str(source),
                percent=round(self.processed * 100 / max(self.total, 1), 1),
            )

        copy_complete = (
            not self.cancelled.is_set()
            and failed == 0
            and not uncopied
            and cache_checkpoint_error is None
        )
        complete = copy_complete
        atomic_write_json(manifest_path, manifest)
        if legacy_manifest.is_file():
            try:
                legacy_manifest.unlink()
            except OSError as error:
                append_log(
                    log_path,
                    f"Ancien index visible non supprimé : {error}",
                )
        if not self.cancelled.is_set():
            if complete:
                marker = archive / "guardian-valid.marker"
                atomic_write_text(
                    marker,
                    f"Sauvegarde terminée le {datetime.now().isoformat(timespec='seconds')}\n",
                )
            cleanup_old_archives(usb_mountpoint, retention_count)
            append_log(log_path, f"Sauvegarde terminée : {copied} copiés, {skipped} déjà présents, {failed} erreurs.")
        else:
            append_log(log_path, "Sauvegarde annulée.")

        final_cache_flush_error = (
            cache_flush_callback(usb_mountpoint)
            if cache_flush_callback is not None
            else None
        )
        safe_to_remove = cache_flush_callback is not None and final_cache_flush_error is None
        cache_flush_errors = [
            error
            for error in (cache_checkpoint_error, final_cache_flush_error)
            if error
        ]
        if final_cache_flush_error:
            marker = archive / "guardian-valid.marker"
            try:
                marker.unlink(missing_ok=True)
            except OSError as error:
                cache_flush_errors.append(f"Impossible de retirer le marqueur de validité : {error}")
            complete = False

        error_messages = []
        if self.cancelled.is_set():
            error_messages.append("Sauvegarde annulée.")
        elif not copy_complete:
            error_messages.append("Certains fichiers n'ont pas pu être sauvegardés.")
        if cache_flush_errors:
            error_messages.append(
                "La synchronisation du cache de la clé a échoué : "
                + " ; ".join(cache_flush_errors)
            )
        error_message = " ".join(error_messages) if error_messages else None

        event_type = "cancelled_complete" if self.cancelled.is_set() else "completed"
        self.emit(
            event_type,
            archive=str(archive),
            success=complete,
            error=error_message,
            copied=copied,
            skipped=skipped,
            failed=failed,
            category_summary=category_summary,
            uncopied=uncopied[:20],
            safe_to_remove=safe_to_remove,
            cache_flush_error=cache_flush_errors[-1] if cache_flush_errors else None,
        )

        self.running = False
        elapsed = time.time() - self.started_at
        return {
            "success": complete,
            "error": error_message,
            "safe_to_remove": safe_to_remove,
            "cache_flush_error": cache_flush_errors[-1] if cache_flush_errors else None,
            "archive": str(archive),
            "copied": copied,
            "skipped": skipped,
            "failed": failed,
            "elapsed": elapsed,
            "category_summary": category_summary,
            "uncopied": uncopied[:20],
        }