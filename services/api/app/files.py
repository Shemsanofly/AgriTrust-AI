"""Farmer uploads (crop photos, loan documents): type checking by content and private storage.

A file's type is taken from its first bytes, never from the name or the type the phone sends,
and files are stored under random names in UPLOAD_DIR/<kind>, outside the web root."""

import secrets
from pathlib import Path

from .config import get_settings

MAX_BYTES = 5 * 1024 * 1024
EXTENSION = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}
IMAGES = ("image/jpeg", "image/png", "image/webp")


def sniff(head: bytes) -> str | None:
    """Real file type from the first bytes, whatever the upload claims."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def upload_dir(kind: str) -> Path:
    base = Path(get_settings().upload_dir)
    if not base.is_absolute():
        base = Path(__file__).resolve().parents[1] / base
    path = base / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def save(kind: str, data: bytes, content_type: str) -> str:
    """Stores the bytes under a random name and returns that name."""
    name = f"{secrets.token_hex(16)}{EXTENSION[content_type]}"
    (upload_dir(kind) / name).write_bytes(data)
    return name
