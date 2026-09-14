-- =====================================================
-- B2B PLATFORM — MISSING TABLES MIGRATION
-- For fmganuxtqbquubtvvqdo (Shuttler14's Project)
-- Only creates tables that don't already exist
-- =====================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- =====================================================
-- BRAND CATALOGS (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS brand_catalogs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'Main Catalog',
    sync_status TEXT DEFAULT 'idle',
    product_count INTEGER DEFAULT 0,
    last_synced_at TIMESTAMPTZ,
    feed_url TEXT DEFAULT '',
    sync_config JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- BRAND PRODUCTS (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS brand_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_id UUID NOT NULL REFERENCES brand_catalogs(id) ON DELETE CASCADE,
    external_id TEXT NOT NULL,
    brand TEXT DEFAULT '',
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    price NUMERIC(12,2) DEFAULT 0,
    currency TEXT DEFAULT 'INR',
    image_url TEXT NOT NULL,
    images JSONB DEFAULT '[]'::jsonb,
    category TEXT DEFAULT '',
    subcategory TEXT DEFAULT '',
    tags JSONB DEFAULT '[]'::jsonb,
    sizes JSONB DEFAULT '[]'::jsonb,
    colors JSONB DEFAULT '[]'::jsonb,
    sku TEXT DEFAULT '',
    color TEXT DEFAULT '',
    size TEXT DEFAULT '',
    material TEXT DEFAULT '',
    gender TEXT DEFAULT 'unisex',
    marketplace_source TEXT DEFAULT '',
    uploaded_by TEXT DEFAULT 'api',
    flat_lay_url TEXT DEFAULT '',
    embedding_vector vector(1536),
    embedding JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(catalog_id, external_id)
);

-- =====================================================
-- SUBSCRIPTION EVENTS (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS subscription_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'razorpay',
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- USERS (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fingerprint_id TEXT UNIQUE NOT NULL,
    email TEXT,
    display_name TEXT DEFAULT 'Fashion Explorer',
    avatar_url TEXT DEFAULT '',
    preferred_brands UUID[] DEFAULT '{}',
    style_preferences JSONB DEFAULT '{
        "occasions": ["casual", "formal", "party"],
        "price_tier": "mid",
        "color_preferences": [],
        "size": {}
    }'::jsonb,
    closet_item_count INTEGER DEFAULT 0,
    total_recommendations INTEGER DEFAULT 0,
    is_anonymous BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- USER CLOSET ITEMS (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS user_closet_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    thumbnail_url TEXT DEFAULT '',
    category TEXT NOT NULL DEFAULT 'top',
    color_primary TEXT DEFAULT '',
    color_secondary TEXT DEFAULT '',
    pattern TEXT DEFAULT 'solid',
    material TEXT DEFAULT '',
    brand_name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    embedding_vector vector(1536),
    embedding JSONB,
    metadata JSONB DEFAULT '{
        "ai_detected": false,
        "fit": "regular",
        "season": "all-season"
    }'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- CROSS-BRAND CLOSET VISIBILITY (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS cross_brand_closet (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    closet_item_id UUID NOT NULL REFERENCES user_closet_items(id) ON DELETE CASCADE,
    visible_brand_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, closet_item_id)
);

-- =====================================================
-- RECOMMENDATION SESSIONS (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS recommendation_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    occasion TEXT NOT NULL DEFAULT 'casual',
    price_tier TEXT NOT NULL DEFAULT 'mid',
    budget_min NUMERIC(12,2),
    budget_max NUMERIC(12,2),
    include_closet BOOLEAN DEFAULT FALSE,
    results JSONB DEFAULT '[]'::jsonb,
    vton_preview_url TEXT,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- =====================================================
-- RECOMMENDATION ITEMS (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS recommendation_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES recommendation_sessions(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    item_ref_id UUID,
    rank INTEGER NOT NULL DEFAULT 0,
    title TEXT DEFAULT '',
    image_url TEXT DEFAULT '',
    reason TEXT DEFAULT '',
    is_gap_item BOOLEAN DEFAULT FALSE,
    affiliate_url TEXT DEFAULT '',
    clicked BOOLEAN DEFAULT FALSE,
    added_to_cart BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- WIDGET ANALYTICS (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS widget_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    event_data JSONB DEFAULT '{}'::jsonb,
    session_id UUID,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- BRAND SYNDICATE RULES (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS brand_syndicate_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    allowed_categories TEXT[] DEFAULT '{}',
    blocked_categories TEXT[] DEFAULT '{}',
    min_partner_price NUMERIC(12,2) DEFAULT 0,
    max_partner_price NUMERIC(12,2) DEFAULT 999999,
    allowed_tiers TEXT[] DEFAULT '{}',
    approved_partner_brand_ids UUID[] DEFAULT '{}',
    blocked_partner_brand_ids UUID[] DEFAULT '{}',
    affiliate_commission_rate NUMERIC(5,4) DEFAULT 0.0700,
    cpa_rate NUMERIC(5,4) DEFAULT 0.1000,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(brand_id)
);

-- =====================================================
-- BRAND SYNDICATE PAIRINGS (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS brand_syndicate_pairings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    guest_brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    host_commission_rate NUMERIC(5,4),
    guest_cpa_rate NUMERIC(5,4),
    total_clicks INTEGER DEFAULT 0,
    total_conversions INTEGER DEFAULT 0,
    total_revenue_generated NUMERIC(12,2) DEFAULT 0,
    total_commissions_earned NUMERIC(12,2) DEFAULT 0,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(host_brand_id, guest_brand_id)
);

-- =====================================================
-- AFFILIATE TRANSACTIONS (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS affiliate_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_brand_id UUID NOT NULL REFERENCES brands(id),
    guest_brand_id UUID NOT NULL REFERENCES brands(id),
    user_id UUID REFERENCES users(id),
    order_id TEXT,
    order_total NUMERIC(12,2) NOT NULL,
    currency TEXT DEFAULT 'INR',
    product_id UUID,
    product_title TEXT,
    product_sku TEXT,
    product_price NUMERIC(12,2),
    quantity INTEGER DEFAULT 1,
    host_commission_rate NUMERIC(5,4),
    host_commission_amount NUMERIC(12,2),
    guest_cpa_rate NUMERIC(5,4),
    guest_cpa_amount NUMERIC(12,2),
    platform_fee_rate NUMERIC(5,4) DEFAULT 0.0300,
    platform_fee_amount NUMERIC(12,2),
    widget_session_id UUID,
    referral_source TEXT DEFAULT 'widget',
    host_commission_status TEXT DEFAULT 'pending',
    guest_cpa_status TEXT DEFAULT 'pending',
    platform_fee_status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    paid_at TIMESTAMPTZ
);

-- =====================================================
-- AFFILIATE PAYOUTS (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id),
    payout_type TEXT NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    currency TEXT DEFAULT 'INR',
    transaction_count INTEGER DEFAULT 0,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    payment_method TEXT,
    payment_reference TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- =====================================================
-- CART HANDOFFS (missing)
-- =====================================================
CREATE TABLE IF NOT EXISTS cart_handoffs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_brand_id UUID NOT NULL REFERENCES brands(id),
    guest_brand_id UUID NOT NULL REFERENCES brands(id),
    widget_session_id UUID,
    user_id UUID REFERENCES users(id),
    target_checkout_url TEXT NOT NULL,
    product_sku TEXT,
    product_id TEXT,
    selected_size TEXT,
    selected_color TEXT,
    quantity INTEGER DEFAULT 1,
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,
    converted BOOLEAN DEFAULT FALSE,
    order_id TEXT,
    order_value NUMERIC(12,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    converted_at TIMESTAMPTZ
);

-- =====================================================
-- GLOBAL INVENTORY (create with RLS enabled)
-- =====================================================
CREATE TABLE IF NOT EXISTS global_inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand TEXT DEFAULT '',
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    price NUMERIC(12,2) DEFAULT 0,
    currency TEXT DEFAULT 'INR',
    image_url TEXT DEFAULT '',
    category TEXT DEFAULT '',
    subcategory TEXT DEFAULT '',
    tags JSONB DEFAULT '[]'::jsonb,
    color TEXT DEFAULT '',
    size TEXT DEFAULT '',
    material TEXT DEFAULT '',
    gender TEXT DEFAULT 'unisex',
    marketplace_source TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS on global_inventory
ALTER TABLE global_inventory ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role full access global_inventory" ON global_inventory;
CREATE POLICY "Service role full access global_inventory"
ON global_inventory FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Authenticated read global_inventory" ON global_inventory;
CREATE POLICY "Authenticated read global_inventory"
ON global_inventory FOR SELECT USING (true);

-- =====================================================
-- INDEXES
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_catalogs_brand ON brand_catalogs(brand_id);
CREATE INDEX IF NOT EXISTS idx_products_catalog ON brand_products(catalog_id);
CREATE INDEX IF NOT EXISTS idx_products_brand ON brand_products(brand);
CREATE INDEX IF NOT EXISTS idx_products_category ON brand_products(category);
CREATE INDEX IF NOT EXISTS idx_products_active ON brand_products(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_products_embedding ON brand_products USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_users_fingerprint ON users(fingerprint_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_closet_user ON user_closet_items(user_id);
CREATE INDEX IF NOT EXISTS idx_closet_category ON user_closet_items(category);
CREATE INDEX IF NOT EXISTS idx_closet_embedding ON user_closet_items USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_cross_brand_user ON cross_brand_closet(user_id);
CREATE INDEX IF NOT EXISTS idx_rec_sessions_user ON recommendation_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_rec_sessions_brand ON recommendation_sessions(brand_id);
CREATE INDEX IF NOT EXISTS idx_rec_items_session ON recommendation_items(session_id);
CREATE INDEX IF NOT EXISTS idx_analytics_brand ON widget_analytics(brand_id);
CREATE INDEX IF NOT EXISTS idx_analytics_type ON widget_analytics(event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_created ON widget_analytics(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_syndicate_rules_brand ON brand_syndicate_rules(brand_id);
CREATE INDEX IF NOT EXISTS idx_syndicate_pairings_host ON brand_syndicate_pairings(host_brand_id);
CREATE INDEX IF NOT EXISTS idx_syndicate_pairings_guest ON brand_syndicate_pairings(guest_brand_id);
CREATE INDEX IF NOT EXISTS idx_syndicate_pairings_status ON brand_syndicate_pairings(status);
CREATE INDEX IF NOT EXISTS idx_affiliate_tx_host ON affiliate_transactions(host_brand_id);
CREATE INDEX IF NOT EXISTS idx_affiliate_tx_guest ON affiliate_transactions(guest_brand_id);
CREATE INDEX IF NOT EXISTS idx_affiliate_tx_created ON affiliate_transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payouts_brand ON affiliate_payouts(brand_id);
CREATE INDEX IF NOT EXISTS idx_handoffs_host ON cart_handoffs(host_brand_id);
CREATE INDEX IF NOT EXISTS idx_handoffs_guest ON cart_handoffs(guest_brand_id);
CREATE INDEX IF NOT EXISTS idx_handoffs_created ON cart_handoffs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sub_events_brand ON subscription_events(brand_id);

-- =====================================================
-- TRIGGERS
-- =====================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_brands_updated') THEN
        CREATE TRIGGER trg_brands_updated BEFORE UPDATE ON brands
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_subs_updated') THEN
        CREATE TRIGGER trg_subs_updated BEFORE UPDATE ON brand_subscriptions
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_catalogs_updated') THEN
        CREATE TRIGGER trg_catalogs_updated BEFORE UPDATE ON brand_catalogs
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_products_updated') THEN
        CREATE TRIGGER trg_products_updated BEFORE UPDATE ON brand_products
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_closet_updated') THEN
        CREATE TRIGGER trg_closet_updated BEFORE UPDATE ON user_closet_items
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_syndicate_rules_updated') THEN
        CREATE TRIGGER trg_syndicate_rules_updated BEFORE UPDATE ON brand_syndicate_rules
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_syndicate_pairings_updated') THEN
        CREATE TRIGGER trg_syndicate_pairings_updated BEFORE UPDATE ON brand_syndicate_pairings
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
END $$;

-- Sync embedding_vector from embedding JSONB
CREATE OR REPLACE FUNCTION sync_embedding_vector()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.embedding IS NULL THEN
        NEW.embedding_vector = NULL;
    ELSE
        NEW.embedding_vector = (
            SELECT array_agg((value)::float4 ORDER BY ord)::vector
            FROM jsonb_array_elements_text(NEW.embedding) WITH ordinality AS j(value, ord)
        );
    END IF;
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_product_embedding ON brand_products;
CREATE TRIGGER trg_sync_product_embedding
    BEFORE INSERT OR UPDATE OF embedding ON brand_products
    FOR EACH ROW EXECUTE FUNCTION sync_embedding_vector();

DROP TRIGGER IF EXISTS trg_sync_closet_embedding ON user_closet_items;
CREATE TRIGGER trg_sync_closet_embedding
    BEFORE INSERT OR UPDATE OF embedding ON user_closet_items
    FOR EACH ROW EXECUTE FUNCTION sync_embedding_vector();

-- =====================================================
-- RPC FUNCTIONS
-- =====================================================
CREATE OR REPLACE FUNCTION is_brand_subscription_active(p_brand_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    sub_status TEXT;
    period_end TIMESTAMPTZ;
BEGIN
    SELECT status, current_period_end INTO sub_status, period_end
    FROM brand_subscriptions WHERE brand_id = p_brand_id;
    RETURN sub_status = 'active'
       OR (sub_status = 'trialing' AND period_end > NOW());
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION increment_recommendation_usage(p_brand_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE brand_subscriptions
    SET monthly_recommendations_used = monthly_recommendations_used + 1
    WHERE brand_id = p_brand_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION increment_closet_count(p_user_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE users
    SET closet_item_count = closet_item_count + 1
    WHERE id = p_user_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION match_brand_products(
    p_brand_id UUID,
    query_embedding jsonb,
    query_category TEXT DEFAULT NULL,
    query_price_min NUMERIC DEFAULT NULL,
    query_price_max NUMERIC DEFAULT NULL,
    match_count INT DEFAULT 6
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    description TEXT,
    price NUMERIC,
    currency TEXT,
    image_url TEXT,
    category TEXT,
    tags JSONB,
    similarity FLOAT4
)
LANGUAGE sql STABLE
AS $$
    WITH q AS (
        SELECT (
            SELECT array_agg((value)::float4 ORDER BY ord)::vector
            FROM jsonb_array_elements_text(query_embedding) WITH ordinality AS j(value, ord)
        ) AS emb
    )
    SELECT
        bp.id, bp.title, bp.description, bp.price, bp.currency,
        bp.image_url, bp.category, bp.tags,
        1 - (bp.embedding_vector <=> q.emb) AS similarity
    FROM brand_products bp
    JOIN brand_catalogs bc ON bp.catalog_id = bc.id
    CROSS JOIN q
    WHERE bc.brand_id = p_brand_id
      AND bp.is_active = true
      AND bp.embedding_vector IS NOT NULL
      AND (query_category IS NULL OR query_category = '' OR bp.category ILIKE '%' || query_category || '%')
      AND (query_price_min IS NULL OR bp.price >= query_price_min)
      AND (query_price_max IS NULL OR bp.price <= query_price_max)
    ORDER BY bp.embedding_vector <=> q.emb
    LIMIT GREATEST(1, LEAST(match_count, 20));
$$;

-- =====================================================
-- FIX: brand_dashboard_summary (remove SECURITY DEFINER)
-- =====================================================
DROP VIEW IF EXISTS brand_dashboard_summary;
CREATE VIEW brand_dashboard_summary AS
SELECT
    b.id,
    b.name,
    b.slug,
    b.is_active,
    bs.plan_tier,
    bs.status AS subscription_status,
    bs.monthly_recommendations_used,
    bs.monthly_recommendations_limit,
    bs.current_period_end,
    (SELECT COUNT(*) FROM brand_catalogs bc WHERE bc.brand_id = b.id) AS catalog_count,
    (SELECT COALESCE(SUM(bc2.product_count), 0) FROM brand_catalogs bc2 WHERE bc2.brand_id = b.id) AS total_products,
    b.created_at
FROM brands b
LEFT JOIN brand_subscriptions bs ON b.id = bs.brand_id;

-- =====================================================
-- STORAGE BUCKETS
-- =====================================================
INSERT INTO storage.buckets (id, name, public)
VALUES ('closet-items', 'closet-items', false)
ON CONFLICT (id) DO NOTHING;

INSERT INTO storage.buckets (id, name, public)
VALUES ('brand-logos', 'brand-logos', true)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "Service role full access closet" ON storage.objects;
CREATE POLICY "Service role full access closet"
ON storage.objects FOR ALL
USING (bucket_id = 'closet-items')
WITH CHECK (bucket_id = 'closet-items');

DROP POLICY IF EXISTS "Public read brand logos" ON storage.objects;
CREATE POLICY "Public read brand logos"
ON storage.objects FOR SELECT
USING (bucket_id = 'brand-logos');

-- =====================================================
-- DONE
-- =====================================================
SELECT 'B2B Platform migration complete! All missing tables created.' AS status;
