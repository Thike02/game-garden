"""Game images uploaded from the local admin, stored in Supabase Storage."""

from __future__ import annotations

import uuid

from supabase import Client

BUCKET = "game-images"
MAX_BYTES = 5 * 1024 * 1024  # matches the bucket's file_size_limit (0007)

# Checked against the file's first bytes, not the name or the browser's claim.
_SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
}
_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}


class ImageError(ValueError):
    pass


def detect_type(data: bytes) -> str:
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    for content_type, signatures in _SIGNATURES.items():
        if data.startswith(signatures):
            return content_type
    raise ImageError("JPEG、PNG、WebP、GIF の画像を選んでください")


def upload_game_image(database: Client, data: bytes) -> str:
    """Store the image under a random name and return its public URL."""
    if not data:
        raise ImageError("画像ファイルが空です")
    if len(data) > MAX_BYTES:
        raise ImageError("画像は 5MB までにしてください")
    content_type = detect_type(data)
    path = f"manual/{uuid.uuid4().hex}.{_EXTENSIONS[content_type]}"
    database.storage.from_(BUCKET).upload(path, data, {"content-type": content_type})
    return database.storage.from_(BUCKET).get_public_url(path)


def stored_path(database: Client, url: str | None) -> str | None:
    """Path inside the bucket if `url` points at an image we uploaded, else None."""
    if not url:
        return None
    prefix = database.storage.from_(BUCKET).get_public_url("")
    prefix = prefix.split("?", 1)[0]
    if not url.startswith(prefix):
        return None
    return url[len(prefix) :].split("?", 1)[0] or None


def delete_game_image(database: Client, url: str | None) -> None:
    """Remove an image we uploaded. Images hosted elsewhere are left alone."""
    if path := stored_path(database, url):
        database.storage.from_(BUCKET).remove([path])
