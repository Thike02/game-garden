from datetime import UTC, datetime

import pytest

from game_garden.community import CommunityPageError, icon_hash, parse_page, parse_unlock_time

NOW = datetime(2026, 10, 10, 3, 0, tzinfo=UTC)

PAGE = """
<div class="achieveRow">
  <div class="achieveImgHolder"><img src="https://cdn/community_assets/images/apps/487430/aaa111.jpg"></div>
  <div class="achieveTxtHolder"><div class="achieveTxt"><h3> </h3><h5> </h5></div>
    <div class="achieveUnlockTime">
      Unlocked 26 Nov, 2021 @ 8:14am<br/>
    </div>
  </div>
</div>
<div class="achieveRow ">
  <div class="achieveImgHolder"><img src="https://cdn/community_assets/images/apps/487430/bbb222.jpg"></div>
  <div class="achieveTxtHolder"><div class="achieveTxt"><h3> </h3><h5> </h5></div></div>
</div>
<div id="footer"></div>
"""


def test_unlock_time_is_pacific():
    # PDT (UTC-7) in October
    assert parse_unlock_time("4 Oct @ 4:23am", NOW) == datetime(2026, 10, 4, 11, 23, tzinfo=UTC)
    # PST (UTC-8) in November, explicit year
    assert parse_unlock_time("26 Nov, 2021 @ 8:14am", NOW) == datetime(2021, 11, 26, 16, 14, tzinfo=UTC)
    assert parse_unlock_time("1 Jan, 2022 @ 12:05pm", NOW) == datetime(2022, 1, 1, 20, 5, tzinfo=UTC)
    assert parse_unlock_time("1 Jan, 2022 @ 12:05am", NOW) == datetime(2022, 1, 1, 8, 5, tzinfo=UTC)


def test_parse_page_rows():
    rows = parse_page(PAGE, NOW)
    assert [r.icon_hash for r in rows] == ["aaa111", "bbb222"]
    assert rows[0].unlocked_at == datetime(2021, 11, 26, 16, 14, tzinfo=UTC)
    assert rows[1].unlocked_at is None


def test_page_without_achievements():
    with pytest.raises(CommunityPageError):
        parse_page("<html>private</html>", NOW)


def test_icon_hash():
    assert icon_hash("https://x/apps/1/abcd.jpg") == "abcd"
    assert icon_hash(None) is None
