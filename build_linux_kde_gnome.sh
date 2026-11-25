#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 -m nuitka \
    --onefile \
    --enable-plugin=pyside6 \
    --include-package=webview \
    --include-data-dir=frontend=frontend \
    --include-data-dir=doc=doc \
    --output-dir=dist \
    main_wayland_gnome.py
