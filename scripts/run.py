#!/usr/bin/env python3
"""
Entry point script for Voice Assistant (Miehab).

Usage:
    python scripts/run.py
"""

import sys
from pathlib import Path

# Add src/ to Python path so the package can be found
_src_dir = str(Path(__file__).resolve().parent.parent / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from voice_assistant.assistant import main

if __name__ == "__main__":
    main()

