import pytest

from game_garden.tags import COLORS, TagError, _clean


def test_clean_trims_and_checks():
    assert _clean("  ストーリークリア ", "green") == ("ストーリークリア", "green")
    with pytest.raises(TagError):
        _clean("   ", "green")
    with pytest.raises(TagError):
        _clean("x" * 31, "green")
    with pytest.raises(TagError):
        _clean("ok", "#ff0000")  # only palette names, never raw CSS


def test_palette_matches_the_web_page():
    from pathlib import Path

    css = Path(__file__).parents[1].joinpath("web/src/styles.css").read_text(encoding="utf-8")
    for color in COLORS:
        assert f"--tag-{color}" in css
