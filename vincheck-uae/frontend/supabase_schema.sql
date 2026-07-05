-- Run this in your Supabase project's SQL Editor (left sidebar → SQL Editor → New query)
-- before using the history feature. This creates the table that stores every
-- VIN check tied to the user who ran it.

create table check_history (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) on delete cascade not null,
  vin text not null,
  make text,
  model text,
  year text,
  trust_score int,
  verdict text,
  is_salvage boolean,
  checked_at timestamptz default now()
);

-- Row Level Security: without this, any logged-in user could read or write
-- any other user's history through the API. This restricts each user to
-- only their own rows.
alter table check_history enable row level security;

create policy "Users can view their own history"
  on check_history for select
  using (auth.uid() = user_id);

create policy "Users can insert their own history"
  on check_history for insert
  with check (auth.uid() = user_id);

-- Optional: speeds up the "most recent first" query the History page uses.
create index check_history_user_checked_idx
  on check_history (user_id, checked_at desc);
