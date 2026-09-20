-- =====================================================
-- NARRATIVE COMMERCE NETWORK — Database Migration
-- B2B fashion recommendation network schema.
-- Run AFTER supabase_b2b_complete.sql
-- =====================================================

-- =====================================================
-- 1. BRAND DNA — Computed brand profile
-- =====================================================
CREATE TABLE IF NOT EXISTS brand_dna (
    brand_id UUID PRIMARY KEY REFERENCES brands(id) ON DELETE CASCADE,
    style_profile JSONB DEFAULT '{
        "classic": 0.5, "minimalist": 0.5, "streetwear": 0.1,
        "bohemian": 0.1, "romantic": 0.1, "edgy": 0.1
    }'::jsonb,
    price_positioning JSONB DEFAULT '{
        "min": 0, "max": 0, "avg": 0, "tier": "mid",
        "p25": 0, "p75": 0
    }'::jsonb,
    target_demographics JSONB DEFAULT '{
        "age_min": 18, "age_max": 65, "gender": "unisex"
    }'::jsonb,
    category_strength JSONB DEFAULT '{}'::jsonb,
    color_palette JSONB DEFAULT '[]'::jsonb,
    formality_range JSONB DEFAULT '{"min": 2, "max": 5}'::jsonb,
    quality_score FLOAT DEFAULT 0.5,
    brand_popularity FLOAT DEFAULT 0.5,
    network_compatibility_cache JSONB DEFAULT '{}'::jsonb,
    last_computed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- 2. PRODUCT DNA — Rich machine-readable product attributes
-- =====================================================
CREATE TABLE IF NOT EXISTS product_dna (
    product_id UUID PRIMARY KEY REFERENCES brand_products(id) ON DELETE CASCADE,
    category TEXT DEFAULT '',
    subcategory TEXT DEFAULT '',
    gender TEXT DEFAULT 'unisex',
    color_primary TEXT DEFAULT '',
    color_secondary TEXT DEFAULT '',
    material TEXT DEFAULT '',
    fit TEXT DEFAULT 'regular',
    silhouette TEXT DEFAULT 'regular',
    pattern TEXT DEFAULT 'solid',
    occasion JSONB DEFAULT '["casual"]'::jsonb,
    formality INT DEFAULT 3,
    style_tags JSONB DEFAULT '[]'::jsonb,
    season TEXT DEFAULT 'all_season',
    quality_signals JSONB DEFAULT '{"reviews_avg": 0, "return_rate": 0}'::jsonb,
    vton_ready BOOLEAN DEFAULT TRUE,
    embedding_vector vector(1536),
    embedding JSONB,
    last_analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- 3. HOST CATEGORY RULES — What external categories a host allows
-- =====================================================
CREATE TABLE IF NOT EXISTS host_category_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    allow_external BOOLEAN DEFAULT TRUE,
    preferred_positionings JSONB DEFAULT '[]'::jsonb,
    price_range_min NUMERIC(12,2) DEFAULT 0,
    price_range_max NUMERIC(12,2) DEFAULT 999999,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(brand_id, category)
);

-- =====================================================
-- 4. HOST PREFERENCES — Global host settings
-- =====================================================
CREATE TABLE IF NOT EXISTS host_preferences (
    brand_id UUID PRIMARY KEY REFERENCES brands(id) ON DELETE CASCADE,
    network_mode TEXT DEFAULT 'curated_network',
    cross_brand_density TEXT DEFAULT 'balanced',
    allowed_positionings JSONB DEFAULT '["value", "mid", "premium", "luxury"]'::jsonb,
    competitor_policy TEXT DEFAULT 'never_show',
    excluded_brand_ids UUID[] DEFAULT '{}',
    competitor_brand_ids UUID[] DEFAULT '{}',
    price_tolerance_pct FLOAT DEFAULT 0.50,
    show_network_badge BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- 5. BRAND EXCLUSIONS — Explicit brand-to-brand blocks
-- =====================================================
CREATE TABLE IF NOT EXISTS brand_exclusions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    excluded_brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    reason TEXT DEFAULT 'competitor',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(brand_id, excluded_brand_id)
);

