from game_garden.local_steam import account_id, played_appids

STEAM_ID = "76561197960278073"  # made-up account 12345


def test_account_id():
    assert account_id(STEAM_ID) == 12345


def test_played_appids_from_stats_and_localconfig(tmp_path):
    stats = tmp_path / "appcache" / "stats"
    stats.mkdir(parents=True)
    (stats / "UserGameStats_12345_10.bin").write_bytes(b"")
    (stats / "UserGameStats_999_20.bin").write_bytes(b"")  # another account
    (stats / "UserGameStatsSchema_30.bin").write_bytes(b"")  # schema only, not "played"
    config = tmp_path / "userdata" / "12345" / "config"
    config.mkdir(parents=True)
    (config / "localconfig.vdf").write_text(
        '"UserLocalConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n\t\t\t"Steam"\n\t\t\t{\n'
        '\t\t\t\t"apps"\n\t\t\t\t{\n'
        '\t\t\t\t\t"40"\n\t\t\t\t\t{\n\t\t\t\t\t\t"LastPlayed"\t\t"1"\n\t\t\t\t\t}\n'
        '\t\t\t\t\t"50"\n\t\t\t\t\t{\n\t\t\t\t\t}\n'
        "\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n",
        encoding="utf-8",
    )
    assert played_appids(tmp_path, STEAM_ID) == {10, 40, 50}


def test_missing_steam_folder(tmp_path):
    assert played_appids(tmp_path / "nope", STEAM_ID) == set()
