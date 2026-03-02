-- ============================================================
-- Migration v2 — Watchlist, Trade Notes, Backtest Runs
-- Run in Supabase SQL Editor
-- ============================================================

create table if not exists watchlist (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null,
  symbol     text not null,
  notes      text,
  added_at   timestamptz not null default now(),
  unique (user_id, symbol)
);

create table if not exists trade_notes (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null,
  trade_id   uuid references trades(id) on delete cascade,
  note       text not null,
  tags       text[],
  created_at timestamptz not null default now()
);

create table if not exists backtest_runs (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null,
  strategy_name text not null,
  symbol        text not null,
  params        jsonb not null default '{}',
  start_date    date,
  end_date      date,
  metrics       jsonb not null default '{}',
  created_at    timestamptz not null default now()
);

create table if not exists journal_entries (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null,
  entry_date date not null default current_date,
  title      text,
  body       text not null,
  tags       text[],
  mood       text check (mood in ('confident','neutral','uncertain','fearful','greedy')),
  created_at timestamptz not null default now()
);
