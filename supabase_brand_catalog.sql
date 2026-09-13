-- =====================================================
-- BRAND CATALOG PRODUCTS (B2B uploaded catalogs)
-- =====================================================

create table if not exists public.brand_products (
    id uuid primary key default gen_random_uuid(),
    brand text not null,
    title text not null,
    price numeric(12,2) default 0,
    currency text default 'INR',
    image_url text not null,
    flat_lay_url text,
    category text default 'top',
    description text default '',
    sku text default '',
    color text default '',
    size text default '',
    material text default '',
    gender text default 'unisex',
    marketplace_source text default 'generic',
    uploaded_by text default 'api',
    is_active boolean default true,
    embedding jsonb,
    embedding_vector vector(1536),
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create index if not exists idx_brand_products_brand on public.brand_products (brand);
create index if not exists idx_brand_products_category on public.brand_products (category);
create index if not exists idx_brand_products_active on public.brand_products (is_active);
create index if not exists idx_brand_products_price on public.brand_products (price);
create index if not exists idx_brand_products_gender on public.brand_products (gender);

-- Vector search index for brand products
create index if not exists idx_brand_products_embedding_vector
    on public.brand_products using ivfflat (embedding_vector vector_cosine_ops) with (lists = 100);

-- Auto-sync embedding vector from jsonb
create or replace function public.sync_brand_products_embedding_vector()
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

drop trigger if exists trg_sync_brand_products_embedding_vector on public.brand_products;
create trigger trg_sync_brand_products_embedding_vector
before insert or update of embedding on public.brand_products
for each row execute function public.sync_brand_products_embedding_vector();

-- =====================================================
-- BRAND CATALOGS (metadata about uploaded catalogs)
-- =====================================================

create table if not exists public.brand_catalogs (
    id uuid primary key default gen_random_uuid(),
    brand_name text not null unique,
    product_count int default 0,
    marketplace_source text default 'generic',
    uploaded_by text default 'api',
    last_upload_at timestamptz default now(),
    is_active boolean default true,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create index if not exists idx_brand_catalogs_name on public.brand_catalogs (brand_name);

-- =====================================================
-- RPC: Search brand products with vector similarity
-- =====================================================

create or replace function public.match_brand_products(
    query_embedding jsonb,
    query_brand text default null,
    query_category text default null,
    query_gender text default null,
    min_price numeric default 0,
    max_price numeric default 999999,
    match_count int default 10
)
returns table (
    id uuid,
    brand text,
    title text,
    price numeric,
    currency text,
    image_url text,
    flat_lay_url text,
    category text,
    description text,
    color text,
    size material text,
    gender text,
    marketplace_source text,
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
        bp.id, bp.brand, bp.title, bp.price, bp.currency,
        bp.image_url, coalesce(bp.flat_lay_url, bp.image_url) as flat_lay_url,
        bp.category, bp.description, bp.color, bp.size, bp.material,
        bp.gender, bp.marketplace_source,
        1 - (bp.embedding_vector <=> q.emb) as similarity
    from public.brand_products bp
    cross join q
    where bp.is_active = true
      and bp.embedding_vector is not null
      and (query_brand is null or query_brand = '' or bp.brand ilike '%' || query_brand || '%')
      and (query_category is null or query_category = '' or bp.category ilike '%' || query_category || '%')
      and (query_gender is null or query_gender = '' or bp.gender = query_gender or bp.gender = 'unisex')
      and bp.price >= min_price
      and bp.price <= max_price
    order by bp.embedding_vector <=> q.emb
    limit greatest(1, least(match_count, 30));
$$;
