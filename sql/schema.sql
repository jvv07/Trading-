-- ============================================================
-- Trading Dashboard — Supabase Schema
-- Run this in the Supabase SQL editor (Database > SQL Editor)
-- ============================================================

-- Enable RLS on all tables
-- Each table is scoped to auth.uid() so users only see their own data.

-- ── strategies ───────────────────────────────────────────────────────────────
create table if not exists strategies (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  name        text not null,
  description text,
  status      text not null default 'active' check (status in ('active','paused','archived')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

alter table strategies enable row level security;

create policy "users_own_strategies" on strategies
  for all using (user_id = auth.uid());

-- ── positions ────────────────────────────────────────────────────────────────
create table if not exists positions (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  strategy_id   uuid references strategies(id) on delete set null,
  symbol        text not null,
  quantity      numeric not null,
  avg_cost      numeric not null,
  opened_at     timestamptz not null default now(),
  closed_at     timestamptz,
  status        text not null default 'open' check (status in ('open','closed'))
);

alter table positions enable row level security;

create policy "users_own_positions" on positions
  for all using (user_id = auth.uid());

-- ── trades ───────────────────────────────────────────────────────────────────
create table if not exists trades (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  position_id   uuid references positions(id) on delete set null,
  strategy_id   uuid references strategies(id) on delete set null,
  symbol        text not null,
  side          text not null check (side in ('buy','sell')),
  quantity      numeric not null,
  price         numeric not null,
  commission    numeric not null default 0,
  executed_at   timestamptz not null default now(),
  source        text not null default 'manual' check (source in ('manual','ibkr','yfinance'))
);

alter table trades enable row level security;

create policy "users_own_trades" on trades
  for all using (user_id = auth.uid());

-- ── performance_snapshots ────────────────────────────────────────────────────
-- Daily snapshot for equity curve charting (written by cron / edge function)
create table if not exists performance_snapshots (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  strategy_id   uuid references strategies(id) on delete cascade,
  snapshot_date date not null,
  equity        numeric not null,
  cash          numeric not null default 0,
  realized_pnl  numeric not null default 0,
  unrealized_pnl numeric not null default 0,
  unique (user_id, strategy_id, snapshot_date)
);

alter table performance_snapshots enable row level security;

create policy "users_own_snapshots" on performance_snapshots
  for all using (user_id = auth.uid());

-- ── helper: updated_at trigger ───────────────────────────────────────────────
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;

create trigger strategies_updated_at
  before update on strategies
  for each row execute function set_updated_at();
