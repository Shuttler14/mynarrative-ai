-- =====================================================
-- GLOBAL INVENTORY (CJ / Rakuten curated feed)
-- =====================================================
create extension if not exists vector;

create table if not exists public.global_inventory (
    id uuid primary key default gen_random_uuid(),
    network text not null,
    external_product_id text not null,
    title text not null,
    brand text default '',
    category text default '',
    description text default '',
    price numeric(12,2) default 0,
    currency text default 'INR',
    image_url text not null,
    flat_lay_url text,
    checkout_url text,
    affiliate_url text not null,
    embedding jsonb,
    embedding_vector vector(1536),
    quality_score numeric(6,4) default 0,
    is_clean boolean default true,
    filter_reason text default '',
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique(network, external_product_id)
);

create index if not exists idx_global_inventory_clean on public.global_inventory (is_clean);
create index if not exists idx_global_inventory_category on public.global_inventory (category);
create index if not exists idx_global_inventory_network on public.global_inventory (network);
create index if not exists idx_global_inventory_embedding_vector
    on public.global_inventory using ivfflat (embedding_vector vector_cosine_ops) with (lists = 100);

create or replace function public.sync_global_inventory_embedding_vector()
returns trigger
language plpgsql
as $$
begin
    if new.embedding is null then
        new.embedding_vector = null;
    else
        new.embedding_vector = (
            select array_agg((value)::float4 order by ord)::vector
            from jsonb_array_elements_text(new.embedding) with ordinality as j(value, ord)
        );
    end if;
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_sync_global_inventory_embedding_vector on public.global_inventory;
create trigger trg_sync_global_inventory_embedding_vector
before insert or update of embedding on public.global_inventory
for each row execute function public.sync_global_inventory_embedding_vector();

create or replace function public.match_global_inventory(
    query_embedding jsonb,
    query_category text default null,
    match_count int default 6
)
returns table (
    id uuid,
    network text,
    external_product_id text,
    title text,
    brand text,
    category text,
    price numeric,
    currency text,
    image_url text,
    flat_lay_url text,
    checkout_url text,
    affiliate_url text,
    quality_score numeric,
    similarity float4
)
language sql
stable
as $$
    with q as (
        select (
            select array_agg((value)::float4 order by ord)::vector
            from jsonb_array_elements_text(query_embedding) with ordinality as j(value, ord)
        ) as emb
    )
    select
        gi.id,
        gi.network,
        gi.external_product_id,
        gi.title,
        gi.brand,
        gi.category,
        gi.price,
        gi.currency,
        gi.image_url,
        coalesce(gi.flat_lay_url, gi.image_url) as flat_lay_url,
        coalesce(gi.checkout_url, gi.affiliate_url) as checkout_url,
        gi.affiliate_url,
        gi.quality_score,
        1 - (gi.embedding_vector <=> q.emb) as similarity
    from public.global_inventory gi
    cross join q
    where gi.is_clean = true
      and gi.embedding_vector is not null
      and (query_category is null or query_category = '' or gi.category ilike '%' || query_category || '%')
    order by gi.embedding_vector <=> q.emb
    limit greatest(1, least(match_count, 20));
$$;
