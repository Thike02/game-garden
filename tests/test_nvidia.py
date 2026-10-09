import json
from datetime import UTC, datetime

from game_garden.nvidia import detected_apps


def test_reads_last_launch_and_skips_never_launched(tmp_path):
    storage = tmp_path / "ApplicationStorage.json"
    storage.write_text(
        json.dumps(
            {
                "Applications": [
                    {"Application": {"ShortName": "zenless_zone_zero", "DisplayName": "Zenless Zone Zero", "LastLaunchTimeISO": "2026-10-09T16:58:09Z"}},
                    {"Application": {"ShortName": "minecraft", "DisplayName": "Minecraft", "LastLaunchTimeISO": "1601-01-01T00:00:00Z"}},
                    {"Application": {"DisplayName": "no short name"}},
                ]
            }
        ),
        encoding="utf-8",
    )
    apps = {a.short_name: a for a in detected_apps(storage)}
    assert set(apps) == {"zenless_zone_zero", "minecraft"}
    assert apps["zenless_zone_zero"].last_launch == datetime(2026, 10, 9, 16, 58, 9, tzinfo=UTC)
    assert apps["minecraft"].last_launch is None


def test_missing_file_means_no_apps(tmp_path):
    assert detected_apps(tmp_path / "nope.json") == []
