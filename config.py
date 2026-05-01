"""
Project-wide configuration.

Read from environment variables when present, else fall back to the
defaults below. Anything that might reasonably need to change between
local dev, classroom demos, and a deployed instance lives here.
"""

import os
from pathlib import Path


# ─── Filesystem layout ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR      = PROJECT_ROOT / "web"
SAMPLES_DIR  = PROJECT_ROOT / "samples"
DOCS_DIR     = PROJECT_ROOT / "docs"

# ─── Backend (Flask) ────────────────────────────────────────
BACKEND_HOST  = os.environ.get("COMPILER_HOST", "0.0.0.0")
BACKEND_PORT  = int(os.environ.get("COMPILER_PORT", "5000"))
BACKEND_DEBUG = os.environ.get("COMPILER_DEBUG", "1") == "1"

# ─── Reporter defaults ──────────────────────────────────────
DEFAULT_FORMAT   = os.environ.get("COMPILER_FORMAT", "console")
DEFAULT_USE_COLOR = os.environ.get("NO_COLOR") is None   # honour NO_COLOR convention

# ─── Limits ─────────────────────────────────────────────────
MAX_SOURCE_BYTES = int(os.environ.get("COMPILER_MAX_BYTES", "1048576"))   # 1 MiB

# ─── Versioning ─────────────────────────────────────────────
VERSION = "1.0.0"
