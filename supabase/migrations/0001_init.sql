-- Game Garden initial schema.
-- Run in the Supabase SQL editor (or `supabase db push`).
-- Writes happen only with the service_role key (collector / local admin),
-- which bypasses RLS. The public web page uses the anon key and can only read.

-- ---------------------------------------------------------------------------
-- Players (one row per tracked person, so friends can be added later)
-- ---------------------------------------------------------------------------
create table public.players (
  id            uuid primary key default gen_random_uuid(),
  steam_id      text unique,                -- SteamID64; null for non-Steam-only players
  display_name  text not null,
  avatar_url    text,
  created_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Games (Steam and non-Steam share one catalog)
-- ---------------------------------------------------------------------------
create table public.games (
  id                    bigint generated always as identity primary key,
  platform              text not null default 'steam',   -- 'steam', 'switch', 'ps', 'other', ...
  steam_appid           integer unique,                   -- null for non-Steam games
  itad_id               text unique,                      -- IsThereAnyDeal game id
  name                  text not null,
  header_image_url      text,
  -- Historical low (from ITAD, or our own price_history)
  lowest_price          integer,                          -- minor units (JPY: yen)
  lowest_price_currency text,
  lowest_price_at       timestamptz,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  constraint games_steam_has_appid check (platform <> 'steam' or steam_appid is not null)
);

-- ---------------------------------------------------------------------------
-- Ownership and progress
-- ---------------------------------------------------------------------------
create table public.owned_games (
  player_id               uuid   not null references public.players (id) on delete cascade,
  game_id                 bigint not null references public.games (id) on delete cascade,
  source                  text   not null default 'steam',  -- 'steam' (auto) or 'manual'
  playtime_minutes        integer not null default 0,
  last_played_at          timestamptz,
  achievements_total      integer,                          -- null when the game has none / unknown
  achievements_unlocked   integer,
  achievements_synced_at  timestamptz,
  updated_at              timestamptz not null default now(),
  primary key (player_id, game_id)
);

-- Achievement definitions with global unlock rate (used for rarity badges)
create table public.achievements (
  game_id         bigint not null references public.games (id) on delete cascade,
  api_name        text   not null,
  display_name    text   not null,
  description     text,
  icon_url        text,
  icon_gray_url   text,
  hidden          boolean not null default false,
  global_percent  numeric(6, 3),                            -- 0.000 - 100.000
  updated_at      timestamptz not null default now(),
  primary key (game_id, api_name)
);

create table public.player_achievements (
  player_id    uuid   not null references public.players (id) on delete cascade,
  game_id      bigint not null,
  api_name     text   not null,
  unlocked_at  timestamptz,                                 -- null if Steam reports no time
  primary key (player_id, game_id, api_name),
  foreign key (game_id, api_name) references public.achievements (game_id, api_name) on delete cascade
);
create index player_achievements_unlocked_at_idx on public.player_achievements (player_id, unlocked_at);

-- Daily playtime snapshots; day-to-day deltas feed the activity grid ("grass")
create table public.playtime_snapshots (
  player_id         uuid   not null references public.players (id) on delete cascade,
  game_id           bigint not null references public.games (id) on delete cascade,
  snapshot_date     date   not null,
  playtime_minutes  integer not null,
  primary key (player_id, game_id, snapshot_date)
);

-- Aggregated per-day activity shown as the grass grid
create table public.daily_activity (
  player_id              uuid not null references public.players (id) on delete cascade,
  activity_date          date not null,
  minutes_played         integer not null default 0,
  achievements_unlocked  integer not null default 0,
  primary key (player_id, activity_date)
);

-- ---------------------------------------------------------------------------
-- Wishlist and prices
-- ---------------------------------------------------------------------------
create table public.wishlist_items (
  player_id   uuid   not null references public.players (id) on delete cascade,
  game_id     bigint not null references public.games (id) on delete cascade,
  added_at    timestamptz,
  priority    integer,
  removed_at  timestamptz,                                  -- set when it leaves the wishlist (bought / removed)
  primary key (player_id, game_id)
);

create table public.price_history (
  game_id        bigint not null references public.games (id) on delete cascade,
  shop           text   not null default 'steam',
  recorded_on    date   not null,
  price          integer not null,                          -- current price, minor units
  regular_price  integer not null,
  discount_pct   integer not null default 0,
  currency       text   not null,
  source         text   not null default 'collector',      -- 'collector' (daily) or 'itad' (backfill)
  primary key (game_id, shop, recorded_on)
);

-- Sent Discord notifications, so one sale is announced only once
create table public.sale_notifications (
  id           bigint generated always as identity primary key,
  player_id    uuid   not null references public.players (id) on delete cascade,
  game_id      bigint not null references public.games (id) on delete cascade,
  price        integer not null,
  discount_pct integer not null,
  score        numeric(8, 3),
  notified_at  timestamptz not null default now()
);
create index sale_notifications_lookup_idx on public.sale_notifications (player_id, game_id, notified_at desc);

-- ---------------------------------------------------------------------------
-- Job bookkeeping (used to decide what needs updating)
-- ---------------------------------------------------------------------------
create table public.job_runs (
  job          text not null,                               -- 'owned', 'achievements', 'wishlist', 'notify', ...
  player_id    uuid references public.players (id) on delete cascade,
  last_run_at  timestamptz not null,
  status       text not null default 'ok',
  detail       text,
  unique nulls not distinct (job, player_id)
);

-- ---------------------------------------------------------------------------
-- Row level security: anon/authenticated may read, nobody but service_role may write
-- ---------------------------------------------------------------------------
do $$
declare
  t text;
begin
  foreach t in array array[
    'players', 'games', 'owned_games', 'achievements', 'player_achievements',
    'playtime_snapshots', 'daily_activity', 'wishlist_items', 'price_history',
    'sale_notifications', 'job_runs'
  ]
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format(
      'create policy "public read" on public.%I for select to anon, authenticated using (true)', t
    );
  end loop;
end
$$;