-- =====================================================
-- 6. BRAND PAIR COMPATIBILITY — Precomputed pair scores
-- =====================================================
CREATE TABLE IF NOT EXISTS brand_pair_compatibility (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_a_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    brand_b_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    style_compatibility FLOAT DEFAULT 0.5,
    price_compatibility FLOAT DEFAULT 0.5,
    audience_compatibility FLOAT DEFAULT 0.5,
    category_complement FLOAT DEFAULT 0.5,
    occasion_compatibility FLOAT DEFAULT 0.5,
    total_score FLOAT DEFAULT 0.5,
    tier TEXT DEFAULT 'compatible',
    historical_conversions INT DEFAULT 0,
    historical_ctr FLOAT DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(brand_a_id, brand_b_id)
);

-- =====================================================
-- 7. SPONSORED CAMPAIGNS — Brand promotion campaigns
-- =====================================================
CREATE TABLE IF NOT EXISTS sponsored_campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    budget NUMERIC(12,2) NOT NULL,
    spent NUMERIC(12,2) DEFAULT 0,
    target_brand_ids UUID[] DEFAULT '{}',
    target_categories TEXT[] DEFAULT '{}',
    target_occasions TEXT[] DEFAULT '{}',
    target_price_min NUMERIC(12,2) DEFAULT 0,
    target_price_max NUMERIC(12,2) DEFAULT 999999,
    objective TEXT DEFAULT 'vton_impressions',
    boost_pct FLOAT DEFAULT 0.10,
    status TEXT DEFAULT 'active',
    impressions INT DEFAULT 0,
    vton_appearances INT DEFAULT 0,
    clicks INT DEFAULT 0,
    purchases INT DEFAULT 0,
    attributed_gmv NUMERIC(12,2) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- =====================================================
-- 8. CROSS-BRAND TRANSACTIONS — Revenue sharing ledger
-- =====================================================
CREATE TABLE IF NOT EXISTS cross_brand_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_brand_id UUID NOT NULL REFERENCES brands(id),
    supplier_brand_id UUID NOT NULL REFERENCES brands(id),
    user_id UUID REFERENCES users(id),
    product_id UUID,
    product_title TEXT DEFAULT '',
    order_total NUMERIC(12,2) NOT NULL,
    host_commission_rate FLOAT DEFAULT 0.07,
    host_commission_amount NUMERIC(12,2) DEFAULT 0,
    supplier_cpa_rate FLOAT DEFAULT 0.10,
    supplier_cpa_amount NUMERIC(12,2) DEFAULT 0,
    platform_fee_rate FLOAT DEFAULT 0.03,
    platform_fee_amount NUMERIC(12,2) DEFAULT 0,
    campaign_id UUID REFERENCES sponsored_campaigns(id),
    referral_source TEXT DEFAULT 'widget',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- 9. NETWORK EVENTS — Full funnel tracking
