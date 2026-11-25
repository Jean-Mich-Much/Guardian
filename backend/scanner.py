"""
Repérage des souvenirs personnels à sauvegarder.
"""

from __future__ import annotations

import ctypes
import os
import re
from pathlib import Path
from typing import Iterable
from uuid import UUID


PHOTO_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".webp", ".raw",
    ".heif", ".avif", ".dng", ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2",
    ".raf", ".pef", ".srw", ".psd", ".xcf", ".svg",
}
VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".mpg", ".mpeg", ".3gp",
    ".webm", ".mts", ".m2ts", ".ts", ".vob", ".flv",
}
DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".odt",
    ".docm", ".dot", ".dotx", ".xlsm", ".xltx", ".pptm", ".pps", ".ppsx",
    ".ods", ".odp", ".odg", ".csv", ".md", ".html", ".htm", ".eml", ".msg",
    ".epub", ".mobi", ".pages", ".numbers", ".key", ".pub", ".xps", ".wpd",
}
MUSIC_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma",
    ".aif", ".aiff", ".opus", ".alac", ".mid", ".midi",
}
CATEGORY_NAMES = ("photos", "videos", "documents", "music", "other")
PERSONAL_EXTENSIONS = (
    PHOTO_EXTENSIONS
    | VIDEO_EXTENSIONS
    | DOCUMENT_EXTENSIONS
    | MUSIC_EXTENSIONS
    | {".7z", ".epub", ".mobi", ".rar", ".zip"}
)
EXECUTABLE_EXTENSIONS = {".exe", ".com", ".bat", ".cmd"}
PROGRAM_MARKER_FILES = {
    "pyproject.toml", "setup.py", "setup.cfg",
    "package.json", "package-lock.json", "npm-shrinkwrap.json",
    "cargo.toml", "go.mod", "go.work", "composer.json",
    "gemfile", "pom.xml", "build.gradle", "build.gradle.kts",
    "cmakelists.txt", "dockerfile", ".git",
}
PROGRAM_MARKER_DIRECTORIES = {
    ".git", ".hg", ".svn", "node_modules", "site-packages", ".venv", "venv",
}
PROGRAM_MARKER_SUFFIXES = {".sln", ".csproj", ".vbproj", ".vcxproj", ".fsproj"}
WEAK_PROGRAM_MARKER_FILES = {"requirements.txt", "pipfile", "makefile"}
WEAK_PROGRAM_MARKER_DIRECTORIES = {"__pycache__", ".vscode"}
PROGRAM_SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java",
    ".c", ".h", ".cc", ".cpp", ".cs", ".php", ".rb", ".swift", ".kt",
}
PROGRAM_SOURCE_DIRECTORIES = {"src", "source", "tests", "test", "app", "lib"}

SKIPPED_DIRECTORY_NAMES = {
    "$Recycle.Bin", "System Volume Information", "Windows", "Program Files",
    "Program Files (x86)", "ProgramData", "PerfLogs", "Recovery", "$WinREAgent",
    "WindowsApps", "inetpub", "Temp", "Tmp",
    "node_modules", ".git", ".cache", "AppData",
}
SKIPPED_DIRECTORY_NAMES_LOWER = {name.casefold() for name in SKIPPED_DIRECTORY_NAMES}
SKIPPED_DRIVE_ROOT_NAMES = {"Users"}
SKIPPED_DRIVE_ROOT_NAMES_LOWER = {name.casefold() for name in SKIPPED_DRIVE_ROOT_NAMES}
MAX_DISCOVERY_DEPTH = 2

DUPLICATI_VOLUME = re.compile(
    r"duplicati-(?:b[0-9a-f]{32}\.dblock|i[0-9a-f]{32}\.dindex|"
    r"[0-9]{8}t[0-9]{6}z\.dlist)\.zip(?:\.aes)?",
    re.IGNORECASE,
)


def duplicati_backup_files(file_names: Iterable[str]) -> set[str]:
    """Identifie les volumes d'une sauvegarde Duplicati avec ses noms par défaut."""
    volumes = {name for name in file_names if DUPLICATI_VOLUME.fullmatch(name)}
    lower_names = {name.casefold() for name in volumes}
    if not any(".dblock.zip" in name for name in lower_names) or not any(
        ".dlist.zip" in name for name in lower_names
    ):
        return set()
    return volumes


def category_for_file(file_path: Path) -> str:
    """Classe un fichier dans la catégorie utilisée par l'interface et l'archive."""
    suffix = file_path.suffix.casefold()
    if suffix in PHOTO_EXTENSIONS:
        return "photos"
    if suffix in VIDEO_EXTENSIONS:
        return "videos"
    if suffix in DOCUMENT_EXTENSIONS:
        return "documents"
    if suffix in MUSIC_EXTENSIONS:
        return "music"
    return "other"


