"""
Point d'entrée principal de Guardian.

Ce fichier ouvre l'interface native et relie son JavaScript aux fonctions Python.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue

from backend.backup_engine import BackupEngine, calculate_sha256
from backend.config_manager import (
    InstanceLock,
    append_log,
    atomic_write_json,
    get_data_directory,
    load_profile,
    read_json,
    save_profile,
)
from backend.crypto_manager import decrypt_file
from backend.scanner import (
    CATEGORY_NAMES,
    PHOTO_EXTENSIONS,
    category_for_file,
    discover_personal_directories,
    get_directories_by_category,
    get_personal_directories,
    scan_directories,
)
from backend.system_check import get_system_status, prevent_sleep, allow_sleep
from backend.usb_detector import detect_usb_devices, select_backup_device
from utils.env_detector import detect_environment
from utils.common import frontend_directory, license_file, notices_file


event_queue: Queue[dict] = Queue()
backup_engine = BackupEngine(
    event_callback=lambda payload: event_queue.put(payload)
)
sleep_state: object | None = None
lock = InstanceLock(get_data_directory() / ".lock")
MAX_BACKUP_FILE_SIZE_MB = 1_048_576


@dataclass
class BackupRequest:
    mountpoint: str
    password: str | None = None
    profile: str = "default"
    mode: str = "all"
    categories: list[str] | None = None
    custom_directories: list[str] = field(default_factory=list)
    max_file_size_bytes: int | None = None
    excluded_paths: list[str] = field(default_factory=list)


@dataclass
class RestoreRequest:
    mountpoint: str
    password: str | None = None
    categories: list[str] = field(default_factory=list)
    custom_directory: str | None = None
    destination_directory: str | None = None


@dataclass
class ProfileRequest:
    profile: str = "default"
    retention_count: int = 5
    preferred_usb: str | None = None


def _select_custom_paths(select_files: bool) -> dict:
    """Ouvre une boîte native pour choisir un dossier ou des fichiers."""
    try:
        import webview
    except ImportError as error:
        append_log(
            get_data_directory() / "Guardian.log",
            f"Le sélecteur de sources est indisponible : {error}",
        )
        return {"success": False, "error": str(error)}

    if not webview.windows:
        return {"success": False, "error": "La fenêtre Guardian n'est pas prête."}

    try:
        if select_files:
            selected = webview.windows[0].create_file_dialog(
                webview.FileDialog.OPEN,
                allow_multiple=True,
            )
        else:
            selected = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
        if selected:
            selected_paths = [selected] if isinstance(selected, str) else selected
            paths = []
            for selected_path in selected_paths:
                path = Path(selected_path)
                is_valid = path.is_file() if select_files else path.is_dir()
                if not is_valid:
                    return {
                        "success": False,
                        "error": "Un élément sélectionné n'est plus accessible.",
                    }
                paths.append(str(path.resolve()))
            if paths:
                return {"success": True, "paths": paths}
        return {"success": False, "cancelled": True}
    except (OSError, RuntimeError, ValueError, webview.WebViewException) as error:
        append_log(
            get_data_directory() / "Guardian.log",
            f"Impossible d'ouvrir le choix des sources : {error}",
        )
        return {"success": False, "error": str(error)}


def api_select_folder() -> dict:
    """Ouvre une boîte native pour choisir un dossier à sauvegarder."""
    result = _select_custom_paths(select_files=False)
    if result["success"]:
        return {"success": True, "path": result["paths"][0]}
    return result


def api_select_files() -> dict:
    """Ouvre une boîte native pour choisir plusieurs fichiers à sauvegarder."""
    return _select_custom_paths(select_files=True)


def api_status() -> dict:
    """Indique si Guardian est prêt et dans quel environnement il fonctionne."""
    return {
        "ready": True,
        "environment": detect_environment(),
        "backup_running": backup_engine.running,
    }


def api_usb() -> dict:
    """Liste les clés USB visibles."""
    devices = detect_usb_devices()
    selection = select_backup_device(devices)
    return {
        "devices": devices,
        "selected": selection["selected"],
        "requires_choice": selection["requires_choice"],
        "reason": selection["reason"],
    }


def _validate_backup_filters(
    max_file_size_bytes: int | None,
    excluded_paths: list[str] | None,
) -> tuple[int | None, list[Path], str | None]:
    if max_file_size_bytes is not None and (
        isinstance(max_file_size_bytes, bool)
        or not isinstance(max_file_size_bytes, int)
        or max_file_size_bytes < 1
        or max_file_size_bytes > MAX_BACKUP_FILE_SIZE_MB * 1024**2
    ):
        return None, [], "La taille maximale doit être comprise entre 1 octet et 1 To."
    if excluded_paths is None:
        excluded_paths = []
    if not isinstance(excluded_paths, list) or any(
        not isinstance(path, str) or not path.strip()
        for path in excluded_paths
    ):
        return None, [], "La liste des éléments à exclure est invalide."

    resolved_paths = []
    for selected_path in excluded_paths:
        path = Path(selected_path).expanduser()
        try:
            if not path.is_file() and not path.is_dir():
                return None, [], f"Élément à exclure inaccessible : {path}"
            resolved_paths.append(path.resolve(strict=True))
        except OSError:
            return None, [], f"Élément à exclure inaccessible : {path}"
    return max_file_size_bytes, resolved_paths, None


def _backup_path_policy(
    mode: str, custom_sources: list[Path]
) -> tuple[list[Path], list[Path], list[Path]]:
    explicit = custom_sources if mode in {"all", "custom", "folder"} else []
    categories = ("photos",) if mode == "photos" else (
        ("documents", "photos", "music", "videos", "desktop") if mode == "all" else ()
    )
    trusted = [
        path
        for category in categories
        for path in get_directories_by_category(category)
    ] + explicit
    downloads = get_directories_by_category("downloads")
    return trusted, downloads, explicit


def api_diagnostic(
    mountpoint: str | None = None,
    mode: str = "all",
    max_file_size_bytes: int | None = None,
    excluded_paths: list[str] | None = None,
) -> dict:
    """Analyse les souvenirs et les confirme visuellement avant la copie."""
    max_file_size_bytes, excluded_path_objects, filter_error = _validate_backup_filters(
        max_file_size_bytes,
        excluded_paths,
    )
    if filter_error:
        return {"success": False, "error": filter_error}

    devices = detect_usb_devices()
    selection = select_backup_device(devices)
    if mountpoint:
        selected = next(
            (device for device in devices if device["mountpoint"] == mountpoint),
            None,
        )
    else:
        selected = selection["selected"]
    source_usb_roots = [
        Path(device["mountpoint"])
        for device in devices
        if selected and device["mountpoint"] != selected["mountpoint"]
    ]
    custom_sources = load_profile().get("custom_directories", [])
    if not isinstance(custom_sources, list):
        custom_sources = []
    custom_paths = [Path(path) for path in custom_sources if isinstance(path, str)]
    trusted, blocked, explicit = _backup_path_policy(mode, custom_paths)
    scan_options = {
        "max_file_size_bytes": max_file_size_bytes,
        "excluded_paths": excluded_path_objects,
        "trusted_paths": trusted,
        "blocked_paths": blocked,
        "explicit_paths": explicit,
    }
    if mode == "photos":
        directories = get_directories_by_category("photos")
        directories.extend(discover_personal_directories(source_usb_roots, excluded_paths=blocked))
        scan = scan_directories(
            directories,
            include_extensions=PHOTO_EXTENSIONS,
            **scan_options,
        )
    elif mode == "custom":
        scan = scan_directories(custom_paths, **scan_options)
    else:
        directories = get_personal_directories(
            custom_paths,
            extra_search_roots=source_usb_roots,
        )
        scan = scan_directories(directories, **scan_options)
    filesystem = selected["filesystem"] if selected else ""
    status = get_system_status(scan["largest_files"], filesystem)
    available = int(selected["free"]) if selected else 0
    return {
        "directories": scan["roots"],
        "photos": scan["photos"],
        "videos": scan["videos"],
        "documents": scan["documents"],
        "music": scan.get("music", 0),
        "other": scan["other"],
        "files": scan["files"],
        "required": scan["size"],
        "category_files": scan.get(
            "category_files",
            {category: scan.get(category, 0) for category in CATEGORY_NAMES},
        ),
        "category_sizes": scan.get(
            "category_sizes",
            {category: 0 for category in CATEGORY_NAMES},
        ),
        "available": available,
        "battery": status["battery"],
        "large_file_warnings": status["large_file_warnings"],
        "selected_usb": selected,
        "usb_choice_required": selection["requires_choice"] and selected is None,
    }


def api_get_profile(profile: str = "default") -> dict:
    return load_profile(profile)


def api_save_profile(request: ProfileRequest) -> dict:
    existing = load_profile(request.profile)
    custom_directories = existing.get("custom_directories", [])
    if not isinstance(custom_directories, list):
        custom_directories = []
    profile = {
        "profile": request.profile,
        "retention_count": max(1, request.retention_count),
        "preferred_usb": request.preferred_usb,
        "custom_directories": custom_directories,
    }
    save_profile(profile, request.profile)
    return {"success": True, "profile": profile}


def api_save_custom_directories(directories: list[str]) -> dict:
    """Enregistre les chemins ajoutés au parcours de sauvegarde."""
    if not isinstance(directories, list):
        return {"success": False, "error": "La liste d'éléments est invalide."}

    profile = load_profile()
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_path in directories:
        if not isinstance(raw_path, str):
            return {"success": False, "error": "Un chemin d'élément est invalide."}
        if not raw_path.strip():
            continue
        path = Path(raw_path).expanduser()
        try:
            path = path.resolve(strict=False)
        except OSError:
            pass
        value = str(path)
        key = str(path).casefold() if sys.platform == "win32" else str(path)
        if key not in seen:
            seen.add(key)
            normalized.append(value)
    profile["custom_directories"] = normalized
    save_profile(profile)
    return {"success": True, "custom_directories": normalized}


def _flush_volume_cache(mountpoint: Path) -> str | None:
    """Vide les écritures en attente sur le support de destination."""
    if sys.platform == "win32":
        drive = mountpoint.drive.rstrip("\\:").upper()
        if len(drive) != 1 or not drive.isascii() or not drive.isalpha():
            return "La lettre du lecteur de destination est invalide."

        powershell_script = f"""
