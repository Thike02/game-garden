-- 1) A game can appear in the owned list long after it was played: a restored license, a game
--    made non-private again. Its first snapshot then holds its lifetime playtime, which must not
--    land on a single day. Steam's playtime_2weeks says how much of it is recent, so a game's
--    first snapshot counts only that.
alter table public.playtime_snapshots add column playtime_2weeks integer;

-- 2) Games the player marked private on Steam. The sync sets this when Steam refuses their
--    achievements ("Profile is not public") and clears it once they can be read again.
--    Games without achievements can't be detected this way.
alter table public.owned_games add column steam_private boolean not null default false;

-- Same as 0006, except for how a game's first snapshot after the baseline is counted.
create or replace function public.refresh_daily_activity(p_player_id uuid)
returns void
language sql
security invoker
set search_path = public
as $$
  delete from daily_activity where player_id = p_player_id;

  insert into daily_activity (player_id, activity_date, minutes_played, achievements_unlocked)
  with hidden as (
    select game_id from owned_games where player_id = p_player_id and not is_visible
  ),
  baseline as (
    select min(snapshot_date) as day from playtime_snapshots where player_id = p_player_id
  ),
  diffs as (
    select
      s.snapshot_date,
      case
        when lag(s.playtime_minutes) over w is null
          -- first time we see this game: only the last two weeks are new to us
          -- (older snapshots have no playtime_2weeks; count nothing for them)
          then least(s.playtime_minutes, coalesce(s.playtime_2weeks, 0))
        else s.playtime_minutes - lag(s.playtime_minutes) over w
      end as minutes,
      lag(s.snapshot_date) over w as prev_date,
      (s.last_played_at at time zone 'Asia/Tokyo')::date as played_on
    from playtime_snapshots s
    where s.player_id = p_player_id
      and s.game_id not in (select game_id from hidden)
    window w as (partition by s.game_id order by s.snapshot_date)
  ),
  play_days as (
    select
      case
        when d.played_on between coalesce(d.prev_date, d.played_on) and d.snapshot_date then d.played_on
        else d.snapshot_date
      end as day,
      sum(d.minutes) as minutes
    from diffs d, baseline b
    where d.minutes > 0
      and (d.prev_date is not null or d.snapshot_date > b.day)
    group by 1
  ),
  achievement_days as (
    select (unlocked_at at time zone 'Asia/Tokyo')::date as day, count(*) as unlocked
    from player_achievements
    where player_id = p_player_id
      and unlocked_at is not null
      and game_id not in (select game_id from hidden)
    group by 1
  )
  select
    p_player_id,
    coalesce(p.day, a.day),
    coalesce(p.minutes, 0),
    coalesce(a.unlocked, 0)
  from play_days p
  full join achievement_days a on a.day = p.day;
$$;
