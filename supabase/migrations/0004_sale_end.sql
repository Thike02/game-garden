-- When the current Steam discount ends (from the store; null when not on sale or unknown).
alter table public.price_history add column sale_ends_at timestamptz;
