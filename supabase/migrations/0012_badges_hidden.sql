-- Steam's API leaves out the description of hidden achievements, so the page needs to know which
-- ones are hidden to say so. Same view as 0002 with `hidden` added (new columns go at the end).
create or replace view public.player_achievement_badges
with (security_invoker = true)
as
select
  pa.player_id,
  pa.game_id,
  g.name            as game_name,
  g.steam_appid,
  g.header_image_url,
  a.api_name,
  a.display_name,
  a.description,
  a.icon_url,
  a.global_percent,
  public.achievement_rarity(a.global_percent) as rarity,
  pa.unlocked_at,
  a.hidden
from public.player_achievements pa
join public.achievements a on a.game_id = pa.game_id and a.api_name = pa.api_name
join public.games g on g.id = pa.game_id;
