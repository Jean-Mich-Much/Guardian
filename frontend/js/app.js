(function () {
    "use strict";

    let selectedUsb = null;
    let usbDevices = [];
    let diagnostic = null;
    let backupEstimate = null;
    let startedAt = null;
    let paused = false;
    let backupMode = "all";
    let customBackupSources = [];
    let restoreDestination = null;
    let excludedBackupPaths = [];
    let estimateRequestId = 0;
    let estimateTimer = null;

    const $ = (selector) => document.querySelector(selector);

    function showScreen(screenId) {
        document.querySelectorAll(".screen").forEach((screen) => {
            screen.classList.toggle("is-active", screen.id === screenId);
        });
    }

    function formatBytes(bytes) {
        const value = Number(bytes || 0);
        if (value >= 1024 ** 3) {
            return `${(value / 1024 ** 3).toFixed(value >= 10 * 1024 ** 3 ? 0 : 1)} ${window.guardianI18n.translate("common.units.gb")}`;
        }
        if (value >= 1024 ** 2) {
            return `${(value / 1024 ** 2).toFixed(1)} ${window.guardianI18n.translate("common.units.mb")}`;
        }
        if (value >= 1024) {
            return `${(value / 1024).toFixed(1)} ${window.guardianI18n.translate("common.units.kb")}`;
        }
        return `${value} ${window.guardianI18n.translate("common.units.bytes")}`;
    }

    function selectedBackupCategories() {
        return Array.from(
            document.querySelectorAll("input[name='backup-category']:checked")
        ).map((input) => input.value);
    }

    function backupFilterOptions() {
        const limitEnabled = $("#limit-file-size-enabled").checked;
        const sizeMb = Number($("#max-file-size").value);
        if (limitEnabled && (!Number.isInteger(sizeMb) || sizeMb < 1 || sizeMb > 1048576)) {
            return { valid: false };
        }
        return {
            valid: true,
            max_file_size_bytes: limitEnabled ? sizeMb * 1024 ** 2 : null,
            excluded_paths: $("#exclude-items-enabled").checked
                ? [...excludedBackupPaths]
                : [],
        };
    }

    function updateBackupEstimate(stats = backupEstimate || diagnostic) {
        if (!stats) {
            return;
        }
        const categories = selectedBackupCategories();
        const categoryFiles = stats.category_files || {};
        const categorySizes = stats.category_sizes || {};
        const fileCount = categories.reduce(
            (total, category) => total + Number(categoryFiles[category] || 0),
            0
        );
        const required = categories.reduce(
            (total, category) => total + Number(categorySizes[category] || 0),
            0
        );
        const message = $("#diagnostic-message");
        const startButton = $("#start-backup");

        $("#photo-count").textContent = Number(categoryFiles.photos || 0);
        $("#video-count").textContent = Number(categoryFiles.videos || 0);
        $("#document-count").textContent = Number(categoryFiles.documents || 0);
        $("#music-count").textContent = Number(categoryFiles.music || 0);
        $("#other-count").textContent = Number(categoryFiles.other || 0);
        $("#required-space").textContent = formatBytes(required);
        startButton.disabled = !selectedUsb || categories.length === 0 || fileCount === 0;

        let messageKey = "";
        if (categories.length === 0) {
            messageKey = "diagnostic.select_category";
        } else if (fileCount === 0) {
            messageKey = "diagnostic.no_matching_files";
        } else if (!selectedUsb) {
            messageKey = stats.usb_choice_required
                ? "home.choose_usb"
                : "diagnostic.usb_missing";
        } else if (required > Number(stats.available || 0)) {
            messageKey = "diagnostic.low_space";
        } else if (stats.battery && stats.battery.warning) {
            messageKey = "diagnostic.battery_warning";
        } else if (stats.large_file_warnings && stats.large_file_warnings.length) {
            messageKey = "diagnostic.large_warning";
        }

        message.hidden = !messageKey;
        message.textContent = messageKey
            ? window.guardianI18n.translate(messageKey)
            : "";
    }

    function resetBackupOptions() {
        estimateRequestId += 1;
        excludedBackupPaths = [];
        $("#backup-options").open = false;
        $("#limit-file-size-enabled").checked = false;
        $("#max-file-size").value = "256";
        $("#max-file-size").disabled = true;
        $("#exclude-items-enabled").checked = false;
        $("#excluded-items-controls").hidden = true;
        document.querySelectorAll("input[name='backup-category']").forEach((input) => {
            input.checked = backupMode !== "photos" || input.value === "photos";
            input.disabled = backupMode === "photos" && input.value !== "photos";
        });
        renderExcludedItems();
    }

    function renderExcludedItems() {
        const list = $("#excluded-items-list");
        list.replaceChildren();
        excludedBackupPaths.forEach((path) => {
            const item = document.createElement("li");
            const label = document.createElement("span");
            label.textContent = path;
            const remove = document.createElement("button");
            remove.className = "button button-link";
            remove.type = "button";
            remove.textContent = window.guardianI18n.translate("diagnostic.remove");
            remove.addEventListener("click", async () => {
                excludedBackupPaths = excludedBackupPaths.filter(
                    (excludedPath) => excludedPath !== path
                );
                renderExcludedItems();
                await refreshBackupEstimate();
            });
            item.append(label, remove);
            list.append(item);
        });
    }

    async function refreshBackupEstimate() {
        if (!diagnostic) {
            return;
        }
        const options = backupFilterOptions();
        if (!options.valid) {
            $("#start-backup").disabled = true;
            const message = $("#diagnostic-message");
            message.hidden = false;
            message.textContent = window.guardianI18n.translate("diagnostic.invalid_size");
            return;
        }

        if (
            options.max_file_size_bytes === null
            && options.excluded_paths.length === 0
        ) {
            estimateRequestId += 1;
            backupEstimate = diagnostic;
            updateBackupEstimate();
            return;
        }

        const requestId = ++estimateRequestId;
        try {
            const result = await window.pywebview.api.diagnostic(
                selectedUsb ? selectedUsb.mountpoint : null,
                backupMode,
                options.max_file_size_bytes,
                options.excluded_paths
            );
            if (requestId !== estimateRequestId) {
                return;
            }
            if (result.success === false) {
                throw new Error(result.error || "Backup estimate failed");
            }
            backupEstimate = result;
            updateBackupEstimate();
        } catch (error) {
            if (requestId !== estimateRequestId) {
                return;
            }
            $("#start-backup").disabled = true;
            const message = $("#diagnostic-message");
            message.hidden = false;
            message.textContent =
                `${window.guardianI18n.translate("diagnostic.error")}: ${String(error)}`;
        }
    }

    async function selectBackupExclusions(selectFiles) {
        try {
            const result = selectFiles
                ? await window.pywebview.api.select_files()
                : await window.pywebview.api.select_folder();
            if (!result.success) {
                if (!result.cancelled) {
                    throw new Error(result.error || "Could not select items to exclude");
                }
                return;
            }
            const paths = selectFiles ? result.paths : [result.path];
            excludedBackupPaths = Array.from(
                new Set([...excludedBackupPaths, ...paths])
            );
            renderExcludedItems();
            await refreshBackupEstimate();
        } catch (error) {
            const message = $("#diagnostic-message");
            message.hidden = false;
            message.textContent =
                `${window.guardianI18n.translate("diagnostic.error")}: ${String(error)}`;
        }
    }

    async function refreshUsbStatus() {
        try {
            const data = await window.pywebview.api.usb();
            usbDevices = data.devices || [];
            const previous = selectedUsb
                ? usbDevices.find((device) => device.mountpoint === selectedUsb.mountpoint)
                : null;
            selectedUsb = previous || data.selected || null;
            const status = $("#usb-status");
            const needsChoice = Boolean(data.requires_choice);
            $("#usb-choice-wrap").hidden = !needsChoice;
            $("#diagnostic-usb-choice-wrap").hidden = !needsChoice;
            ["#usb-choice", "#diagnostic-usb-choice"].forEach((selector) => {
                const choice = $(selector);
                choice.replaceChildren();
                if (!needsChoice) {
                    return;
                }
                const placeholder = document.createElement("option");
                placeholder.value = "";
                placeholder.textContent =
                    window.guardianI18n.translate("home.choose_usb");
                placeholder.disabled = true;
                choice.append(placeholder);
                usbDevices.forEach((device) => {
                    const option = document.createElement("option");
                    option.value = device.mountpoint;
                    option.textContent =
                        `${device.mountpoint} — ${formatBytes(device.free)} / ${formatBytes(device.total)}`;
                    choice.append(option);
                });
                choice.value = selectedUsb ? selectedUsb.mountpoint : "";
            });
            if (selectedUsb) {
                status.classList.add("is-connected");
                $("#usb-status-title").textContent =
                    `${window.guardianI18n.translate("home.usb")} : ${selectedUsb.mountpoint}`;
                const reasonKeys = {
                    existing_backup: "home.target_existing",
                    least_used: "home.target_least_used",
                    only_device: "home.target_only",
                    tie: "home.target_manual",
                    multiple_backups: "home.target_manual",
                };
                const reason = reasonKeys[data.reason]
                    ? window.guardianI18n.translate(reasonKeys[data.reason])
                    : "";
                $("#usb-status-help").textContent = reason
                    ? `${formatBytes(selectedUsb.free)} — ${reason}`
                    : formatBytes(selectedUsb.free);
            } else if (needsChoice) {
                status.classList.remove("is-connected");
                $("#usb-status-title").textContent =
                    window.guardianI18n.translate("home.choose_usb");
                $("#usb-status-help").textContent = "";
            } else {
                status.classList.remove("is-connected");
                $("#usb-status-title").dataset.i18n = "home.no_usb";
                $("#usb-status-help").dataset.i18n = "home.usb_help";
                window.guardianI18n.applyTranslations(status);
            }
        } catch (error) {
            selectedUsb = null;
            $("#usb-status").classList.remove("is-connected");
            $("#usb-status-title").textContent =
                window.guardianI18n.translate("home.usb_error");
            $("#usb-status-help").textContent = String(error);
            $("#usb-choice-wrap").hidden = true;
            $("#diagnostic-usb-choice-wrap").hidden = true;
        }
    }

    async function loadDiagnostic() {
        resetBackupOptions();
        diagnostic = null;
        backupEstimate = null;
        $("#start-backup").disabled = true;
        $("#diagnostic-message").hidden = true;
        $("#diagnostic-message").textContent = "";
        try {
            if (!selectedUsb) {
                await refreshUsbStatus();
            }
            diagnostic = await window.pywebview.api.diagnostic(
                selectedUsb ? selectedUsb.mountpoint : null,
                backupMode
            );
            if (diagnostic.success === false) {
                throw new Error(diagnostic.error || "Scan failed");
            }
        } catch (error) {
            const message = $("#diagnostic-message");
            message.hidden = false;
            message.textContent =
                `${window.guardianI18n.translate("diagnostic.error")}: ${String(error)}`;
            showScreen("screen-diagnostic");
            return;
        }

        $("#available-space").textContent = formatBytes(diagnostic.available);

        backupEstimate = diagnostic;
        updateBackupEstimate();
        showScreen("screen-diagnostic");
    }

    function renderCustomSources() {
        const list = $("#custom-folder-list");
        list.replaceChildren();
        customBackupSources.forEach((path) => {
            const item = document.createElement("li");
            item.className = "custom-folder-item";
            const label = document.createElement("span");
            label.textContent = path;
            const remove = document.createElement("button");
            remove.className = "button button-link";
            remove.type = "button";
            remove.textContent = window.guardianI18n.translate("home.remove_folder");
            remove.addEventListener("click", async () => {
                const updated = customBackupSources.filter((source) => source !== path);
                try {
                    const result = await window.pywebview.api.save_custom_directories(updated);
                    if (!result.success) {
                        throw new Error(result.error || "Profile update failed");
                    }
                    customBackupSources = result.custom_directories || updated;
                    renderCustomSources();
                } catch (error) {
                    showFolderMessage(error);
                }
            });
            item.append(label, remove);
            list.append(item);
        });
        $("#save-custom-button").disabled = customBackupSources.length === 0;
    }

    function showFolderMessage(error) {
        const message = $("#folder-message");
        message.hidden = false;
        message.textContent =
            `${window.guardianI18n.translate("home.folder_error")}: ${String(error)}`;
    }

    async function loadCustomSources() {
        const profile = await window.pywebview.api.get_profile("default");
        customBackupSources = Array.isArray(profile.custom_directories)
            ? profile.custom_directories.filter((path) => typeof path === "string")
            : [];
        renderCustomSources();
    }

    async function addSelectedSources(paths) {
        if (!Array.isArray(paths) || paths.some((path) => typeof path !== "string")) {
            throw new Error("La sélection est invalide.");
        }
        const updated = [...customBackupSources, ...paths];
        const result = await window.pywebview.api.save_custom_directories(updated);
        if (!result.success) {
            throw new Error(result.error || "Profile update failed");
        }
        customBackupSources = result.custom_directories || updated;
        renderCustomSources();
    }

    async function selectCustomSources(selectFiles) {
        const message = $("#folder-message");
        message.hidden = true;
        message.textContent = "";
        $("#source-picker-options").hidden = true;
        $("#save-folder-button").setAttribute("aria-expanded", "false");
        try {
            const data = selectFiles
                ? await window.pywebview.api.select_files()
                : await window.pywebview.api.select_folder();
            if (!data.success) {
                if (!data.cancelled) {
                    showFolderMessage(data.error || "Source selection failed");
                }
                return;
            }
            await addSelectedSources(selectFiles ? data.paths : [data.path]);
        } catch (error) {
            showFolderMessage(error);
        }
    }

    async function startBackup() {
        const categories = selectedBackupCategories();
        const options = backupFilterOptions();
        if (!options.valid) {
            await refreshBackupEstimate();
            return;
        }
        if (categories.length === 0) {
            updateBackupEstimate();
            return;
        }
        if (!selectedUsb) {
            await refreshUsbStatus();
        }
        if (!selectedUsb) {
            await loadDiagnostic();
            return;
        }

        const data = await window.pywebview.api.start_backup({
            mountpoint: selectedUsb.mountpoint,
            password: null,
            profile: "default",
            mode: backupMode,
            categories,
            custom_directories: customBackupSources,
            max_file_size_bytes: options.max_file_size_bytes,
            excluded_paths: options.excluded_paths,
        });
        if (!data.success) {
            const message = $("#diagnostic-message");
            message.hidden = false;
            message.textContent = data.error || window.guardianI18n.translate("result.error");
            return;
        }

        startedAt = Date.now();
        paused = false;
        $("#progress-percent").textContent = "0%";
        $("#progress-bar").style.width = "0%";
        $(".progress-track").setAttribute("aria-valuenow", "0");
        showScreen("screen-progress");
    }

    function updateProgress(payload) {
        const percent = Number(payload.percent || 0);
        $("#progress-percent").textContent = `${percent}%`;
        $("#progress-bar").style.width = `${percent}%`;
        $(".progress-track").setAttribute("aria-valuenow", String(percent));
        if (payload.current) {
            $("#current-file").textContent = payload.current;
        }
        if (startedAt && percent > 0) {
            const elapsed = (Date.now() - startedAt) / 1000;
            const remaining = Math.max(0, elapsed * (100 - percent) / percent);
            const minutes = Math.max(0, Math.ceil(remaining / 60));
            $("#remaining-time").textContent = minutes > 0
                ? `${minutes} min`
                : window.guardianI18n.translate("progress.calculating");
        }
    }

    function showResult(payload) {
        const incomplete = payload.success === false || Boolean(payload.error);
        $("#result-title").textContent = window.guardianI18n.translate(
            incomplete ? "result.error_title" : "result.title"
        );
        const subtitle = incomplete
            ? (payload.error || window.guardianI18n.translate("result.error"))
            : payload.safe_to_remove
                ? window.guardianI18n.translate("result.safe_to_remove")
                : window.guardianI18n.translate("result.subtitle");
        const safeToRemoveNote = incomplete && payload.safe_to_remove
            ? window.guardianI18n.translate("result.partial_safe_to_remove")
            : "";
        $("#result-subtitle").textContent = [subtitle, safeToRemoveNote]
            .filter(Boolean)
            .join(" ");
        $("#copied-count").textContent = payload.copied || 0;
        $("#skipped-count").textContent = payload.skipped || 0;
        $("#failed-count").textContent = payload.failed || 0;
        $("#archive-path").textContent = payload.archive || "";
        const summary = payload.category_summary;
        if (summary) {
            $("#category-summary").textContent =
                `${window.guardianI18n.translate("restore.documents")}: ${summary.documents || 0} · ` +
                `${window.guardianI18n.translate("restore.photos")}: ${summary.photos || 0} · ` +
                `${window.guardianI18n.translate("restore.music")}: ${summary.music || 0} · ` +
                `${window.guardianI18n.translate("restore.videos")}: ${summary.videos || 0}`;
        }
        const uncopied = payload.uncopied || [];
        $("#uncopied-details").hidden = uncopied.length === 0;
        if (uncopied.length > 0) {
            $("#category-summary").textContent =
                window.guardianI18n.translate("result.space_limited");
        }
        $("#uncopied-list").replaceChildren(
            ...uncopied.map((path) => {
                const item = document.createElement("li");
                item.textContent = path;
                return item;
            })
        );
        showScreen("screen-result");
    }

    async function startRestore() {
        if (!selectedUsb) {
            await refreshUsbStatus();
        }
        if (!selectedUsb) {
            $("#restore-message").textContent =
                window.guardianI18n.translate("restore.no_archive");
            return;
        }

        const password = null;
        const categories = Array.from(
            document.querySelectorAll("input[name='restore-category']:checked")
        ).map((input) => input.value);
        const data = await window.pywebview.api.restore({
            mountpoint: selectedUsb.mountpoint,
            password,
            categories,
            destination_directory: restoreDestination,
        });
        if (data.success) {
            const messages = [window.guardianI18n.translate("restore.success")];
            if (data.destination_mode === "custom") {
                messages.push(
                    `${window.guardianI18n.translate("restore.destination")}: ${data.destination}`
                );
            } else if (data.fallback_used) {
                messages.push(
                    `${window.guardianI18n.translate("restore.fallback")}: ${data.destination}`
                );
            } else {
                messages.push(window.guardianI18n.translate("restore.original_locations"));
            }
            if (data.restored) {
                messages.push(
                    `${data.restored} ${window.guardianI18n.translate("restore.restored_count")}`
                );
            }
            if (data.shortcut_directory) {
                messages.push(
                    `${window.guardianI18n.translate("restore.shortcuts")}: ${data.shortcut_directory}`
                );
            }
            if (data.skipped) {
                messages.push(
                    `${data.skipped} ${window.guardianI18n.translate("restore.skipped")}`
                );
            }
            $("#restore-message").textContent = messages.join(" ");
        } else {
            const details = [data.error || window.guardianI18n.translate("restore.no_archive")];
            if (data.restored) {
                details.push(
                    `${data.restored} ${window.guardianI18n.translate("restore.restored_count")}`
                );
            }
            if (data.skipped) {
                details.push(
                    `${data.skipped} ${window.guardianI18n.translate("restore.skipped")}`
                );
            }
            $("#restore-message").textContent = details.join(" ");
        }
    }

    function renderRestoreDestination() {
        $("#restore-location-path").textContent =
            restoreDestination || window.guardianI18n.translate("restore.automatic");
        $("#restore-location-reset").disabled = !restoreDestination;
    }

    let pollingEvents = false;

    async function pollEvents() {
        if (pollingEvents) {
            return;
        }
        pollingEvents = true;
        try {
            const events = await window.pywebview.api.poll_events();
            events.forEach((payload) => {
                if (payload.type === "progress") {
                    updateProgress(payload);
                } else if (payload.type === "paused") {
                    paused = true;
                    $("#pause-button").dataset.i18n = "progress.resume";
                    window.guardianI18n.applyTranslations($("#pause-button"));
                } else if (payload.type === "resumed") {
                    paused = false;
                    $("#pause-button").dataset.i18n = "progress.pause";
                    window.guardianI18n.applyTranslations($("#pause-button"));
                } else if (payload.type === "backup_result") {
                    showResult(payload);
                } else if (payload.type === "cancelled_complete") {
                    showResult(payload);
                }
            });
        } finally {
            pollingEvents = false;
        }
    }

    function connectEvents() {
        setInterval(() => {
            pollEvents();
        }, 250);
    }

    async function waitForBridge() {
        if (typeof window.pywebview?.api?.usb === "function") {
            return;
        }
        await new Promise((resolve) => {
            window.addEventListener("pywebviewready", resolve, { once: true });
        });
    }

    async function initialize() {
        await waitForBridge();
        await window.guardianI18n.initialize();
        renderRestoreDestination();
        try {
            await loadCustomSources();
        } catch (error) {
            showFolderMessage(error);
        }
        await refreshUsbStatus();
        setInterval(refreshUsbStatus, 3000);
        connectEvents();

        $("#language-select").value = window.guardianI18n.getCurrentLanguage();
        $("#about-button").addEventListener("click", async () => {
            $("#about-dialog").showModal();
            const text = $("#license-text");
            if (!text.textContent) {
                try {
                    text.textContent = await window.pywebview.api.get_license();
                } catch (error) {
                    text.textContent = String(error);
                }
            }
        });
        $("#about-close").addEventListener("click", () => $("#about-dialog").close());
        $("#language-select").addEventListener("change", async (event) => {
            await window.guardianI18n.setLanguage(event.target.value);
            renderCustomSources();
            renderExcludedItems();
            renderRestoreDestination();
            updateBackupEstimate();
            refreshUsbStatus();
        });
        $("#usb-choice").addEventListener("change", (event) => {
            selectedUsb = usbDevices.find(
                (device) => device.mountpoint === event.target.value
            ) || null;
            refreshUsbStatus();
        });
        $("#diagnostic-usb-choice").addEventListener("change", async (event) => {
            selectedUsb = usbDevices.find(
                (device) => device.mountpoint === event.target.value
            ) || null;
            await refreshUsbStatus();
            await loadDiagnostic();
        });

        $("#save-photos-button").addEventListener("click", () => {
            backupMode = "photos";
            loadDiagnostic();
        });
        $("#save-all-button").addEventListener("click", () => {
            backupMode = "all";
            loadDiagnostic();
        });
        $("#save-folder-button").addEventListener("click", () => {
            const options = $("#source-picker-options");
            options.hidden = !options.hidden;
            $("#save-folder-button").setAttribute("aria-expanded", String(!options.hidden));
        });
        $("#add-folder-button").addEventListener("click", () => selectCustomSources(false));
        $("#add-files-button").addEventListener("click", () => selectCustomSources(true));
        $("#save-custom-button").addEventListener("click", () => {
            backupMode = "custom";
            loadDiagnostic();
        });
        $("#restore-button").addEventListener("click", () => {
            $("#restore-message").textContent = "";
            showScreen("screen-restore");
        });
        $("#restore-location-button").addEventListener("click", async () => {
            try {
                const data = await window.pywebview.api.select_folder();
                if (data.success) {
                    restoreDestination = data.path;
                    renderRestoreDestination();
                } else if (!data.cancelled) {
                    $("#restore-message").textContent =
                        data.error || window.guardianI18n.translate("restore.no_archive");
                }
            } catch (error) {
                $("#restore-message").textContent = String(error);
            }
        });
        $("#restore-location-reset").addEventListener("click", () => {
            restoreDestination = null;
            renderRestoreDestination();
        });
        $("#diagnostic-back").addEventListener("click", () => showScreen("screen-home"));
        $("#restore-back").addEventListener("click", () => showScreen("screen-home"));
        $("#start-backup").addEventListener("click", startBackup);
        document.querySelectorAll("input[name='backup-category']").forEach((input) => {
            input.addEventListener("change", () => updateBackupEstimate());
        });
        $("#limit-file-size-enabled").addEventListener("change", async (event) => {
            $("#max-file-size").disabled = !event.target.checked;
            await refreshBackupEstimate();
        });
        $("#max-file-size").addEventListener("input", () => {
            clearTimeout(estimateTimer);
            estimateTimer = setTimeout(refreshBackupEstimate, 300);
        });
        $("#exclude-items-enabled").addEventListener("change", async (event) => {
            $("#excluded-items-controls").hidden = !event.target.checked;
            await refreshBackupEstimate();
        });
        $("#exclude-folder-button").addEventListener("click", () => {
            selectBackupExclusions(false);
        });
        $("#exclude-files-button").addEventListener("click", () => {
            selectBackupExclusions(true);
        });
        $("#start-restore").addEventListener("click", startRestore);
        $("#result-home").addEventListener("click", () => showScreen("screen-home"));
        $("#pause-button").addEventListener("click", async () => {
            if (paused) {
                await window.pywebview.api.resume_backup();
            } else {
                await window.pywebview.api.pause_backup();
            }
        });
        $("#cancel-button").addEventListener("click", async () => {
            await window.pywebview.api.cancel_backup();
        });
        document.querySelectorAll("[data-action='home']").forEach((button) => {
            button.addEventListener("click", () => showScreen("screen-home"));
        });
    }

    document.addEventListener("DOMContentLoaded", initialize);
})();