$ErrorActionPreference = 'Stop'
$driveLetter = '{drive}'
$partition = Get-Partition -DriveLetter $driveLetter | Select-Object -First 1
if ($null -eq $partition) {{ throw 'Le lecteur de destination est introuvable.' }}
$letters = @(Get-Partition -DiskNumber $partition.DiskNumber |
    Where-Object {{ $_.DriveLetter }} |
    ForEach-Object {{ $_.DriveLetter.ToString() + ':' }} |
    Select-Object -Unique)
if ($letters.Count -eq 0) {{ $letters = @(($driveLetter + ':')) }}
Import-Module Storage -ErrorAction Stop
foreach ($letter in $letters) {{
    Write-VolumeCache -DriveLetter $letter[0] -ErrorAction Stop
}}
exit 0
"""
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    powershell_script,
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                details = result.stderr.strip() or result.stdout.strip()
                return details or "Windows n'a pas confirmé la synchronisation de la clé."
            return None
        except subprocess.TimeoutExpired:
            return "Le délai d'écriture du cache de la clé a été dépassé."
        except (OSError, subprocess.SubprocessError) as error:
            return str(error)

    if hasattr(os, "sync"):
        try:
            os.sync()
            return None
        except OSError as error:
            return str(error)
    return "La synchronisation finale du support n'est pas disponible sur ce système."


def api_backup_start(request: BackupRequest) -> dict:
    """Démarre une sauvegarde dans un fil séparé."""
    global sleep_state

    if request.categories is None:
        selected_categories = set(CATEGORY_NAMES)
    elif (
        not isinstance(request.categories, list)
        or any(not isinstance(category, str) for category in request.categories)
    ):
        return {"success": False, "error": "La sélection des catégories est invalide."}
    else:
        selected_categories = set(request.categories)
    if not selected_categories:
        return {
            "success": False,
            "error": "Sélectionnez au moins une catégorie à sauvegarder.",
        }
    if not selected_categories.issubset(CATEGORY_NAMES):
        return {"success": False, "error": "Une catégorie sélectionnée est inconnue."}

    max_file_size_bytes, excluded_path_objects, filter_error = _validate_backup_filters(
        request.max_file_size_bytes,
        request.excluded_paths,
    )
    if filter_error:
        return {"success": False, "error": filter_error}

    if backup_engine.running:
        return {"success": False, "error": "Une sauvegarde est déjà en cours."}

    usb = Path(request.mountpoint)
    if not usb.is_dir():
        return {"success": False, "error": "La clé sélectionnée n'est plus disponible."}
    devices = detect_usb_devices()
    if not any(device["mountpoint"] == str(usb) for device in devices):
        return {"success": False, "error": "La clé sélectionnée n'est plus reconnue."}

    profile = load_profile(request.profile)
    configured_directories = profile.get("custom_directories", [])
    if not isinstance(configured_directories, list):
        configured_directories = []
    custom_directories = list(configured_directories)
    custom_directories.extend(request.custom_directories)
    custom_paths = [
        Path(path) for path in custom_directories if isinstance(path, str)
    ]
    trusted, blocked, explicit = _backup_path_policy(request.mode, custom_paths)
    if request.mode == "photos":
        directories = get_directories_by_category("photos")
        source_usb_roots = [
            Path(device["mountpoint"])
            for device in devices
            if device["mountpoint"] != str(usb)
        ]
        directories.extend(discover_personal_directories(source_usb_roots, excluded_paths=blocked))
    elif request.mode == "custom":
        directories = [
            Path(path)
            for path in custom_directories
            if isinstance(path, str) and Path(path).exists()
        ]
        if not directories:
            return {
                "success": False,
                "error": "Ajoutez d'abord un dossier ou un fichier à sauvegarder.",
            }
    elif request.mode == "folder":
        directories = [
            Path(path)
            for path in request.custom_directories
            if Path(path).exists()
        ]
    else:
        source_usb_roots = [
            Path(device["mountpoint"])
            for device in devices
            if device["mountpoint"] != str(usb)
        ]
        directories = get_personal_directories(
            [Path(path) for path in custom_directories if isinstance(path, str)],
            extra_search_roots=source_usb_roots,
        )

    target = usb.resolve()
    for source in directories:
        try:
            resolved_source = Path(source).resolve()
        except OSError:
            continue
        if (
            resolved_source == target
            or resolved_source in target.parents
            or target in resolved_source.parents
        ):
            return {
                "success": False,
                "error": "Le dossier à sauvegarder ne peut pas contenir la clé de destination.",
            }

    known_folders = {
        label: get_directories_by_category(category)
        for category, label in (
            ("documents", "Documents"),
            ("photos", "Images"),
            ("music", "Musique"),
            ("videos", "Vidéos"),
            ("desktop", "Bureau"),
        )
    }
    sleep_state = prevent_sleep()

    def execute() -> None:
        global sleep_state
        try:
            result = backup_engine.run(
                directories,
                usb,
                password=request.password,
                retention_count=int(profile.get("retention_count", 5)),
                include_extensions=PHOTO_EXTENSIONS if request.mode == "photos" else None,
                cache_flush_callback=_flush_volume_cache,
                included_categories=selected_categories,
                max_file_size_bytes=max_file_size_bytes,
                excluded_paths=excluded_path_objects,
                trusted_paths=trusted,
                blocked_paths=blocked,
                explicit_paths=explicit,
                known_folders=known_folders,
            )
            event_queue.put({"type": "backup_result", **result})
        finally:
            allow_sleep(sleep_state)
            sleep_state = None

    threading.Thread(target=execute, name="GuardianBackup", daemon=True).start()
    return {"success": True}


def api_backup_pause() -> dict:
    backup_engine.pause()
    return {"success": True}


def api_backup_resume() -> dict:
    backup_engine.resume()
    return {"success": True}


def api_backup_cancel() -> dict:
    backup_engine.cancel()
    return {"success": True}


def api_archives(mountpoint: str) -> dict:
    """Liste les sauvegardes datées valides présentes sur une clé."""
    root = Path(mountpoint)
    if not root.is_dir():
        return {"archives": []}
    archives = []
    archive = root / "Sauvegardes"
    if archive.is_dir():
        marker = archive / "guardian-valid.marker"
        archives.append(
            {
                "name": archive.name,
                "path": str(archive),
                "marker": marker.read_text(
                    encoding="utf-8",
                    errors="replace",
                ).strip() if marker.is_file() else "Sauvegarde en cours",
            }
        )
    return {"archives": archives}


def _default_restore_root() -> Path:
    documents = get_directories_by_category("documents")
    base = documents[0] if documents else Path.home() / "Documents"
    return base / "GuardianRestored"


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        return path.resolve(strict=False).is_relative_to(parent.resolve(strict=False))
    except (OSError, RuntimeError, ValueError):
        return False


def _paths_are_equal(first: Path, second: Path) -> bool:
    try:
        return first.resolve(strict=False) == second.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return False


def _create_restore_shortcuts(targets: set[Path]) -> dict:
    if not targets:
        return {"success": True, "directory": None}

    desktops = get_directories_by_category("desktop")
    desktop = desktops[0] if desktops else Path.home() / "Desktop"
    directory = desktop / "Guardian - Éléments restaurés"
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return {"success": False, "directory": str(directory), "error": str(error)}

    unique_targets: dict[str, Path] = {}
    for target in targets:
        try:
            key = os.path.normcase(str(target.resolve(strict=False)))
        except OSError:
            key = os.path.normcase(str(target))
        if target.exists():
            unique_targets[key] = target

    labels = {
        key: target.name or "Guardian"
        for key, target in unique_targets.items()
    }
    label_counts = Counter(label.casefold() for label in labels.values())
    items = []
    for key, target in unique_targets.items():
        label = labels[key]
        if label_counts[label.casefold()] > 1:
            suffix = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
            label = f"{label}-{suffix}"
        items.append({"name": label, "target": str(target.resolve(strict=False))})

    if not items:
        return {"success": True, "directory": str(directory)}

    if sys.platform == "win32":
        payload = base64.b64encode(
            json.dumps(
                {"directory": str(directory), "items": items},
                ensure_ascii=False,
            ).encode("utf-8")
        ).decode("ascii")
        script = """
