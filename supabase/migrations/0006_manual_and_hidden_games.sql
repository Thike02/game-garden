-- Games added by hand in the local admin:
--   owned_games.source = 'manual'    : non-Steam games (counts typed in by hand)
--   owned_games.source = 'community' : Steam games the Web API hides (e.g. titles with mature
--                                      content); achievements are read from the profile page
-- Each owned game can be hidden from the public page individually.

alter table public.owned_games add column is_visible boolean not null default true;

-- RLS subqueries run with the caller's rights, and anon cannot read owned_games directly,
-- so visibility is looked up through this definer function.
create or replace function public.game_visible(p_player_id uuid, p_game_id bigint)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    (select is_visible from owned_games where player_id = p_player_id and game_id = p_game_id),
    true
  )
$$;

drop policy "public players" on public.player_achievements;
create policy "public players" on public.player_achievements
  for select to anon, authenticated
  using (
    exists (select 1 from public.players p where p.id = player_id and p.is_public)
    and public.game_visible(player_id, game_id)
  );

drop policy "public playtime" on public.playtime_snapshots;
create policy "public playtime" on public.playtime_snapshots
  for select to anon, authenticated
  using (
    exists (select 1 from public.players p where p.id = player_id and p.is_public and p.show_playtime)
    and public.game_visible(player_id, game_id)
  );

create or replace view public.player_games as
select
  og.player_id,
  og.game_id,
  og.source,
  case when p.show_playtime then og.playtime_minutes end as playtime_minutes,
  case when p.show_playtime then og.last_played_at end   as last_played_at,
  og.achievements_total,
  og.achievements_unlocked,
  og.achievements_synced_at
from public.owned_games og
join public.players p on p.id = og.player_id
where p.is_public and og.is_visible;

-- Same as 0003, but hidden games no longer count toward the activity grid.
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
      s.playtime_minutes - coalesce(lag(s.playtime_minutes) over w, 0) as minutes,
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
