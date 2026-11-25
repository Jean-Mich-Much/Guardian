"""
Variante de lancement Guardian pour GNOME en Wayland.
"""

from __future__ import annotations

import os

os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")

from main import main


if __name__ == "__main__":
    raise SystemExit(main())
