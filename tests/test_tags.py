import pytest

from game_garden.tags import TagError, _clean


def test_clean_trims_and_checks():
    assert _clean("  ストーリークリア ", "#8BC34A") == ("ストーリークリア", "#8bc34a")
    with pytest.raises(TagError):
        _clean("   ", "#8bc34a")
    with pytest.raises(TagError):
        _clean("x" * 31, "#8bc34a")


@pytest.mark.parametrize("color", ["blue", "#fff", "#12345g", "red;background:url(x)", "#8bc34a "])
def test_only_hex_colors(color):
    # the colour ends up in CSS, so anything but #rrggbb is refused
    if color == "#8bc34a ":
        assert _clean("ok", color)[1] == "#8bc34a"  # surrounding spaces are trimmed
    else:
        with pytest.raises(TagError):
            _clean("ok", color)
