#!/usr/bin/env python3
"""
Script to pre-download Kokoro TTS models.
Can be run during Docker build or manually.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.kokoro import download_kokoro_models

if __name__ == "__main__":
    success = download_kokoro_models()
    sys.exit(0 if success else 1)

