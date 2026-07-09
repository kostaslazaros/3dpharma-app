"""
Download database files from external URLs (e.g., Google Drive) during build.

Set COMPACT_DATABASE_URL / DATABASE_URL env vars to download the files.
Defaults to the provided Google Drive link for the compact DB.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import gdown

ROOT = Path(__file__).resolve().parents[1]
COMPACT_DB = ROOT / "comprehensive_drug_database_compact.json"
FULL_DB = ROOT / "comprehensive_drug_database.json"

# Default compact DB URL provided by user
DEFAULT_COMPACT_URL = "https://drive.google.com/file/d/12o_cdObA01lxXJMY8LjCqlPVrXF56bZF/view?usp=drive_link"


def download_file(url: str, target: Path) -> bool:
    """Download a file (supports Google Drive links via gdown)."""
    try:
        if target.exists():
            target.unlink()
        target.parent.mkdir(parents=True, exist_ok=True)
        gdown.download(url, str(target), quiet=False, fuzzy=True)
        size_mb = target.stat().st_size / (1024 ** 2)
        if size_mb < 5 or _looks_like_html(target):
            target.unlink(missing_ok=True)
            raise ValueError("Download appears to be HTML/too small; Google Drive may have blocked the request.")

        print(f"✓ Downloaded {target.name} ({size_mb:.1f} MB)")
        return True
    except Exception as exc:
        print(f"✗ Failed to download {url} -> {target}: {exc}")
        return False


def _looks_like_html(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            start = f.read(512).lstrip()
            return start.startswith(b"<")
    except Exception:
        return False


def ensure_file(target: Path, url: Optional[str]) -> None:
    if target.exists():
        print(f"✓ {target.name} already present ({target.stat().st_size / (1024 ** 2):.1f} MB)")
        return
    if not url:
        print(f"⚠️  No URL provided for {target.name}; skipping download.")
        return
    download_file(url, target)


def main() -> None:
    compact_url = os.getenv("COMPACT_DATABASE_URL", DEFAULT_COMPACT_URL)
    full_url = os.getenv("DATABASE_URL")

    ensure_file(COMPACT_DB, compact_url)
    ensure_file(FULL_DB, full_url)

    if not COMPACT_DB.exists() and not FULL_DB.exists():
        print("⚠️  No database files available. The app will show an error at runtime.")


if __name__ == "__main__":
    main()