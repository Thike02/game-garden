from game_garden.env_file import render_env, update_env_file


def test_replaces_in_place_and_keeps_comments():
    existing = "# Steam\nSTEAM_API_KEY=old\n\n# other\nSTEAM_COUNTRY_CODE=JP\n"
    out = render_env(existing, {"STEAM_API_KEY": "new", "ITAD_API_KEY": "k"})
    assert out == "# Steam\nSTEAM_API_KEY=new\n\n# other\nSTEAM_COUNTRY_CODE=JP\n\nITAD_API_KEY=k\n"


def test_quotes_values_with_spaces_or_quotes():
    assert render_env("", {"A": 'x "y"'}) == 'A="x \\"y\\""\n'
    assert render_env("", {"URL": "https://x.supabase.co"}) == "URL=https://x.supabase.co\n"


def test_starts_from_template(tmp_path):
    template = tmp_path / ".env.example"
    template.write_text("# keys\nSTEAM_ID=\n", encoding="utf-8")
    env = tmp_path / ".env"
    update_env_file(env, {"STEAM_ID": "765"}, template=template)
    assert env.read_text(encoding="utf-8") == "# keys\nSTEAM_ID=765\n"
