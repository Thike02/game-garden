-- Rarity tiers for achievement badges, based on the global unlock rate.
-- Thresholds live only here so the collector and the web page agree.

create or replace function public.achievement_rarity(global_percent numeric)
returns text
language sql
immutable
as $$
  select case
    when global_percent is null then null
    when global_percent < 1  then 'legendary'
    when global_percent < 5  then 'epic'
    when global_percent < 10 then 'rare'
    when global_percent < 25 then 'uncommon'
    else 'common'
  end
$$;

-- Unlocked achievements with game info and rarity (unordered; sort by global_percent to get the rarest).
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
  pa.unlocked_at
from public.player_achievements pa
join public.achievements a on a.game_id = pa.game_id and a.api_name = pa.api_name
join public.games g on g.id = pa.game_id;

grant select on public.player_achievement_badges to anon, authenticated;
