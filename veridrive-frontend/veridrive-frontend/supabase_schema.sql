-- Run this in your Supabase project's SQL Editor (left sidebar → SQL Editor → New query)
-- before using login/history. Creates the table that stores every completed
-- verification report tied to the user who ran it.

create table report_history (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) on delete cascade not null,
  listing_url text,
  make text,
  model text,
  year text,
  composite_score int,
  report_json jsonb not null,      -- the full report object, as-is
  checked_at timestamptz default now()
);

-- Row Level Security: without this, any logged-in user could read or write
-- any other user's history through the API.
alter table report_history enable row level security;

create policy "Users can view their own report history"
  on report_history for select
  using (auth.uid() = user_id);

create policy "Users can insert their own report history"
  on report_history for insert
  with check (auth.uid() = user_id);

create index report_history_user_checked_idx
  on report_history (user_id, checked_at desc);

-- ---------------------------------------------------------------------------
-- VERIFY: after running everything above, run this on its own to confirm
-- the table exists with the correct columns. You should see exactly these
-- 9 rows back: id, user_id, listing_url, make, model, year,
-- composite_score, report_json, checked_at.
-- ---------------------------------------------------------------------------
--
--   select column_name, data_type
--   from information_schema.columns
--   where table_name = 'report_history'
--   order by ordinal_position;
--
-- ---------------------------------------------------------------------------
-- NOTE: this is a DIFFERENT table from check_history, which belonged to an
-- earlier, now-retired standalone version of the VIN module (VinCheck).
-- If your Supabase project has a check_history table from that earlier
-- version, it is unused by the current frontend and can be ignored or
-- dropped — the current app reads and writes report_history only.
-- ---------------------------------------------------------------------------

