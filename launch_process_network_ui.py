# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys


def _install_bundled_tkinter() -> None:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if not bundle_root:
        return

    tkinter_zip = os.path.join(bundle_root, "tkinter_bundle.zip")
    if os.path.isfile(tkinter_zip) and tkinter_zip not in sys.path:
        sys.path.insert(0, tkinter_zip)

    vendor_root = os.path.join(bundle_root, "vendor")
    if os.path.isdir(vendor_root) and vendor_root not in sys.path:
        sys.path.insert(0, vendor_root)


_install_bundled_tkinter()

from process_network_ui import main


if __name__ == "__main__":
    main()
