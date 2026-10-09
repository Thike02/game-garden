-- When the player started a game (typed in the admin; Steam does not report it).
alter table public.owned_games add column started_on date;

-- Lets the admin fill in "last played" for non-Steam games from NVIDIA App's records
-- (its ShortName, e.g. 'arknights_endfield').
alter table public.games add column nvidia_app_name text;

-- Same as 0006 plus started_on (new columns must go at the end of a view).
create or replace view public.player_games as
select
  og.player_id,
  og.game_id,
  og.source,
  case when p.show_playtime then og.playtime_minutes end as playtime_minutes,
  case when p.show_playtime then og.last_played_at end   as last_played_at,
  og.achievements_total,
  og.achievements_unlocked,
  og.achievements_synced_at,
  og.started_on
from public.owned_games og
join public.players p on p.id = og.player_id
where p.is_public and og.is_visible;
