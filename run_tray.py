#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AI Prompt Studio - System Tray Launcher."""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.tray import run_tray_app

if __name__ == "__main__":
    run_tray_app()
