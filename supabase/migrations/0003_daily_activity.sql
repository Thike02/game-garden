-- Activity grid ("grass"): per-day play minutes and achievement unlocks.

-- Remember when the game was last played at snapshot time, so a playtime increase
-- can be attributed to the day it was actually played rather than the day we noticed it.
alter table public.playtime_snapshots add column last_played_at timestamptz;

-- Rebuild daily_activity for one player from playtime_snapshots and player_achievements.
-- Days are Japan time.
--
-- Play minutes = increase of a game's total playtime since its previous snapshot.
--   * The player's first snapshot day is only a baseline (it holds lifetime totals).
--   * A game first seen after that (newly bought) counts from 0.
--   * The increase goes to the last-played day if it falls between the two snapshots,
--     otherwise to the snapshot day.
create or replace function public.refresh_daily_activity(p_player_id uuid)
returns void
language sql
security invoker
set search_path = public
as $$
  delete from daily_activity where player_id = p_player_id;

  insert into daily_activity (player_id, activity_date, minutes_played, achievements_unlocked)
  with baseline as (
    select min(snapshot_date) as day from playtime_snapshots where player_id = p_player_id
  ),
  diffs as (
    select
      s.snapshot_date,
      s.playtime_minutes - coalesce(lag(s.playtime_minutes) over w, 0) as minutes,
      lag(s.snapshot_date) over w as prev_date,
      (s.last_played_at at time zone 'Asia/Tokyo')::date as played_on
    from playtime_snapshots s
    where s.player_id = p_player_id
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
    where player_id = p_player_id and unlocked_at is not null
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

-- Functions are executable by everyone by default; only the collector should call this.
revoke execute on function public.refresh_daily_activity(uuid) from public, anon, authenticated;
grant execute on function public.refresh_daily_activity(uuid) to service_role;