$ErrorActionPreference = 'Stop'
$payload64 = [Console]::In.ReadToEnd().Trim()
$json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payload64))
$data = $json | ConvertFrom-Json
$shell = New-Object -ComObject WScript.Shell
foreach ($item in $data.items) {
    $linkPath = Join-Path $data.directory ($item.name + '.lnk')
    $shortcut = $shell.CreateShortcut($linkPath)
    $shortcut.TargetPath = $item.target
    $shortcut.Save()
}
"""
        encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-EncodedCommand",
                    encoded_script,
                ],
                input=payload,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return {"success": False, "directory": str(directory), "error": str(error)}
        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip()
            return {
                "success": False,
                "directory": str(directory),
                "error": details or "Windows n'a pas créé les raccourcis.",
            }
    else:
        for item in items:
            target = Path(item["target"])
            link = directory / item["name"]
            if link.exists() and not link.is_symlink():
                suffix = hashlib.sha256(item["target"].encode("utf-8")).hexdigest()[:8]
                link = directory / f"{item['name']}-{suffix}"
            temporary = link.with_name(f".{link.name}.guardian-tmp")
            try:
                temporary.unlink(missing_ok=True)
                temporary.symlink_to(target, target_is_directory=target.is_dir())
                os.replace(temporary, link)
            except OSError as error:
                return {"success": False, "directory": str(directory), "error": str(error)}

    return {"success": True, "directory": str(directory)}


def api_restore(request: RestoreRequest) -> dict:
    """Restaure la sauvegarde vers les emplacements adaptés."""
    root = Path(request.mountpoint)
    archive = root / "Sauvegardes"
    if not archive.is_dir():
        return {"success": False, "error": "Aucune sauvegarde complète n'est disponible."}

    if request.destination_directory:
        restore_root = Path(request.destination_directory).expanduser().resolve(strict=False)
        if not restore_root.is_dir():
            return {
                "success": False,
                "error": "Le dossier de destination n'est plus accessible.",
            }
        if _path_is_within(restore_root, root):
            return {
                "success": False,
                "error": "La destination ne peut pas se trouver sur la clé de sauvegarde.",
            }
    else:
        restore_root = _default_restore_root()

    index_path = root / ".guardian" / "guardian-index.json"
    if not index_path.is_file():
        index_path = archive / "guardian-index.json"
    manifest = read_json(index_path, {})
    if not isinstance(manifest, dict):
        manifest = {}
    restored = 0
    skipped = 0
    failed = 0
    fallback_used = False
    selected_categories = set(request.categories)
    category_names = {
        "documents": "documents",
        "photos": "photos",
        "musique": "music",
        "vidéos": "videos",
        "autres": "other",
    }
    shortcut_targets: set[Path] = set()
    usb_root = root.resolve(strict=False)

    archive_files = sorted(
        archive.rglob("*"),
        key=lambda path: (
            isinstance(manifest.get(path.relative_to(archive).as_posix()), dict)
            and manifest[path.relative_to(archive).as_posix()].get("layout_version") == 2
        ),
    )
    for source in archive_files:
        if not source.is_file():
            continue
        if source.is_symlink():
            continue
        if source.name in {"Guardian.log", "guardian-index.json", "guardian-valid.marker"}:
            continue
        relative = source.relative_to(archive)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            failed += 1
            continue
        if request.custom_directory:
            custom = Path(request.custom_directory)
            if custom.name and custom.name.lower() not in str(relative).lower():
                continue
        entry = manifest.get(relative.as_posix(), {})
        if not isinstance(entry, dict):
            entry = {}
        if selected_categories:
            if entry.get("layout_version") == 2:
                category = entry.get("category")
            elif entry:
                category = category_names.get(relative.parts[0].casefold())
            else:
                category = category_for_file(source)
            if category not in selected_categories:
                continue

        original_path = entry.get("source_path")
        original_root = entry.get("source_root")
        source_root_is_file = entry.get("source_root_is_file") is True
        if request.destination_directory:
            destination = restore_root / relative
            destination_guard = restore_root
            shortcut_target = restore_root
        elif isinstance(original_path, str) and isinstance(original_root, str):
            original_destination = Path(original_path)
            original_root_path = Path(original_root)
            root_guard = (
                original_root_path.parent
                if source_root_is_file
                else original_root_path
            )
            root_available = False
            if (
                root_guard.is_dir()
                and original_destination.is_absolute()
                and original_root_path.is_absolute()
            ):
                root_available = (
                    _paths_are_equal(original_destination, original_root_path)
                    if source_root_is_file
                    else _path_is_within(original_destination, original_root_path)
                )
            if root_available:
                destination = original_destination
                destination_guard = root_guard
                shortcut_target = (
                    destination if source_root_is_file else original_root_path
                )
            else:
                destination = restore_root / relative
                destination_guard = restore_root
                shortcut_target = restore_root / relative.parts[0]
                fallback_used = True
        else:
            destination = restore_root / relative
            destination_guard = restore_root
            shortcut_target = restore_root / relative.parts[0]
            fallback_used = True

        if (
            not _path_is_within(destination, destination_guard)
            or _path_is_within(destination, usb_root)
        ):
            failed += 1
            continue

        if entry.get("protected") is True and not request.password:
            failed += 1
            continue

        temporary = destination.with_name(
            f".{destination.name}.guardian-restore-tmp"
        )
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and not destination.is_file():
                raise OSError("Un dossier occupe déjà l'emplacement du fichier.")
            expected_hash = entry.get("source_sha256")
            expected_size = entry.get("source_size")
            if (
                destination.is_file()
                and isinstance(expected_hash, str)
                and isinstance(expected_size, int)
                and destination.stat().st_size == expected_size
                and calculate_sha256(destination) == expected_hash
            ):
                skipped += 1
                shortcut_targets.add(shortcut_target)
                continue

            temporary.unlink(missing_ok=True)
            if request.password:
                if not decrypt_file(source, temporary, request.password):
                    failed += 1
                    continue
            else:
                shutil.copy2(source, temporary)

            temporary_size = temporary.stat().st_size
            temporary_hash = calculate_sha256(temporary)
            if (
                isinstance(expected_size, int)
                and temporary_size != expected_size
            ) or (
                isinstance(expected_hash, str)
                and temporary_hash != expected_hash
            ):
                failed += 1
                continue
            if (
                destination.is_file()
                and destination.stat().st_size == temporary_size
                and calculate_sha256(destination) == temporary_hash
            ):
                skipped += 1
                temporary.unlink(missing_ok=True)
                shortcut_targets.add(shortcut_target)
                continue

            os.replace(temporary, destination)
            shortcut_targets.add(shortcut_target)
            restored += 1
        except (OSError, PermissionError, ValueError):
            failed += 1
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                failed += 1

    shortcut_result = _create_restore_shortcuts(shortcut_targets)
    errors = []
    if failed:
        errors.append(f"{failed} fichier(s) n'ont pas pu être restaurés.")
    if not shortcut_result["success"]:
        errors.append(
            "Les raccourcis du Bureau n'ont pas pu être créés : "
            + shortcut_result["error"]
        )

    return {
        "success": failed == 0 and shortcut_result["success"],
        "restored": restored,
        "skipped": skipped,
        "failed": failed,
        "destination": str(restore_root),
        "destination_mode": "custom" if request.destination_directory else "automatic",
        "shortcut_directory": shortcut_result["directory"],
        "error": " ".join(errors) or None,
        "fallback_used": fallback_used,
    }


class GuardianApi:
    """Expose les fonctions Guardian au JavaScript via le pont natif pywebview."""

    def get_translations(self) -> dict[str, object]:
        frontend = frontend_directory()
        return {
            language: json.loads(
                (frontend / "locales" / f"{language}.json").read_text(encoding="utf-8")
            )
            for language in ("fr", "en")
        }

    def status(self) -> dict:
        return api_status()

    def get_license(self) -> str:
        parts = [
            path.read_text(encoding="utf-8")
            for path in (license_file(), notices_file())
            if path
        ]
        return ("\n\n" + "=" * 72 + "\n\n").join(parts)

    def usb(self) -> dict:
        return api_usb()

    def diagnostic(
        self,
        mountpoint: str | None = None,
        mode: str = "all",
        max_file_size_bytes: int | None = None,
        excluded_paths: list[str] | None = None,
    ) -> dict:
        return api_diagnostic(
            mountpoint,
            mode,
            max_file_size_bytes,
            excluded_paths,
        )

    def get_profile(self, profile: str = "default") -> dict:
        return api_get_profile(profile)

    def save_profile(self, request: dict) -> dict:
        return api_save_profile(ProfileRequest(**request))

    def save_custom_directories(self, directories: list[str]) -> dict:
        return api_save_custom_directories(directories)

    def archives(self, mountpoint: str) -> dict:
        return api_archives(mountpoint)

    def get_language(self) -> str:
        settings = read_json(get_data_directory() / "settings.json", {})
        if not isinstance(settings, dict):
            return "fr"
        language = settings.get("language", "fr")
        return language if language in {"fr", "en"} else "fr"

    def set_language(self, language: str) -> dict:
        if language not in {"fr", "en"}:
            raise ValueError(f"Langue non prise en charge : {language}")
        settings_path = get_data_directory() / "settings.json"
        settings = read_json(settings_path, {})
        if not isinstance(settings, dict):
            settings = {}
        settings["language"] = language
        atomic_write_json(settings_path, settings)
        return {"success": True}

    def select_folder(self) -> dict:
        return api_select_folder()

    def select_files(self) -> dict:
        return api_select_files()

    def start_backup(self, request: dict) -> dict:
        return api_backup_start(BackupRequest(**request))

    def pause_backup(self) -> dict:
        return api_backup_pause()

    def resume_backup(self) -> dict:
        return api_backup_resume()

    def cancel_backup(self) -> dict:
        return api_backup_cancel()

    def restore(self, request: dict) -> dict:
        return api_restore(RestoreRequest(**request))

    def poll_events(self) -> list[dict]:
        events = []
        while True:
            try:
                events.append(event_queue.get_nowait())
            except Empty:
                return events


guardian_api = GuardianApi()


def main() -> int:
    if not lock.acquire():
        if "--self-test" in sys.argv:
            return 1
        _show_startup_message("Guardian est déjà ouvert.")
        return 1

    try:
        if "--self-test" in sys.argv:
            frontend = frontend_directory()
            page = frontend / "index.html"
            if not page.is_file() or 'id="screen-home"' not in page.read_text(encoding="utf-8"):
                return 2
            required_files = (
                frontend / "css" / "fonts.css",
                frontend / "css" / "base.css",
                frontend / "css" / "screens.css",
                frontend / "css" / "components.css",
                frontend / "js" / "i18n.js",
                frontend / "js" / "app.js",
                frontend / "fonts" / "inter_01.woff2",
                frontend / "fonts" / "inter_02.woff2",
                frontend / "fonts" / "Twemoji.woff2",
            )
            if any(not resource.is_file() for resource in required_files):
                return 3
            if set(guardian_api.get_translations()) != {"fr", "en"}:
                return 4
            if "GUARDIAN" not in guardian_api.get_license():
                return 5
            return 0 if guardian_api.status()["ready"] else 4

        import webview

        frontend_url = (frontend_directory() / "index.html").resolve().as_uri()
        webview.create_window(
            "Guardian",
            url=frontend_url,
            js_api=guardian_api,
            width=1180,
            height=760,
            min_size=(960, 620),
            text_select=False,
        )
        webview.start(http_server=False, debug=False)
        return 0
    except Exception as error:
        append_log(
            get_data_directory() / "Guardian.log",
            f"Le démarrage de Guardian a échoué : {error}",
        )
        if "--self-test" in sys.argv:
            return 5
        _show_startup_message(
            "Guardian n'a pas pu démarrer. Fermez puis relancez l'application."
        )
        return 1
    finally:
        lock.release()


def _show_startup_message(message: str) -> None:
    """Affiche une explication courte si Guardian ne peut pas ouvrir son interface."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Guardian", message, parent=root)
        root.destroy()
    except Exception:
        print(message)


if __name__ == "__main__":
    raise SystemExit(main())