-- The Steam avatar frame the player has equipped (Points Shop item), refreshed by the daily sync.
-- Animated APNG for normal display, static PNG for people who prefer reduced motion.
alter table public.players
  add column avatar_frame_url        text,
  add column avatar_frame_static_url text;
