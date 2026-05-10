-- Legal Doc Catalog — Supabase schema
-- Run this in the Supabase SQL Editor after creating your project.

-- Documents table: stores metadata + full extracted text
create table documents (
  id          uuid default gen_random_uuid() primary key,
  user_id     uuid references auth.users(id) not null,
  title       text not null,
  filename    text not null,
  category    text not null,
  year        integer,
  body_text   text not null default '',
  word_count  integer not null default 0,
  fts         tsvector generated always as (
                to_tsvector('english'::regconfig, coalesce(title, '') || ' ' || coalesce(body_text, ''))
              ) stored,
  created_at  timestamptz default now()
);

-- Full-text search index
create index documents_fts_idx on documents using gin (fts);

-- Filter indexes
create index documents_category_idx on documents (category);
create index documents_year_idx on documents (year);

-- Row Level Security
alter table documents enable row level security;

create policy "Users can view own documents"
  on documents for select
  using (auth.uid() = user_id);

create policy "Users can insert own documents"
  on documents for insert
  with check (auth.uid() = user_id);

create policy "Users can update own documents"
  on documents for update
  using (auth.uid() = user_id);

create policy "Users can delete own documents"
  on documents for delete
  using (auth.uid() = user_id);

-- Search function: returns results with highlighted snippets
create or replace function search_documents(search_query text)
returns table (
  id uuid,
  title text,
  category text,
  year integer,
  word_count integer,
  headline text
)
language sql
security definer
as $$
  select
    d.id,
    d.title,
    d.category,
    d.year,
    d.word_count,
    ts_headline('english'::regconfig, d.body_text, websearch_to_tsquery('english'::regconfig, search_query),
      'StartSel=<mark>, StopSel=</mark>, MaxWords=35, MinWords=15') as headline
  from documents d
  where d.fts @@ websearch_to_tsquery('english'::regconfig, search_query)
    and d.user_id = auth.uid()
  order by ts_rank(d.fts, websearch_to_tsquery('english'::regconfig, search_query)) desc;
$$;
