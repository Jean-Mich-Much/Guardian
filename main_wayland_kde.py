"""
Variante de lancement Guardian pour KDE en Wayland.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "wayland")
os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")

from main import main


if __name__ == "__main__":
    raise SystemExit(main())
