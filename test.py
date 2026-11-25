"""
Tests locaux essentiels du projet Guardian.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from backend.backup_engine import BackupEngine, calculate_sha256
from backend.config_manager import InstanceLock
from backend.crypto_manager import decrypt_file, encrypt_file, verify_password
from backend.usb_detector import select_backup_device
from backend import scanner
from backend.scanner import scan_directories
import main
from main import GuardianApi
from utils import common


def test_api() -> None:
    api = GuardianApi()
    assert api.status()["ready"] is True
    assert isinstance(api.usb()["devices"], list)
    empty_scan = {
        "roots": [],
        "photos": 0,
        "videos": 0,
        "documents": 0,
        "other": 0,
        "files": 0,
        "size": 0,
        "largest_files": [],
    }
    with (
        patch("main.get_personal_directories", return_value=[]),
        patch("main.scan_directories", return_value=empty_scan),
        patch("main.detect_usb_devices", return_value=[]),
        patch(
            "main.get_system_status",
            return_value={"battery": None, "large_file_warnings": []},
        ),
    ):
        assert "files" in api.diagnostic()


def test_backup_rejects_an_empty_category_selection() -> None:
    result = main.api_backup_start(
        main.BackupRequest(mountpoint="unused", categories=[])
    )
    assert not result["success"]
    assert "catégorie" in result["error"]


def test_local_ui_resources_and_translations() -> None:
    frontend = common.frontend_directory()
    page = (frontend / "index.html").read_text(encoding="utf-8")
    assert 'id="screen-home"' in page
    assert 'id="custom-folder-list"' in page
    assert 'id="usb-choice"' in page
    assert 'href="css/base.css"' in page
    assert 'src="js/app.js"' in page
    assert (frontend / "css" / "fonts.css").is_file()
    assert (frontend / "fonts" / "Twemoji.woff2").is_file()
    assert "get_translations" in (frontend / "js" / "i18n.js").read_text(encoding="utf-8")
    assert set(GuardianApi().get_translations()) == {"fr", "en"}
    for script_name in ("app.js", "i18n.js"):
        script = (frontend / "js" / script_name).read_text(encoding="utf-8")
        assert "fetch(" not in script
        assert "EventSource" not in script


def test_native_window_disables_http_server() -> None:
    webview = ModuleType("webview")
    create_window = Mock()
    start = Mock()
    setattr(webview, "create_window", create_window)
    setattr(webview, "start", start)
    with (
        patch.dict(sys.modules, {"webview": webview}),
        patch.object(main.lock, "acquire", return_value=True),
        patch.object(main.lock, "release") as release,
    ):
        assert main.main() == 0

    window_options = create_window.call_args.kwargs
    assert window_options["js_api"] is main.guardian_api
    assert window_options["url"] == (
        common.frontend_directory() / "index.html"
    ).resolve().as_uri()
    assert "html" not in window_options
    start.assert_called_once_with(http_server=False, debug=False)
    release.assert_called_once()


def test_onefile_data_directory_uses_original_executable() -> None:
    executable = Path(tempfile.gettempdir()) / "Guardian" / "Guardian.exe"
    with patch.dict(
        common.__dict__,
        {"__compiled__": SimpleNamespace(original_argv0=str(executable))},
    ):
        assert common.application_directory() == executable.parent


def test_frontend_uses_compiled_runtime_directory() -> None:
    with tempfile.TemporaryDirectory() as directory:
        runtime = Path(directory) / "runtime"
        frontend = runtime / "frontend"
        frontend.mkdir(parents=True)
        containing = Path(directory) / "original-exe"
        containing.mkdir()
        with patch.dict(
            common.__dict__,
            {
                "__compiled__": SimpleNamespace(
                    python_runtime_dir=str(runtime),
                    containing_dir=str(containing),
                )
            },
        ):
            assert common.frontend_directory() == frontend


def test_language_setting_persists() -> None:
    with tempfile.TemporaryDirectory() as directory:
        with patch("main.get_data_directory", return_value=Path(directory)):
            api = GuardianApi()
            api.set_language("en")
            assert api.get_language() == "en"


def test_custom_directories_persist() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        custom = root / "Mes dossiers"
        custom.mkdir()
        custom_file = root / "notes.txt"
        custom_file.write_text("notes", encoding="utf-8")
        with patch("backend.config_manager.get_data_directory", return_value=Path(directory)):
            result = main.api_save_custom_directories(
                [str(custom), str(custom_file), str(custom)]
            )
            assert result["success"]
            expected = [str(custom), str(custom_file)]
            assert result["custom_directories"] == expected
            assert main.api_get_profile()["custom_directories"] == expected


def test_native_folder_picker_returns_selected_directory() -> None:
    with tempfile.TemporaryDirectory() as directory:
        selected = Path(directory)
        window = Mock()
        window.create_file_dialog.return_value = [str(selected)]
        webview = ModuleType("webview")
        setattr(webview, "windows", [window])
        setattr(webview, "FileDialog", SimpleNamespace(FOLDER=20))
        with patch.dict(sys.modules, {"webview": webview}):
            result = main.api_select_folder()

        assert result == {"success": True, "path": str(selected)}
        window.create_file_dialog.assert_called_once_with(20)


def test_native_folder_picker_reports_cancelled_selection() -> None:
    window = Mock()
    window.create_file_dialog.return_value = None
    webview = ModuleType("webview")
    setattr(webview, "windows", [window])
    setattr(webview, "FileDialog", SimpleNamespace(FOLDER=20))
    with patch.dict(sys.modules, {"webview": webview}):
        result = main.api_select_folder()
    assert result == {"success": False, "cancelled": True}


def test_native_file_picker_returns_selected_files() -> None:
    with tempfile.TemporaryDirectory() as directory:
        first = Path(directory) / "premier.txt"
        second = Path(directory) / "second.pdf"
        first.write_text("1", encoding="utf-8")
        second.write_text("2", encoding="utf-8")
        window = Mock()
        window.create_file_dialog.return_value = [str(first), str(second)]
        webview = ModuleType("webview")
        setattr(webview, "windows", [window])
        setattr(webview, "FileDialog", SimpleNamespace(OPEN=10))
        with patch.dict(sys.modules, {"webview": webview}):
            result = main.api_select_files()

    assert result == {
        "success": True,
        "paths": [str(first.resolve()), str(second.resolve())],
    }
    window.create_file_dialog.assert_called_once_with(10, allow_multiple=True)


def test_windows_restore_shortcuts_use_shell_link_files() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        desktop = root / "Desktop"
        target = root / "Restored"
        desktop.mkdir()
        target.mkdir()
        completed = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch("main.get_directories_by_category", return_value=[desktop]),
            patch("main.sys.platform", "win32"),
            patch("main.subprocess.run", return_value=completed) as run,
        ):
            result = main._create_restore_shortcuts({target})

        script = base64.b64decode(run.call_args.args[0][-1]).decode("utf-16le")
        payload = json.loads(
            base64.b64decode(run.call_args.kwargs["input"]).decode("utf-8")
        )

    assert result["success"]
    assert "WScript.Shell" in script
    assert ".lnk" in script
    assert payload["items"][0]["target"] == str(target.resolve())


def _write_restore_fixture(
    root: Path,
    relative: str,
    contents: bytes,
    source_path: Path,
    source_root: Path,
    source_root_is_file: bool = False,
) -> tuple[Path, Path]:
    usb = root / "usb"
    archive = usb / "Sauvegardes"
    backup_file = archive / Path(*relative.split("/"))
    backup_file.parent.mkdir(parents=True)
    backup_file.write_bytes(contents)
    index = usb / ".guardian" / "guardian-index.json"
    index.parent.mkdir(parents=True)
    index.write_text(
        json.dumps(
            {
                relative: {
                    "source_path": str(source_path),
                    "source_root": str(source_root),
                    "source_root_is_file": source_root_is_file,
                    "source_size": len(contents),
                    "source_sha256": calculate_sha256(backup_file),
                    "protected": False,
                }
            }
        ),
        encoding="utf-8",
    )
    return usb, backup_file


def test_restore_skips_an_identical_file_at_its_original_location() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source_root = root / "Documents"
        source_root.mkdir()
        source = source_root / "notes.txt"
        source.write_bytes(b"same")
        usb, _ = _write_restore_fixture(
            root,
            "Documents/notes.txt",
            b"same",
            source,
            source_root,
        )
        shortcuts = {"success": True, "directory": str(root / "Desktop")}
        with patch("main._create_restore_shortcuts", return_value=shortcuts):
            result = main.api_restore(main.RestoreRequest(str(usb)))

        assert result["success"]
        assert result["restored"] == 0
        assert result["skipped"] == 1
        assert result["fallback_used"] is False


def test_restore_replaces_different_same_size_file_regardless_of_date() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source_root = root / "Documents"
        source_root.mkdir()
        source = source_root / "notes.txt"
        source.write_bytes(b"old")
        future = time.time() + 86400
        os.utime(source, (future, future))
        usb, _ = _write_restore_fixture(
            root,
            "Documents/notes.txt",
            b"new",
            source,
            source_root,
        )
        shortcuts = {"success": True, "directory": str(root / "Desktop")}
        with patch("main._create_restore_shortcuts", return_value=shortcuts):
            result = main.api_restore(main.RestoreRequest(str(usb)))

        assert result["success"]
        assert result["restored"] == 1
        assert result["skipped"] == 0
        assert source.read_bytes() == b"new"


def test_restore_rejects_a_backup_file_with_a_hash_mismatch() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        missing_root = root / "old-pc" / "Documents"
        usb, backup_file = _write_restore_fixture(
            root,
            "Documents/notes.txt",
            b"expected",
            missing_root / "notes.txt",
            missing_root,
        )
        backup_file.write_bytes(b"corrupted")
        restore_root = root / "new-pc" / "Documents" / "GuardianRestored"
        restore_root.mkdir(parents=True)
        shortcuts = {"success": True, "directory": str(root / "Desktop")}
        with (
            patch("main._default_restore_root", return_value=restore_root),
            patch("main._create_restore_shortcuts", return_value=shortcuts),
        ):
            result = main.api_restore(main.RestoreRequest(str(usb)))

        assert not result["success"]
        assert result["failed"] == 1
        assert result["restored"] == 0
        assert not (restore_root / "Documents" / "notes.txt").exists()


def test_restore_uses_documents_fallback_when_original_root_is_missing() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        documents = root / "new-pc" / "Documents"
        documents.mkdir(parents=True)
        missing_root = root / "old-pc" / "Documents"
        usb, _ = _write_restore_fixture(
            root,
            "Documents/notes.txt",
            b"backup",
            missing_root / "notes.txt",
            missing_root,
        )
        shortcuts = {"success": True, "directory": str(root / "Desktop")}
        with (
            patch("main.get_directories_by_category", return_value=[documents]),
            patch("main._create_restore_shortcuts", return_value=shortcuts),
        ):
            result = main.api_restore(main.RestoreRequest(str(usb)))

        destination = documents / "GuardianRestored" / "Documents" / "notes.txt"
        assert result["success"]
        assert result["fallback_used"]
        assert destination.read_bytes() == b"backup"


def test_restore_can_use_a_user_chosen_destination() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source_root = root / "Documents"
        source_root.mkdir()
        source = source_root / "notes.txt"
        source.write_bytes(b"backup")
        usb, _ = _write_restore_fixture(
            root,
            "Documents/notes.txt",
            b"backup",
            source,
            source_root,
        )
        chosen = root / "My chosen folder"
        chosen.mkdir()
        shortcuts = {"success": True, "directory": str(root / "Desktop")}
        with patch("main._create_restore_shortcuts", return_value=shortcuts):
            result = main.api_restore(
                main.RestoreRequest(str(usb), destination_directory=str(chosen))
            )

        assert result["success"]
        assert result["destination_mode"] == "custom"
        assert (chosen / "Documents" / "notes.txt").read_bytes() == b"backup"


def test_windows_cache_flush_covers_all_volumes() -> None:
    completed = subprocess.CompletedProcess([], 0, "", "")
    with (
        patch("main.sys.platform", "win32"),
        patch("main.subprocess.run", return_value=completed) as run,
    ):
        error = main._flush_volume_cache(Path("F:\\"))

    assert error is None
    command = run.call_args.args[0]
    script = command[-1]
    assert "Get-Partition -DiskNumber" in script
    assert "Write-VolumeCache -DriveLetter" in script
    assert "InvokeVerb" not in script


def test_windows_cache_flush_reports_failure() -> None:
    completed = subprocess.CompletedProcess([], 1, "", "Access denied")
    with (
        patch("main.sys.platform", "win32"),
        patch("main.subprocess.run", return_value=completed),
    ):
        error = main._flush_volume_cache(Path("F:\\"))

    assert "Access denied" in error


def test_linux_cache_flush_calls_sync() -> None:
    with (
        patch("main.sys.platform", "linux"),
        patch("main.os.sync", create=True) as sync,
    ):
        error = main._flush_volume_cache(Path("."))
    assert error is None
    sync.assert_called_once()


def test_scan() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "photo.jpg").write_bytes(b"photo")
        (root / "notes.pdf").write_bytes(b"notes")
        result = scan_directories([root])
        assert result["files"] == 2
        assert result["photos"] == 1
        photo_scan = scan_directories([root], include_extensions=scanner.PHOTO_EXTENSIONS)
        assert photo_scan["files"] == 1
        assert photo_scan["photos"] == 1


def test_scan_counts_music_and_applies_size_and_path_filters() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        excluded = root / "Private"
        excluded.mkdir()
        (root / "song.mp3").write_bytes(b"music")
        (root / "at-limit.mp3").write_bytes(b"123456")
        (root / "photo.jpg").write_bytes(b"img")
        (excluded / "notes.pdf").write_bytes(b"note")

        result = scan_directories(
            [root],
            max_file_size_bytes=6,
            excluded_paths=[excluded],
        )

    assert result["files"] == 2
    assert result["music"] == 1
    assert result["photos"] == 1
    assert result["documents"] == 0
    assert result["category_sizes"]["music"] == len(b"music")
    assert result["category_sizes"]["photos"] == len(b"img")


def test_scan_accepts_a_selected_file_as_a_source() -> None:
    with tempfile.TemporaryDirectory() as directory:
        selected = Path(directory) / "notes.pdf"
        selected.write_bytes(b"notes")
        result = scan_directories([selected])

    assert result["roots"] == [str(selected)]
    assert result["files"] == 1
    assert result["documents"] == 1
    assert result["size"] == len(b"notes")


def test_custom_diagnostic_scans_only_added_sources() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        selected = root / "notes.pdf"
        selected.write_bytes(b"notes")
        device = {
            "mountpoint": str(root / "usb"),
            "free": 1000,
            "filesystem": "NTFS",
        }
        selection = {"selected": device, "requires_choice": False}
        with (
            patch("main.detect_usb_devices", return_value=[device]),
            patch("main.select_backup_device", return_value=selection),
            patch(
                "main.load_profile",
                return_value={"custom_directories": [str(selected)]},
            ),
            patch("main.get_personal_directories") as get_personal_directories,
            patch(
                "main.get_system_status",
                return_value={"battery": None, "large_file_warnings": []},
            ),
        ):
            result = main.api_diagnostic(device["mountpoint"], "custom")

    assert result["files"] == 1
    assert result["directories"] == [str(selected)]
    get_personal_directories.assert_not_called()


def test_discovery_is_bounded_and_skips_system_directories() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        images = root / "Photos perso" / "Albums"
        images.mkdir(parents=True)
        (images / "photo.jpg").write_bytes(b"photo")

        too_deep = root / "Archives" / "Niveau 2" / "Niveau 3"
        too_deep.mkdir(parents=True)
        (too_deep / "document.pdf").write_bytes(b"document")

        program_data = root / "ProgramData" / "Cache perso"
        program_data.mkdir(parents=True)
        (program_data / "document.pdf").write_bytes(b"document")

        python = root / "Python"
        python.mkdir()
        (python / "python.exe").write_bytes(b"executable")
        (python / "README.txt").write_text("runtime files", encoding="utf-8")
        fixture = python / "Lib" / "test" / "test_email" / "data"
        fixture.mkdir(parents=True)
        (fixture / "sndhdr.wav").write_bytes(b"fixture")

        found = scanner.discover_personal_directories([root])
        assert images in found
        assert python not in found
        assert not any(path.is_relative_to(python) for path in found)


def test_discovery_skips_project_assets_without_executables() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        project = root / "sglang"
        (project / ".git").mkdir(parents=True)
        (project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        docs = project / "docs"
        docs.mkdir()
        (docs / "logo.png").write_bytes(b"program asset")

        found = scanner.discover_personal_directories([root])

        assert project not in found
        assert docs not in found


def test_log_files_do_not_mark_personal_directories_as_programs() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        personal = root / "Photos"
        personal.mkdir()
        (personal / "photo.png").write_bytes(b"personal photo")
        (personal / "application.log").write_text("activity", encoding="utf-8")

        assert personal in scanner.discover_personal_directories([root])


def test_weak_project_markers_need_source_code() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        notes = root / "Notes"
        notes.mkdir()
        (notes / "requirements.txt").write_text("ordinary text", encoding="utf-8")
        (notes / "photo.png").write_bytes(b"personal photo")

        project = root / "Application"
        project.mkdir()
        (project / "requirements.txt").write_text("requests", encoding="utf-8")
        (project / "main.py").write_text("print('app')", encoding="utf-8")
        (project / "logo.png").write_bytes(b"program asset")

        found = scanner.discover_personal_directories([root])

        assert notes in found
        assert project not in found


def test_personal_directories_include_added_and_external_sources() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        home = root / "home"
        added = root / "Dossier ajouté"
        removable = root / "source-usb"
        discovered = removable / "Papiers"
        home.mkdir()
        added.mkdir()
        (added / "outil.exe").write_bytes(b"executable")
        (added / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        discovered.mkdir(parents=True)
        (discovered / "facture.pdf").write_bytes(b"pdf")

        with (
            patch("backend.scanner.Path.home", return_value=home),
            patch("backend.scanner.get_local_fixed_drive_roots", return_value=[]),
            patch("backend.scanner._category_directories", return_value=[]),
        ):
            directories = scanner.get_personal_directories(
                [added],
                extra_search_roots=[removable],
            )

        assert added in directories
        assert discovered in directories


def test_automatic_selection_distinguishes_trusted_and_discovered_sources() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        known = root / "Documents"
        project = known / "IActu"
        (project / ".git").mkdir(parents=True)
        (project / ".git" / "config").write_text("settings", encoding="utf-8")
        (project / "index.php").write_text("php", encoding="utf-8")
        (project / "script.py").write_text("python", encoding="utf-8")
        downloads = known / "Downloads"
        downloads.mkdir()
        (downloads / "download.pdf").write_bytes(b"download")
        selected_download = downloads / "selected"
        selected_download.mkdir()
        (selected_download / "chosen.py").write_text("chosen", encoding="utf-8")
        discovered = root / "Memories"
        discovered.mkdir()
        (discovered / "photo.jpg").write_bytes(b"photo")
        (discovered / "unknown.bin").write_bytes(b"binary")
        nested_program = discovered / "Application"
        nested_program.mkdir()
        (nested_program / "package.json").write_text("{}", encoding="utf-8")
        (nested_program / "logo.png").write_bytes(b"logo")
        rescue = root / "Backup-Windows-Rescuezilla"
        rescue.mkdir()
        (rescue / "clonezilla-img").write_bytes(b"")
        (rescue / "Info-dmi.txt").write_bytes(b"metadata")
        usb = root / "usb"
        usb.mkdir()

        assert rescue not in scanner.discover_personal_directories([root])
        sources = [known, discovered]
        scan = scan_directories(
            sources,
            trusted_paths=[known, selected_download],
            blocked_paths=[downloads],
            explicit_paths=[selected_download],
        )
        result = BackupEngine().run(
            sources,
            usb,
            trusted_paths=[known, selected_download],
            blocked_paths=[downloads],
            explicit_paths=[selected_download],
        )
        archive = usb / "Sauvegardes"
        copied = {
            path.name for path in archive.rglob("*")
            if path.is_file() and path.name not in {"Guardian.log", "guardian-valid.marker"}
        }
        assert result["success"]
        assert scan["files"] == result["copied"] == 5
        assert copied == {"config", "index.php", "script.py", "chosen.py", "photo.jpg"}


def test_recognized_rescuezilla_metadata_and_explicit_override() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rescue = root / "SystemImage"
        rescue.mkdir()
        for name in ("disk", "parts", "dev-fs.list", "Info-dmi.txt"):
            (rescue / name).write_bytes(b"metadata")
        assert rescue not in scanner.discover_personal_directories([root])
        assert scan_directories([rescue], trusted_paths=[])["files"] == 0
        assert scan_directories([rescue], trusted_paths=[rescue])["files"] == 4


def test_duplicati_volumes_are_excluded_without_losing_nearby_files() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        backup = root / "Archives"
        backup.mkdir()
        block = "duplicati-b69a2a32a50bb4c6d8780389efdbf7442.dblock.zip"
        index = "duplicati-i84de11dd9a334727a080a3cdedc11f76.dindex.zip"
        listing = "duplicati-20171109T100606Z.dlist.zip"
        for name in (block, index, listing):
            (backup / name).write_bytes(b"backup volume")

        assert backup not in scanner.discover_personal_directories([root])

        (backup / "personal.zip").write_bytes(b"personal archive")
        (backup / "duplicati-not-a-volume.dblock.zip").write_bytes(b"personal archive")
        assert backup in scanner.discover_personal_directories([root])
        assert scan_directories([backup], trusted_paths=[])["files"] == 2
        assert scan_directories([backup])["files"] == 5
        assert scan_directories([backup], trusted_paths=[backup])["files"] == 5
        assert scan_directories([backup], trusted_paths=[backup / block])["files"] == 3

        usb = root / "usb"
        usb.mkdir()
        result = BackupEngine().run([backup], usb, trusted_paths=[])
        copied = {path.name for path in (usb / "Sauvegardes").rglob("*.zip")}
        assert result["success"]
        assert result["copied"] == 2
        assert copied == {"personal.zip", "duplicati-not-a-volume.dblock.zip"}

        (backup / listing).unlink()
        assert scan_directories([backup], trusted_paths=[])["files"] == 4

        (backup / (listing + ".aes")).write_bytes(b"encrypted listing")
        assert scan_directories([backup], trusted_paths=[])["files"] == 2


def test_downloads_are_not_automatically_selected() -> None:
    with tempfile.TemporaryDirectory() as directory:
        home = Path(directory)
        downloads = home / "Downloads"
        downloads.mkdir()
        (downloads / "invoice.pdf").write_bytes(b"invoice")
        with (
            patch("backend.scanner.Path.home", return_value=home),
            patch("backend.scanner.get_local_fixed_drive_roots", return_value=[]),
            patch(
                "backend.scanner._category_directories",
                side_effect=lambda category: [downloads] if category == "downloads" else [],
            ),
        ):
            assert downloads not in scanner.get_personal_directories()
            assert downloads in scanner.get_personal_directories([downloads])


def test_diagnostic_and_backup_apply_the_same_source_policy() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        known = root / "Documents"
        discovered = root / "Memories"
        downloads = known / "Downloads"
        known.mkdir()
        discovered.mkdir()
        downloads.mkdir()
        (known / "code.php").write_bytes(b"php")
        (downloads / "download.pdf").write_bytes(b"download")
        (discovered / "photo.jpg").write_bytes(b"photo")
        (discovered / "utility.bin").write_bytes(b"binary")
        usb = root / "usb"
        usb.mkdir()
        device = {"mountpoint": str(usb), "free": 100000, "filesystem": "NTFS"}
        selection = {"selected": device, "requires_choice": False}
        known_by_category = {"documents": [known], "downloads": [downloads]}
        with (
            patch("main.detect_usb_devices", return_value=[device]),
            patch("main.select_backup_device", return_value=selection),
            patch("main.load_profile", return_value={"custom_directories": []}),
            patch("main.get_personal_directories", return_value=[known, discovered]),
            patch(
                "main.get_directories_by_category",
                side_effect=lambda category: known_by_category.get(category, []),
            ),
            patch("main.get_system_status", return_value={"battery": None, "large_file_warnings": []}),
            patch("main.prevent_sleep", return_value=None),
            patch("main.allow_sleep"),
            patch("main._flush_volume_cache", return_value=None),
            patch("main.threading.Thread") as thread,
            patch("main.event_queue", new=main.Queue()) as events,
        ):
            diagnostic = main.api_diagnostic(str(usb), "all")
            started = main.api_backup_start(main.BackupRequest(mountpoint=str(usb)))
            assert started["success"]
            thread.call_args.kwargs["target"]()
            result = events.get_nowait()
            while result["type"] != "backup_result":
                result = events.get_nowait()

        assert diagnostic["files"] == 2
        assert result["success"]
        assert result["copied"] == diagnostic["files"]
        assert (usb / "Sauvegardes" / "Documents" / "code.php").is_file()
        assert (usb / "Sauvegardes" / "Autres emplacements" / "Memories" / "photo.jpg").is_file()


def test_backup_keeps_windows_folders_intact_and_separates_discovered_sources() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        drive = root / "drive"
        known = drive / "Mes documents"
        project = known / "IActu"
        (project / ".git").mkdir(parents=True)
        (project / ".git" / "config").write_text("config", encoding="utf-8")
        (project / "index.php").write_bytes(b"php")
        (project / "readme.txt").write_bytes(b"text")
        (project / "photo.jpg").write_bytes(b"image")
        discovered = drive / "Souvenirs"
        discovered.mkdir()
        (discovered / "photo.jpg").write_bytes(b"other image")
        (discovered / "unknown.bin").write_bytes(b"unknown")
        usb = root / "usb"
        usb.mkdir()

        result = BackupEngine().run(
            [drive, known], usb, trusted_paths=[known],
            known_folders={"Documents": [known]},
        )
        archive = usb / "Sauvegardes"
        assert result["success"]
        assert result["copied"] == 5
        assert (archive / "Documents" / "IActu" / ".git" / "config").is_file()
        assert (archive / "Documents" / "IActu" / "index.php").is_file()
        assert (archive / "Documents" / "IActu" / "readme.txt").is_file()
        assert (archive / "Documents" / "IActu" / "photo.jpg").is_file()
        assert (archive / "Autres emplacements" / "drive" / "Souvenirs" / "photo.jpg").is_file()
        assert not list(archive.rglob("unknown.bin"))
        assert len(list(archive.rglob("index.php"))) == 1
        (project / "index.php").write_bytes(b"updated php")
        repeated = BackupEngine().run(
            [drive, known], usb, trusted_paths=[known],
            known_folders={"Documents": [known]},
        )
        assert repeated["success"]
        assert (archive / "Documents" / "IActu" / "index.php").read_bytes() == b"updated php"
        assert len(list(archive.rglob("index.php"))) == 1

        selected_usb = root / "selected-usb"
        selected_usb.mkdir()
        selected = BackupEngine().run(
            [known], selected_usb, trusted_paths=[known],
            included_categories=["documents"], known_folders={"Documents": [known]},
        )
        assert selected["success"]
        assert selected["copied"] == 1
        assert (selected_usb / "Sauvegardes" / "Documents" / "IActu" / "readme.txt").is_file()
        assert not list((selected_usb / "Sauvegardes").rglob("index.php"))


def test_backup_preserves_existing_file_owned_by_another_source() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        known = root / "known"
        known.mkdir()
        source = known / "note.txt"
        source.write_bytes(b"new")
        old_source = root / "old" / "note.txt"
        usb, old_backup = _write_restore_fixture(
            root, "Documents/note.txt", b"old", old_source, old_source.parent
        )

        result = BackupEngine().run(
            [known], usb, trusted_paths=[known], known_folders={"Documents": [known]}
        )
        assert not result["success"]
        assert result["failed"] == 1
        assert old_backup.read_bytes() == b"old"


def test_backup_keeps_old_index_and_refuses_a_corrupt_index() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        known = root / "known"
        known.mkdir()
        (known / "note.txt").write_bytes(b"new")
        old_source = root / "old" / "note.txt"
        usb, old_backup = _write_restore_fixture(
            root, "Documents/note.txt", b"old", old_source, old_source.parent
        )
        index = usb / ".guardian" / "guardian-index.json"
        legacy = usb / "Sauvegardes" / "guardian-index.json"
        index.replace(legacy)
        result = BackupEngine().run(
            [known], usb, trusted_paths=[known], known_folders={"Documents": [known]}
        )
        assert not result["success"]
        assert old_backup.read_bytes() == b"old"
        assert "Documents/note.txt" in json.loads(index.read_text(encoding="utf-8"))

        index.write_text("{", encoding="utf-8")
        result = BackupEngine().run(
            [known], usb, trusted_paths=[known], known_folders={"Documents": [known]}
        )
        assert not result["success"]
        assert "index" in result["error"]
        assert index.read_text(encoding="utf-8") == "{"
        assert old_backup.read_bytes() == b"old"


def test_restore_uses_file_categories_and_prefers_new_layout_over_old() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        known = root / "known"
        known.mkdir()
        source = known / "code.php"
        source.write_bytes(b"new")
        (known / "note.txt").write_bytes(b"note")
        usb, old_backup = _write_restore_fixture(
            root, "Autres/known/code.php", b"old", source, known
        )
        result = BackupEngine().run(
            [known], usb, trusted_paths=[known], known_folders={"Documents": [known]}
        )
        assert result["success"]
        assert old_backup.read_bytes() == b"old"
        source.write_bytes(b"changed")
        (known / "note.txt").unlink()
        shortcuts = {"success": True, "directory": str(root)}
        with patch("main._create_restore_shortcuts", return_value=shortcuts):
            restored = main.api_restore(
                main.RestoreRequest(str(usb), categories=["other"])
            )
        assert restored["success"]
        assert source.read_bytes() == b"new"
        assert not (known / "note.txt").exists()


def test_windows_folders_are_not_scanned_again_during_discovery() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        known = root / "Known"
        known.mkdir()
        (known / "note.txt").write_bytes(b"document")
        elsewhere = root / "Elsewhere"
        elsewhere.mkdir()
        (elsewhere / "photo.jpg").write_bytes(b"photo")
        real_scandir = os.scandir
        visited: list[Path] = []

        def capture_scandir(path: Path):
            visited.append(Path(path))
            return real_scandir(path)

        with (
            patch("backend.scanner.Path.home", return_value=root),
            patch("backend.scanner.get_local_fixed_drive_roots", return_value=[]),
            patch(
                "backend.scanner._category_directories",
                side_effect=lambda category: [known] if category == "documents" else [],
            ),
            patch("backend.scanner.os.scandir", side_effect=capture_scandir),
        ):
            directories = scanner.get_personal_directories()

        assert known in directories and elsewhere in directories
        assert known not in visited


def test_backup_device_selection() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        fuller = {
            "mountpoint": str(root / "A"),
            "total": 1000,
            "free": 200,
        }
        emptier = {
            "mountpoint": str(root / "B"),
            "total": 1000,
            "free": 800,
        }
        assert select_backup_device([fuller, emptier])["selected"] == emptier

        archive = Path(fuller["mountpoint"]) / "Sauvegardes"
        archive.mkdir(parents=True)
        (archive / "guardian-valid.marker").write_text("valid", encoding="utf-8")
        assert select_backup_device([fuller, emptier])["selected"] == fuller

        other_archive = Path(emptier["mountpoint"]) / "Sauvegardes"
        other_archive.mkdir(parents=True)
        (other_archive / "guardian-valid.marker").write_text("valid", encoding="utf-8")
        assert select_backup_device([fuller, emptier])["requires_choice"]

        tied_a = {**fuller, "mountpoint": str(root / "C")}
        tied_b = {**fuller, "mountpoint": str(root / "D")}
        assert select_backup_device([tied_a, tied_b])["requires_choice"]


def test_windows_redirected_personal_folders() -> None:
    if scanner.os.name != "nt":
        return

    with tempfile.TemporaryDirectory() as directory:
        home = Path(directory) / "home"
        pictures = Path(directory) / "Images"
        home.mkdir()
        pictures.mkdir()
        known_folders = {
            scanner.WINDOWS_KNOWN_FOLDERS["photos"]: pictures,
        }
        with patch(
            "backend.scanner._windows_known_folder",
            side_effect=lambda folder_id: known_folders.get(folder_id),
        ), patch("backend.scanner.Path.home", return_value=home), patch(
            "backend.scanner.get_local_fixed_drive_roots", return_value=[]
        ):
            assert scanner.get_directories_by_category("photos") == [pictures]
            assert pictures in scanner.get_personal_directories()


def test_crypto() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "souvenir.txt"
        protected = root / "souvenir.guardian"
        restored = root / "restored.txt"
        source.write_text("Nos souvenirs", encoding="utf-8", newline="\n")
        encrypt_file(source, protected, "code secret")
        assert verify_password(protected, "code secret")
        assert decrypt_file(protected, restored, "code secret")
        assert restored.read_text(encoding="utf-8") == "Nos souvenirs"


def test_backup() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source"
        usb = root / "usb"
        source.mkdir()
        usb.mkdir()
        (source / "souvenir.txt").write_text("test", encoding="utf-8", newline="\n")
        nested_directory = source / "Album" / "Sous-dossier"
        nested_directory.mkdir(parents=True)
        (nested_directory / "photo.jpg").write_bytes(b"photo")
        temp_directory = source / "Temp"
        temp_directory.mkdir()
        (temp_directory / "temporary.pdf").write_bytes(b"temporary")
        result = BackupEngine().run([source], usb, retention_count=2)
        assert result["success"]
        assert result["copied"] == 2
        assert (
            usb / "Sauvegardes" / "Photos" / "source" / "Album" / "Sous-dossier" / "photo.jpg"
        ).is_file()
        assert not (
            usb / "Sauvegardes" / "Documents" / "source" / "Temp" / "temporary.pdf"
        ).exists()


def test_backup_applies_categories_size_limit_and_exclusions() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source"
        excluded = source / "Private"
        usb = root / "usb"
        excluded.mkdir(parents=True)
        usb.mkdir()
        (source / "photo.jpg").write_bytes(b"img")
        (source / "note.pdf").write_bytes(b"doc")
        (source / "at-limit.pdf").write_bytes(b"12345")
        (source / "song.mp3").write_bytes(b"song")
        (source / "other.bin").write_bytes(b"other")
        (excluded / "hidden.jpg").write_bytes(b"hidden")

        result = BackupEngine().run(
            [source],
            usb,
            included_categories={"photos", "documents", "music"},
            max_file_size_bytes=5,
            excluded_paths=[excluded],
        )

        archive = usb / "Sauvegardes"
        assert result["success"]
        assert result["copied"] == 3
        assert (archive / "Photos" / "source" / "photo.jpg").is_file()
        assert (archive / "Documents" / "source" / "note.pdf").is_file()
        assert (archive / "Musique" / "source" / "song.mp3").is_file()
        assert not (archive / "Documents" / "source" / "at-limit.pdf").exists()
        assert not (archive / "Autres" / "source" / "other.bin").exists()
        assert not (archive / "Photos" / "source" / "Private" / "hidden.jpg").exists()


def test_backup_flushes_periodically_and_at_completion() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source"
        usb = root / "usb"
        source.mkdir()
        usb.mkdir()
        (source / "first.txt").write_text("1", encoding="utf-8")
        (source / "second.txt").write_text("2", encoding="utf-8")
        flushes: list[Path] = []
        engine = BackupEngine()

        with patch("backend.backup_engine.CACHE_FLUSH_INTERVAL_BYTES", 1):
            result = engine.run(
                [source],
                usb,
                cache_flush_callback=lambda mountpoint: flushes.append(mountpoint),
            )

        assert result["success"]
        assert result["safe_to_remove"]
        assert len(flushes) == 2


def test_file_copy_does_not_force_disk_flush_for_each_block() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source.bin"
        destination = root / "destination.bin"
        log_path = root / "Guardian.log"
        source.write_bytes(b"x" * (2 * 1024 * 1024))

        with patch("backend.backup_engine.os.fsync") as fsync:
            success, _, _ = BackupEngine()._copy_atomically(
                source,
                destination,
                None,
                log_path,
            )

        assert success
        fsync.assert_not_called()


def test_backup_stops_on_checkpoint_flush_failure() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source"
        usb = root / "usb"
        source.mkdir()
        usb.mkdir()
        (source / "first.txt").write_text("1", encoding="utf-8")
        (source / "second.txt").write_text("2", encoding="utf-8")
        flush_count = 0

        def flush_cache(_mountpoint: Path) -> str | None:
            nonlocal flush_count
            flush_count += 1
            return "échec intermédiaire" if flush_count == 1 else None

        with patch("backend.backup_engine.CACHE_FLUSH_INTERVAL_BYTES", 1):
            result = BackupEngine().run(
                [source],
                usb,
                cache_flush_callback=flush_cache,
            )

        assert not result["success"]
        assert result["safe_to_remove"]
        assert result["copied"] == 1
        assert flush_count == 2
        assert not (usb / "Sauvegardes" / "guardian-valid.marker").exists()


def test_backup_flush_failure_blocks_safe_removal() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source"
        usb = root / "usb"
        source.mkdir()
        usb.mkdir()
        (source / "souvenir.txt").write_text("test", encoding="utf-8")

        result = BackupEngine().run(
            [source],
            usb,
            cache_flush_callback=lambda _mountpoint: "échec de synchronisation",
        )

        assert not result["success"]
        assert not result["safe_to_remove"]
        assert "synchronisation" in result["error"]
        assert not (usb / "Sauvegardes" / "guardian-valid.marker").exists()


def test_backup_preserves_added_folder_names() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source_a = root / "Travail"
        source_b = root / "Personnel"
        usb = root / "usb"
        source_a.mkdir()
        source_b.mkdir()
        usb.mkdir()
        (source_a / "note.txt").write_text("A", encoding="utf-8")
        (source_b / "note.txt").write_text("B", encoding="utf-8")
        legacy_manifest = usb / "Sauvegardes" / "guardian-index.json"
        legacy_manifest.parent.mkdir()
        legacy_manifest.write_text("{}", encoding="utf-8")

        result = BackupEngine().run([source_a], usb)
        assert result["success"]
        result = BackupEngine().run([source_b], usb)
        assert result["success"]
        assert (
            usb / "Sauvegardes" / "Documents" / "Travail" / "note.txt"
        ).read_text(encoding="utf-8") == "A"
        assert (
            usb / "Sauvegardes" / "Documents" / "Personnel" / "note.txt"
        ).read_text(encoding="utf-8") == "B"
        index_path = usb / ".guardian" / "guardian-index.json"
        assert index_path.is_file()
        assert not (usb / "Sauvegardes" / "guardian-index.json").exists()
        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert index["Documents/Travail/note.txt"]["source_path"] == str(
            (source_a / "note.txt").resolve()
        )
        assert index["Documents/Travail/note.txt"]["source_root"] == str(
            source_a.resolve()
        )
        assert "Documents/Personnel/note.txt" in index


def test_backup_copies_a_selected_file_without_scanning_its_folder() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "Selection" / "wanted.txt"
        unrelated = source.parent / "unrelated.txt"
        usb = root / "usb"
        source.parent.mkdir()
        usb.mkdir()
        source.write_text("wanted", encoding="utf-8")
        unrelated.write_text("not selected", encoding="utf-8")

        result = BackupEngine().run([source], usb)

        destination = (
            usb
            / "Sauvegardes"
            / "Documents"
            / "Fichiers ajoutés"
            / "Selection"
            / "wanted.txt"
        )
        assert result["success"]
        assert result["copied"] == 1
        assert destination.read_text(encoding="utf-8") == "wanted"
        assert not (
            usb
            / "Sauvegardes"
            / "Documents"
            / "Fichiers ajoutés"
            / "Selection"
            / "unrelated.txt"
        ).exists()


def test_backup_disambiguates_selected_files_with_same_parent_name() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source_a = root / "A" / "Selection" / "notes.txt"
        source_b = root / "B" / "Selection" / "notes.txt"
        usb = root / "usb"
        source_a.parent.mkdir(parents=True)
        source_b.parent.mkdir(parents=True)
        usb.mkdir()
        source_a.write_text("A", encoding="utf-8")
        source_b.write_text("B", encoding="utf-8")

        result = BackupEngine().run([source_a, source_b], usb)

        selected_folder = usb / "Sauvegardes" / "Documents" / "Fichiers ajoutés"
        destinations = [
            folder / "notes.txt"
            for folder in selected_folder.glob("Selection-*")
            if (folder / "notes.txt").is_file()
        ]
        assert result["success"]
        assert result["copied"] == 2
        assert len(destinations) == 2
        assert {path.read_text(encoding="utf-8") for path in destinations} == {"A", "B"}


def test_photo_backup_excludes_non_photos() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "Images"
        usb = root / "usb"
        source.mkdir()
        usb.mkdir()
        (source / "photo.jpg").write_bytes(b"photo")
        (source / "notes.txt").write_text("notes", encoding="utf-8")

        result = BackupEngine().run(
            [source],
            usb,
            include_extensions=scanner.PHOTO_EXTENSIONS,
        )
        archive = usb / "Sauvegardes"
        assert result["success"]
        assert result["copied"] == 1
        assert (archive / "Photos" / "Images" / "photo.jpg").is_file()
        assert not (archive / "Documents" / "Images" / "notes.txt").exists()


def test_empty_backup_is_not_marked_valid() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "empty"
        usb = root / "usb"
        source.mkdir()
        usb.mkdir()

        result = BackupEngine().run([source], usb)
        assert not result["success"]
        assert result["error"]
        assert not (
            usb / "Sauvegardes" / "guardian-valid.marker"
        ).exists()


def test_lock() -> None:
    with tempfile.TemporaryDirectory() as directory:
        lock = InstanceLock(Path(directory) / ".lock")
        assert lock.acquire()
        second = InstanceLock(Path(directory) / ".lock")
        assert not second.acquire()
        lock.release()


if __name__ == "__main__":
    test_api()
    test_backup_rejects_an_empty_category_selection()
    test_local_ui_resources_and_translations()
    test_native_window_disables_http_server()
    test_onefile_data_directory_uses_original_executable()
    test_frontend_uses_compiled_runtime_directory()
    test_language_setting_persists()
    test_custom_directories_persist()
    test_native_folder_picker_returns_selected_directory()
    test_windows_cache_flush_covers_all_volumes()
    test_windows_cache_flush_reports_failure()
    test_linux_cache_flush_calls_sync()
    test_scan()
    test_discovery_is_bounded_and_skips_system_directories()
    test_discovery_skips_project_assets_without_executables()
    test_log_files_do_not_mark_personal_directories_as_programs()
    test_weak_project_markers_need_source_code()
    test_personal_directories_include_added_and_external_sources()
    test_automatic_selection_distinguishes_trusted_and_discovered_sources()
    test_recognized_rescuezilla_metadata_and_explicit_override()
    test_duplicati_volumes_are_excluded_without_losing_nearby_files()
    test_downloads_are_not_automatically_selected()
    test_diagnostic_and_backup_apply_the_same_source_policy()
    test_backup_device_selection()
    test_windows_redirected_personal_folders()
    test_crypto()
    test_backup()
    test_backup_applies_categories_size_limit_and_exclusions()
    test_backup_flushes_periodically_and_at_completion()
    test_file_copy_does_not_force_disk_flush_for_each_block()
    test_backup_stops_on_checkpoint_flush_failure()
    test_backup_flush_failure_blocks_safe_removal()
    test_backup_preserves_added_folder_names()
    test_scan_counts_music_and_applies_size_and_path_filters()
    test_photo_backup_excludes_non_photos()
    test_empty_backup_is_not_marked_valid()
    test_lock()
    print("Tous les tests Guardian essentiels ont réussi.")