-- =====================================================
CREATE TABLE IF NOT EXISTS network_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    brand_id UUID REFERENCES brands(id),
    user_id UUID REFERENCES users(id),
    product_id UUID,
    session_id UUID,
    host_brand_id UUID REFERENCES brands(id),
    campaign_id UUID REFERENCES sponsored_campaigns(id),
    event_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- INDEXES
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_dna_brand ON brand_dna(brand_id);
CREATE INDEX IF NOT EXISTS idx_product_dna_product ON product_dna(product_id);
CREATE INDEX IF NOT EXISTS idx_product_dna_category ON product_dna(category);
CREATE INDEX IF NOT EXISTS idx_host_rules_brand ON host_category_rules(brand_id);
CREATE INDEX IF NOT EXISTS idx_host_prefs_brand ON host_preferences(brand_id);
CREATE INDEX IF NOT EXISTS idx_exclusions_brand ON brand_exclusions(brand_id);
CREATE INDEX IF NOT EXISTS idx_exclusions_excluded ON brand_exclusions(excluded_brand_id);
CREATE INDEX IF NOT EXISTS idx_pair_compat_a ON brand_pair_compatibility(brand_a_id);
CREATE INDEX IF NOT EXISTS idx_pair_compat_b ON brand_pair_compatibility(brand_b_id);
CREATE INDEX IF NOT EXISTS idx_pair_compat_score ON brand_pair_compatibility(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_campaigns_brand ON sponsored_campaigns(brand_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON sponsored_campaigns(status);
CREATE INDEX IF NOT EXISTS idx_cross_tx_host ON cross_brand_transactions(host_brand_id);
CREATE INDEX IF NOT EXISTS idx_cross_tx_supplier ON cross_brand_transactions(supplier_brand_id);
CREATE INDEX IF NOT EXISTS idx_cross_tx_created ON cross_brand_transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_network_events_type ON network_events(event_type);
CREATE INDEX IF NOT EXISTS idx_network_events_brand ON network_events(brand_id);
CREATE INDEX IF NOT EXISTS idx_network_events_created ON network_events(created_at DESC);

-- Vector indexes for product DNA
CREATE INDEX IF NOT EXISTS idx_product_dna_embedding ON product_dna USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100);

-- =====================================================
-- TRIGGERS
-- =====================================================
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_dna_updated') THEN
        CREATE TRIGGER trg_dna_updated BEFORE UPDATE ON brand_dna
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_product_dna_updated') THEN
        CREATE TRIGGER trg_product_dna_updated BEFORE UPDATE ON product_dna
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_host_rules_updated') THEN
        CREATE TRIGGER trg_host_rules_updated BEFORE UPDATE ON host_category_rules
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_host_prefs_updated') THEN
        CREATE TRIGGER trg_host_prefs_updated BEFORE UPDATE ON host_preferences
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
END $$;

-- Product DNA embedding sync
DROP TRIGGER IF EXISTS trg_sync_product_dna_embedding ON product_dna;
CREATE TRIGGER trg_sync_product_dna_embedding
    BEFORE INSERT OR UPDATE OF embedding ON product_dna
    FOR EACH ROW EXECUTE FUNCTION sync_embedding_vector();

-- =====================================================
-- RPC FUNCTIONS
-- =====================================================

-- Get host preferences with defaults
CREATE OR REPLACE FUNCTION get_host_preferences(p_brand_id UUID)
RETURNS TABLE (
    network_mode TEXT,
    cross_brand_density TEXT,
    allowed_positionings JSONB,
    competitor_policy TEXT,
    excluded_brand_ids UUID[],
    competitor_brand_ids UUID[],
    price_tolerance_pct FLOAT,
    show_network_badge BOOLEAN
)
LANGUAGE sql STABLE
AS $$
    SELECT
        COALESCE(hp.network_mode, 'curated_network'),
        COALESCE(hp.cross_brand_density, 'balanced'),
        COALESCE(hp.allowed_positionings, '["value","mid","premium","luxury"]'::jsonb),
        COALESCE(hp.competitor_policy, 'never_show'),
        COALESCE(hp.excluded_brand_ids, '{}'),
        COALESCE(hp.competitor_brand_ids, '{}'),
        COALESCE(hp.price_tolerance_pct, 0.50),
        COALESCE(hp.show_network_badge, true)
    FROM host_preferences hp
    WHERE hp.brand_id = p_brand_id

    UNION ALL

    SELECT
        'curated_network', 'balanced',
        '["value","mid","premium","luxury"]'::jsonb,
        'never_show', '{}', '{}', 0.50, true
    WHERE NOT EXISTS (SELECT 1 FROM host_preferences WHERE brand_id = p_brand_id);
$$;

-- Get eligible cross-brand products for a host
CREATE OR REPLACE FUNCTION get_eligible_cross_products(
    p_host_brand_id UUID,
    p_category TEXT DEFAULT NULL,
    p_gender TEXT DEFAULT 'unisex',
    p_price_min NUMERIC DEFAULT 0,
    p_price_max NUMERIC DEFAULT 999999,
    p_limit INT DEFAULT 30
)
RETURNS TABLE (
    product_id UUID,
    title TEXT,
    price NUMERIC,
    currency TEXT,
    image_url TEXT,
    category TEXT,
    brand TEXT,
    brand_id UUID,
    color TEXT,
    material TEXT,
    tags JSONB,
    similarity FLOAT4
)
LANGUAGE sql STABLE
AS $$
    SELECT
        bp.id, bp.title, bp.price, bp.currency, bp.image_url,
        bp.category, bp.brand, bc.brand_id,
        bp.color, bp.material, bp.tags,
        0.0 as similarity
    FROM brand_products bp
    JOIN brand_catalogs bc ON bp.catalog_id = bc.id
    WHERE bc.brand_id != p_host_brand_id
      AND bp.is_active = true
      AND (p_category IS NULL OR p_category = '' OR bp.category ILIKE '%' || p_category || '%')
      AND bp.price >= p_price_min
      AND bp.price <= p_price_max
      AND (p_gender = 'unisex' OR bp.gender = 'unisex' OR bp.gender = p_gender)
      AND bc.brand_id NOT IN (
          SELECT excluded_brand_id FROM brand_exclusions WHERE brand_id = p_host_brand_id
      )
    ORDER BY bp.created_at DESC
    LIMIT p_limit;
$$;

-- Record a network event
CREATE OR REPLACE FUNCTION record_network_event(
    p_event_type TEXT,
    p_brand_id UUID,
    p_user_id UUID,
    p_product_id UUID,
    p_session_id UUID DEFAULT NULL,
    p_host_brand_id UUID DEFAULT NULL,
    p_campaign_id UUID DEFAULT NULL,
    p_event_data JSONB DEFAULT '{}'::jsonb
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO network_events (event_type, brand_id, user_id, product_id, session_id, host_brand_id, campaign_id, event_data)
    VALUES (p_event_type, p_brand_id, p_user_id, p_product_id, p_session_id, p_host_brand_id, p_campaign_id, p_event_data);
END;
$$ LANGUAGE plpgsql;

-- Get brand pair compatibility
CREATE OR REPLACE FUNCTION get_brand_pair_compatibility(
    p_brand_a UUID,
    p_brand_b UUID
)
RETURNS TABLE (
    total_score FLOAT,
    tier TEXT,
    style_compat FLOAT,
    price_compat FLOAT,
    audience_compat FLOAT,
    category_complement FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        bpc.total_score, bpc.tier,
        bpc.style_compatibility, bpc.price_compatibility,
        bpc.audience_compatibility, bpc.category_complement
    FROM brand_pair_compatibility bpc
    WHERE (bpc.brand_a_id = p_brand_a AND bpc.brand_b_id = p_brand_b)
       OR (bpc.brand_a_id = p_brand_b AND bpc.brand_b_id = p_brand_a);
$$;

-- =====================================================
-- VIEWS
-- =====================================================
CREATE OR REPLACE VIEW v_network_dashboard AS
SELECT
    b.id AS brand_id,
    b.name AS brand_name,
    b.slug,
    hp.network_mode,
    hp.cross_brand_density,
    (SELECT COUNT(*) FROM brand_products bp
     JOIN brand_catalogs bc ON bp.catalog_id = bc.id
     WHERE bc.brand_id = b.id AND bp.is_active = true) AS product_count,
    (SELECT COUNT(*) FROM cross_brand_transactions cbt
     WHERE cbt.supplier_brand_id = b.id) AS cross_sales_as_supplier,
    (SELECT COALESCE(SUM(cbt.supplier_cpa_amount), 0) FROM cross_brand_transactions cbt
     WHERE cbt.supplier_brand_id = b.id) AS revenue_as_supplier,
    (SELECT COUNT(*) FROM cross_brand_transactions cbt
     WHERE cbt.host_brand_id = b.id) AS cross_sales_as_host,
    (SELECT COALESCE(SUM(cbt.host_commission_amount), 0) FROM cross_brand_transactions cbt
     WHERE cbt.host_brand_id = b.id) AS commission_as_host,
    (SELECT COUNT(*) FROM sponsored_campaigns sc
     WHERE sc.brand_id = b.id AND sc.status = 'active') AS active_campaigns,
    b.created_at
FROM brands b
LEFT JOIN host_preferences hp ON b.id = hp.brand_id
WHERE b.is_active = true;

-- =====================================================
-- DONE
-- =====================================================
SELECT 'Narrative Commerce Network schema created successfully! 9 new tables ready.' AS status;
