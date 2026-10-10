-- Player-made tags on games ("ストーリークリア", "積みゲー", ...), managed in the local admin.

create table public.tags (
  id          bigint generated always as identity primary key,
  player_id   uuid not null references public.players (id) on delete cascade,
  name        text not null,
  color       text not null default 'blue',   -- a palette name shared by the admin and the web page
  is_public   boolean not null default true,  -- shown on the public page
  sort_order  integer not null default 0,
  created_at  timestamptz not null default now(),
  unique (player_id, name)
);

create table public.game_tags (
  player_id  uuid   not null,
  game_id    bigint not null,
  tag_id     bigint not null references public.tags (id) on delete cascade,
  primary key (tag_id, game_id),
  -- a tag can only be put on a game the player has; removing the game removes its tags
  foreign key (player_id, game_id) references public.owned_games (player_id, game_id) on delete cascade
);
create index game_tags_player_idx on public.game_tags (player_id);

alter table public.tags      enable row level security;
alter table public.game_tags enable row level security;

create policy "public tags" on public.tags
  for select to anon, authenticated
  using (
    is_public
    and exists (select 1 from public.players p where p.id = player_id and p.is_public)
  );

-- The tags subquery is itself filtered by the policy above, so private tags drop out here too.
create policy "public game tags" on public.game_tags
  for select to anon, authenticated
  using (
    exists (select 1 from public.tags t where t.id = tag_id)
    and public.game_visible(player_id, game_id)
  );