def _resolved_path(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except OSError:
        return path.absolute()


def is_path_excluded(path: Path, excluded_paths: Iterable[Path]) -> bool:
    if not excluded_paths:
        return False
    candidate = _resolved_path(path)
    return any(
        candidate == excluded or excluded in candidate.parents
        for excluded in excluded_paths
    )


WINDOWS_KNOWN_FOLDERS = {
    "documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
    "photos": "33E28130-4E1E-4676-835A-98395C3BC3BB",
    "videos": "18989B1D-99B5-455B-841C-AB7C74E4DDFC",
    "desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
    "downloads": "374DE290-123F-4565-9164-39C4925E467B",
    "music": "4BD8D571-6D19-48D3-BE97-422220080E43",
}

FOLDER_NAME_FALLBACKS = {
    "documents": ("Documents", "Mes Documents"),
    "photos": ("Pictures", "Mes Images", "Images"),
    "videos": ("Videos", "Mes Vidéos", "Vidéos", "Movies"),
    "desktop": ("Desktop", "Bureau"),
    "downloads": ("Downloads", "Téléchargements"),
    "music": ("Music", "Musique", "Mes Musiques"),
}


def get_local_fixed_drive_roots() -> list[Path]:
    """Retourne les racines locales que Windows classe comme lecteurs fixes."""
    if os.name != "nt":
        return []

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetLogicalDrives.restype = ctypes.c_uint32
    kernel32.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
    kernel32.GetDriveTypeW.restype = ctypes.c_uint
    drive_mask = int(kernel32.GetLogicalDrives())
    return [
        Path(f"{chr(ord('A') + index)}:\\")
        for index in range(26)
        if drive_mask & (1 << index)
        and kernel32.GetDriveTypeW(f"{chr(ord('A') + index)}:\\") == 3
    ]


def _is_skipped_directory(directory: Path) -> bool:
    return (
        directory.name.casefold() in SKIPPED_DIRECTORY_NAMES_LOWER
        or directory.name.startswith(".")
    )


def contains_program_markers(file_names: Iterable[str], directory_names: Iterable[str]) -> bool:
    """Reconnaît des marqueurs de projet logiciel, sans traiter les journaux comme tels."""
    files = {name.casefold() for name in file_names}
    directories = {name.casefold() for name in directory_names}
    if files & PROGRAM_MARKER_FILES:
        return True
    if any(Path(name).suffix.casefold() in PROGRAM_MARKER_SUFFIXES for name in files):
        return True
    if any(
        name in PROGRAM_MARKER_DIRECTORIES
        or name.endswith((".dist-info", ".egg-info"))
        for name in directories
    ):
        return True
    has_weak_manifest = (
        bool(files & WEAK_PROGRAM_MARKER_FILES)
        or bool(directories & WEAK_PROGRAM_MARKER_DIRECTORIES)
    )
    has_source_code = (
        any(Path(name).suffix.casefold() in PROGRAM_SOURCE_SUFFIXES for name in files)
        or bool(directories & PROGRAM_SOURCE_DIRECTORIES)
    )
    return has_weak_manifest and has_source_code


def is_disk_image_directory(file_names: Iterable[str]) -> bool:
    """Reconnaît les métadonnées caractéristiques d'une image Clonezilla."""
    names = {name.casefold() for name in file_names}
    return "clonezilla-img" in names or {"disk", "parts", "dev-fs.list"} <= names


def discover_personal_directories(
    search_roots: Iterable[Path],
    max_depth: int = MAX_DISCOVERY_DEPTH,
    excluded_paths: Iterable[Path] = (),
) -> list[Path]:
    """Repère les dossiers contenant des fichiers personnels sur deux niveaux."""
    candidates: set[Path] = set()

    for root in search_roots:
        root = Path(root)
        if not root.is_dir():
            continue
        pending = [(root, 0, False)]
        while pending:
            current, depth, has_program_ancestor = pending.pop()
            if is_path_excluded(current, excluded_paths):
                continue
            try:
                with os.scandir(current) as entries:
                    entries = list(entries)
                    file_names: list[str] = []
                    directory_names: list[str] = []
                    subdirectories: list[Path] = []
                    for entry in entries:
                        path = Path(entry.path)
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                directory_names.append(entry.name)
                                if _is_skipped_directory(path):
                                    continue
                                if depth == 0 and path.name.casefold() in SKIPPED_DRIVE_ROOT_NAMES_LOWER:
                                    continue
                                subdirectories.append(path)
                            elif entry.is_file(follow_symlinks=False):
                                file_names.append(entry.name)
                        except OSError:
                            continue

                    backup_files = duplicati_backup_files(file_names)
                    has_personal_file = any(
                        name not in backup_files
                        and Path(name).suffix.casefold() in PERSONAL_EXTENSIONS
                        for name in file_names
                    )
                    current_is_program_directory = depth > 0 and (
                        contains_program_markers(file_names, directory_names)
                        or is_disk_image_directory(file_names)
                        or any(
                            Path(name).suffix.casefold() in EXECUTABLE_EXTENSIONS
                            for name in file_names
                        )
                    )
                    if (
                        depth > 0
                        and has_personal_file
                        and not has_program_ancestor
                        and not current_is_program_directory
                    ):
                        candidates.add(current)

                    program_in_ancestry = (
                        has_program_ancestor or current_is_program_directory
                    )
                    if depth + 1 <= max_depth:
                        pending.extend(
                            (path, depth + 1, program_in_ancestry)
                            for path in subdirectories
                        )
            except OSError:
                continue

    ordered = sorted(candidates, key=lambda path: (len(path.parts), str(path).casefold()))
    selected: list[Path] = []
    for candidate in ordered:
        if any(candidate == parent or parent in candidate.parents for parent in selected):
            continue
        selected.append(candidate)
    return selected


def _unique_directories(directories: Iterable[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for directory in directories:
        path = Path(directory).expanduser()
        try:
            key = os.path.normcase(str(path.resolve(strict=False)))
        except OSError:
            key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)

    ordered = sorted(unique, key=lambda path: (len(path.parts), str(path).casefold()))
    roots: list[Path] = []
    for candidate in ordered:
        if any(candidate == parent or parent in candidate.parents for parent in roots):
            continue
        roots.append(candidate)
    return roots


def _iter_scannable_files(
    root: Path,
    excluded_paths: Iterable[Path] = (),
    trusted_paths: Iterable[Path] | None = None,
    blocked_paths: Iterable[Path] = (),
    explicit_paths: Iterable[Path] = (),
) -> Iterable[Path]:
    trusted = tuple(_resolved_path(path) for path in (trusted_paths or ()))
    blocked = tuple(_resolved_path(path) for path in blocked_paths)
    explicit = tuple(_resolved_path(path) for path in explicit_paths)

    def blocked_by_default(path: Path) -> bool:
        return is_path_excluded(path, blocked) and not is_path_excluded(path, explicit)

    def can_reach_trusted(path: Path) -> bool:
        candidate = _resolved_path(path)
        return any(candidate == item or candidate in item.parents for item in trusted)

    if is_path_excluded(root, excluded_paths) or (
        blocked_by_default(root) and not can_reach_trusted(root)
    ):
        return
    if root.is_file():
        if (
            not blocked_by_default(root)
            and (trusted_paths is None or is_path_excluded(root, trusted)
                 or root.suffix.casefold() in PERSONAL_EXTENSIONS)
        ):
            yield root
        return
    if not root.is_dir():
        return

    try:
        for current, directory_names, file_names in os.walk(root, topdown=True):
            current_path = Path(current)
            full_access = trusted_paths is not None and is_path_excluded(current_path, trusted)
            backup_files = (
                duplicati_backup_files(file_names)
                if trusted_paths is not None and not full_access else set()
            )
            default_blocked = blocked_by_default(current_path)
            unsafe = trusted_paths is not None and not full_access and (
                contains_program_markers(file_names, directory_names)
                or is_disk_image_directory(file_names)
                or any(Path(name).suffix.casefold() in EXECUTABLE_EXTENSIONS for name in file_names)
            )
            if default_blocked or unsafe:
                directory_names[:] = [
                    name for name in directory_names
                    if can_reach_trusted(current_path / name)
                    and not is_path_excluded(current_path / name, excluded_paths)
                ]
                continue
            directory_names[:] = [
                name
                for name in directory_names
                if (full_access or not _is_skipped_directory(current_path / name)
                    or can_reach_trusted(current_path / name))
                and not is_path_excluded(current_path / name, excluded_paths)
                and (not blocked_by_default(current_path / name)
                     or can_reach_trusted(current_path / name))
            ]
            for file_name in file_names:
                path = current_path / file_name
                if (
                    not is_path_excluded(path, excluded_paths)
                    and not blocked_by_default(path)
                    and (file_name not in backup_files or is_path_excluded(path, trusted))
                    and (trusted_paths is None or full_access
                         or is_path_excluded(path, trusted)
                         or path.suffix.casefold() in PERSONAL_EXTENSIONS)
                ):
                    yield path
    except (OSError, PermissionError):
        return


def _windows_known_folder(folder_id: str) -> Path | None:
    class Guid(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    guid = Guid.from_buffer_copy(UUID(folder_id).bytes_le)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(Guid),
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long

    folder_path = ctypes.c_wchar_p()
    result = shell32.SHGetKnownFolderPath(
        ctypes.byref(guid),
        0,
        None,
        ctypes.byref(folder_path),
    )
    try:
        if result != 0 or not folder_path.value:
            return None
        return Path(folder_path.value)
    finally:
        if folder_path:
            ole32 = ctypes.WinDLL("ole32", use_last_error=True)
            ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
            ole32.CoTaskMemFree.restype = None
            ole32.CoTaskMemFree(ctypes.cast(folder_path, ctypes.c_void_p))


def _category_directories(category: str) -> list[Path]:
    home = Path.home()
    if os.name == "nt":
        folder_id = WINDOWS_KNOWN_FOLDERS.get(category)
        if folder_id:
            known_folder = _windows_known_folder(folder_id)
            if known_folder and known_folder.is_dir():
                return [known_folder]

    return [
        home / name
        for name in FOLDER_NAME_FALLBACKS.get(category, ())
        if (home / name).is_dir()
    ]


def get_personal_directories(
    custom_directories: Iterable[Path] | None = None,
    extra_search_roots: Iterable[Path] | None = None,
) -> list[Path]:
    """Retourne les sources connues, ajoutées et repérées sur les lecteurs fixes."""
    directories: list[Path] = []
    for category in ("documents", "photos", "music", "videos", "desktop"):
        for path in _category_directories(category):
            if path not in directories:
                directories.append(path)

    search_roots = [Path.home(), *get_local_fixed_drive_roots()]
    if extra_search_roots:
        search_roots.extend(Path(root) for root in extra_search_roots)
    downloads = _category_directories("downloads")
    directories.extend(
        discover_personal_directories(
            search_roots,
            excluded_paths=[_resolved_path(path) for path in [*downloads, *directories]],
        )
    )
    if custom_directories:
        directories.extend(Path(path) for path in custom_directories)
    return _unique_directories(directories)


def get_directories_by_category(category: str) -> list[Path]:
    """Retourne les dossiers personnel utiles pour une catégorie simple."""
    category = category.lower()
    if category == "other":
        category = "downloads"
    return _category_directories(category)


def scan_directories(
    directories: Iterable[Path] | None = None,
    include_extensions: Iterable[str] | None = None,
    *,
    max_file_size_bytes: int | None = None,
    excluded_paths: Iterable[Path] | None = None,
    trusted_paths: Iterable[Path] | None = None,
    blocked_paths: Iterable[Path] = (),
    explicit_paths: Iterable[Path] = (),
) -> dict:
    """Compte les fichiers, leur taille et leur catégorie dans les dossiers choisis."""
    if max_file_size_bytes is not None and (
        isinstance(max_file_size_bytes, bool)
        or not isinstance(max_file_size_bytes, int)
        or max_file_size_bytes < 1
    ):
        raise ValueError("La taille maximale doit être un nombre positif d'octets.")

    roots = _unique_directories(
        directories if directories is not None else get_personal_directories()
    )
    normalized_exclusions = [
        _resolved_path(Path(path).expanduser())
        for path in (excluded_paths or ())
    ]
    allowed_extensions = (
        {extension.casefold() for extension in include_extensions}
        if include_extensions is not None
        else None
    )
    result = {
        "roots": [str(path) for path in roots],
        "photos": 0,
        "videos": 0,
        "documents": 0,
        "music": 0,
        "other": 0,
        "category_files": {category: 0 for category in CATEGORY_NAMES},
        "category_sizes": {category: 0 for category in CATEGORY_NAMES},
        "files": 0,
        "size": 0,
        "largest_files": [],
    }
    largest: list[tuple[int, str]] = []

    for root in roots:
        for file_path in _iter_scannable_files(
            root, normalized_exclusions, trusted_paths, blocked_paths, explicit_paths
        ):
            suffix = file_path.suffix.casefold()
            if allowed_extensions is not None and suffix not in allowed_extensions:
                continue
            try:
                size = file_path.stat().st_size
                if max_file_size_bytes is not None and size >= max_file_size_bytes:
                    continue
                result["files"] += 1
                result["size"] += size
                largest.append((size, str(file_path)))
            except (OSError, PermissionError):
                continue

            category = category_for_file(file_path)
            result[category] += 1
            result["category_files"][category] += 1
            result["category_sizes"][category] += size

    largest.sort(reverse=True)
    result["largest_files"] = [
        {"path": path, "size": size}
        for size, path in largest[:20]
    ]
    return result