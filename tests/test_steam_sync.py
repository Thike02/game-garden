from datetime import UTC, datetime

from game_garden.steam import OwnedGame
from game_garden.steam_sync import select_achievement_targets


def game(appid: int, last_played: datetime | None) -> OwnedGame:
    return OwnedGame(appid=appid, name=f"g{appid}", playtime_minutes=0, last_played_at=last_played)


DAY1 = datetime(2026, 10, 1, tzinfo=UTC)
DAY2 = datetime(2026, 10, 2, tzinfo=UTC)
DAY3 = datetime(2026, 10, 3, tzinfo=UTC)


def test_first_run_selects_everything():
    owned = [game(1, DAY1), game(2, None)]
    assert {g.appid for g in select_achievement_targets(owned, {}, full=False)} == {1, 2}


def test_only_games_played_since_last_sync():
    owned = [game(1, DAY3), game(2, DAY1), game(3, None)]
    synced = {1: DAY2, 2: DAY2, 3: DAY2}
    assert [g.appid for g in select_achievement_targets(owned, synced, full=False)] == [1]


def test_new_game_is_selected():
    owned = [game(1, DAY1), game(2, None)]
    synced = {1: DAY2}
    assert [g.appid for g in select_achievement_targets(owned, synced, full=False)] == [2]


def test_full_selects_everything_recent_first():
    owned = [game(1, DAY1), game(2, None), game(3, DAY3)]
    synced = {1: DAY2, 2: DAY2, 3: DAY3}
    assert [g.appid for g in select_achievement_targets(owned, synced, full=True)] == [3, 1, 2]
