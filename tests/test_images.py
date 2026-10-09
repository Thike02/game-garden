import pytest

from game_garden.images import MAX_BYTES, ImageError, detect_type, upload_game_image


def test_type_is_checked_by_content():
    assert detect_type(b"\x89PNG\r\n\x1a\n....") == "image/png"
    assert detect_type(b"\xff\xd8\xff\xe0....") == "image/jpeg"
    assert detect_type(b"GIF89a....") == "image/gif"
    assert detect_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    # SVG can carry scripts; it is not accepted even if named .png
    with pytest.raises(ImageError):
        detect_type(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")


def test_rejects_empty_and_too_large_before_uploading():
    with pytest.raises(ImageError):
        upload_game_image(None, b"")
    with pytest.raises(ImageError):
        upload_game_image(None, b"\x89PNG\r\n\x1a\n" + b"0" * MAX_BYTES)
