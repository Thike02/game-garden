-- Images uploaded from the local admin for hand-entered games.
-- Public bucket: anyone can view the files by URL; only the service_role key (the admin) can write.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'game-images',
  'game-images',
  true,
  5242880,  -- 5 MB
  array['image/jpeg', 'image/png', 'image/webp', 'image/gif']
)
on conflict (id) do nothing;
