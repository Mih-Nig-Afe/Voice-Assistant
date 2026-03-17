#!/usr/bin/env python3
"""Entry point for Miehab web frontend."""

import sys
from pathlib import Path

_src_dir = str(Path(__file__).resolve().parent.parent / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from voice_assistant.web import main

if __name__ == "__main__":
    main()
