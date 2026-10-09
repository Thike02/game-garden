-- Per-player visibility for the public page.
-- The anon key could read every table directly, so hiding things in the UI alone is not enough:
-- these rules are enforced by RLS (and by masking views for column-level hiding).

alter table public.players
  add column is_public     boolean not null default false,  -- show this player at all
  add column show_playtime boolean not null default false,  -- playtime and playtime-based activity
  add column show_wishlist boolean not null default false;  -- wishlist and sale notifications

-- Players that already exist are the repository owner; new players (friends) start private.
update public.players set is_public = true, show_playtime = true, show_wishlist = true;

-- ---------------------------------------------------------------------------
-- Replace the "everyone can read" policies on per-player tables.
-- Shared catalog tables (games, achievements, price_history) stay public.
-- ---------------------------------------------------------------------------
drop policy "public read" on public.players;
drop policy "public read" on public.owned_games;
drop policy "public read" on public.player_achievements;
drop policy "public read" on public.playtime_snapshots;
drop policy "public read" on public.daily_activity;
drop policy "public read" on public.wishlist_items;
drop policy "public read" on public.sale_notifications;
drop policy "public read" on public.job_runs;

create policy "public players" on public.players
  for select to anon, authenticated
  using (is_public);

create policy "public players" on public.player_achievements
  for select to anon, authenticated
  using (exists (select 1 from public.players p where p.id = player_id and p.is_public));

create policy "public playtime" on public.playtime_snapshots
  for select to anon, authenticated
  using (exists (select 1 from public.players p where p.id = player_id and p.is_public and p.show_playtime));

create policy "public wishlist" on public.wishlist_items
  for select to anon, authenticated
  using (exists (select 1 from public.players p where p.id = player_id and p.is_public and p.show_wishlist));

create policy "public wishlist" on public.sale_notifications
  for select to anon, authenticated
  using (exists (select 1 from public.players p where p.id = player_id and p.is_public and p.show_wishlist));

-- owned_games, daily_activity: no direct read; use the masking views below.
-- job_runs: internal bookkeeping, not readable with the anon key.

-- ---------------------------------------------------------------------------
-- Masking views. They run with the view owner's rights (deliberately not
-- security_invoker) so they can read the base tables, and apply the rules themselves.
-- ---------------------------------------------------------------------------
create view public.player_games as
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
where p.is_public;

create view public.player_activity as
select
  a.player_id,
  a.activity_date,
  case when p.show_playtime then a.minutes_played end as minutes_played,
  a.achievements_unlocked
from public.daily_activity a
join public.players p on p.id = a.player_id
where p.is_public;

grant select on public.player_games, public.player_activity to anon, authenticated;
