-- =====================================================
-- CROSS-BRAND SYNDICATE SYSTEM
-- Enables brands to show complementary products from
-- partner brands, creating a distributed affiliate network.
-- =====================================================

-- =====================================================
-- BRAND SYNDICATE RULES (what each brand allows)
-- =====================================================
CREATE TABLE IF NOT EXISTS brand_syndicate_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    
    -- What this brand ALLOWS from partners
    allowed_categories TEXT[] DEFAULT '{}',           -- e.g. {'bottom', 'footwear', 'accessory'}
    blocked_categories TEXT[] DEFAULT '{}',           -- e.g. {'top'} - never show competing tops
    
    -- Price tier constraints
    min_partner_price NUMERIC(12,2) DEFAULT 0,
    max_partner_price NUMERIC(12,2) DEFAULT 999999,
    
    -- Brand tier matching
    allowed_tiers TEXT[] DEFAULT '{}',               -- e.g. {'premium', 'luxury'} - only partner with similar tier
    
    -- Manual brand approvals (empty = auto-approve all matching)
    approved_partner_brand_ids UUID[] DEFAULT '{}',  -- whitelist specific brands
    blocked_partner_brand_ids UUID[] DEFAULT '{}',   -- blacklist specific brands
    
    -- Revenue settings
    affiliate_commission_rate NUMERIC(5,4) DEFAULT 0.0700,  -- 7% host commission
    cpa_rate NUMERIC(5,4) DEFAULT 0.1000,                   -- 10% guest CPA
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(brand_id)
);

ALTER TABLE brand_syndicate_rules ENABLE ROW LEVEL SECURITY;
CREATE INDEX idx_syndicate_rules_brand ON brand_syndicate_rules(brand_id);

-- =====================================================
-- BRAND SYNDICATE PAIRINGS (approved partnerships)
-- =====================================================
CREATE TABLE IF NOT EXISTS brand_syndicate_pairings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,   -- Brand whose site hosts the widget
    guest_brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,  -- Brand whose products are shown
    
    -- Pairing status
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected, suspended
    
    -- Commission settings (override global if set)
    host_commission_rate NUMERIC(5,4),   -- Override host's default
    guest_cpa_rate NUMERIC(5,4),         -- Override guest's default
    
    -- Performance tracking
    total_clicks INTEGER DEFAULT 0,
    total_conversions INTEGER DEFAULT 0,
    total_revenue_generated NUMERIC(12,2) DEFAULT 0,
    total_commissions_earned NUMERIC(12,2) DEFAULT 0,
    
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(host_brand_id, guest_brand_id)
);

ALTER TABLE brand_syndicate_pairings ENABLE ROW LEVEL SECURITY;
CREATE INDEX idx_syndicate_pairings_host ON brand_syndicate_pairings(host_brand_id);
CREATE INDEX idx_syndicate_pairings_guest ON brand_syndicate_pairings(guest_brand_id);
CREATE INDEX idx_syndicate_pairings_status ON brand_syndicate_pairings(status);

-- =====================================================
-- AFFILIATE TRANSACTIONS (revenue tracking)
-- =====================================================
CREATE TABLE IF NOT EXISTS affiliate_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Transaction details
    host_brand_id UUID NOT NULL REFERENCES brands(id),        -- Brand whose site the click came from
    guest_brand_id UUID NOT NULL REFERENCES brands(id),       -- Brand whose product was purchased
    user_id UUID REFERENCES users(id),                         -- The customer
    
    -- Order details
    order_id TEXT,                                              -- External order ID from guest brand
    order_total NUMERIC(12,2) NOT NULL,
    currency TEXT DEFAULT 'INR',
    
    -- Product details
    product_id UUID,                                            -- FK to brand_products
    product_title TEXT,
    product_sku TEXT,
    product_price NUMERIC(12,2),
    quantity INTEGER DEFAULT 1,
    
    -- Commission breakdown
    host_commission_rate NUMERIC(5,4),                          -- e.g. 0.0700 = 7%
    host_commission_amount NUMERIC(12,2),
    guest_cpa_rate NUMERIC(5,4),                                -- e.g. 0.1000 = 10%
    guest_cpa_amount NUMERIC(12,2),
    platform_fee_rate NUMERIC(5,4) DEFAULT 0.0300,             -- 3% platform fee
    platform_fee_amount NUMERIC(12,2),
    
    -- Attribution
    widget_session_id UUID,                                     -- Which widget session drove this
    referral_source TEXT DEFAULT 'widget',                      -- widget, closet, recommendation
    
    -- Payment status
    host_commission_status TEXT DEFAULT 'pending',              -- pending, paid, failed
    guest_cpa_status TEXT DEFAULT 'pending',                    -- pending, paid, failed
    platform_fee_status TEXT DEFAULT 'pending',                 -- pending, paid, failed
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    paid_at TIMESTAMPTZ
);

ALTER TABLE affiliate_transactions ENABLE ROW LEVEL SECURITY;
CREATE INDEX idx_affiliate_tx_host ON affiliate_transactions(host_brand_id);
CREATE INDEX idx_affiliate_tx_guest ON affiliate_transactions(guest_brand_id);
CREATE INDEX idx_affiliate_tx_created ON affiliate_transactions(created_at DESC);
CREATE INDEX idx_affiliate_tx_status ON affiliate_transactions(host_commission_status, guest_cpa_status);

-- =====================================================
-- AFFILIATE PAYOUTS (payment history)
-- =====================================================
CREATE TABLE IF NOT EXISTS affiliate_payouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id),
    
    -- Payout details
    payout_type TEXT NOT NULL,               -- 'host_commission', 'guest_cpa', 'platform_fee'
    amount NUMERIC(12,2) NOT NULL,
    currency TEXT DEFAULT 'INR',
    transaction_count INTEGER DEFAULT 0,
    
    -- Period
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    
    -- Payment
    payment_method TEXT,                     -- stripe, razorpay, bank_transfer
    payment_reference TEXT,                  -- Transaction ID
    
    status TEXT DEFAULT 'pending',           -- pending, processing, completed, failed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

ALTER TABLE affiliate_payouts ENABLE ROW LEVEL SECURITY;
CREATE INDEX idx_payouts_brand ON affiliate_payouts(brand_id);

-- =====================================================
-- CART HANDOFFS (cross-brand checkout tracking)
-- =====================================================
CREATE TABLE IF NOT EXISTS cart_handoffs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source
    host_brand_id UUID NOT NULL REFERENCES brands(id),
    widget_session_id UUID,
    user_id UUID REFERENCES users(id),
    
    -- Target
    guest_brand_id UUID NOT NULL REFERENCES brands(id),
    target_checkout_url TEXT NOT NULL,
    
    -- Product data passed
    product_sku TEXT,
    product_id TEXT,                        -- Guest brand's product ID
    selected_size TEXT,
    selected_color TEXT,
    quantity INTEGER DEFAULT 1,
    
    -- Attribution
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,
    
    -- Outcome
    converted BOOLEAN DEFAULT FALSE,
    order_id TEXT,
    order_value NUMERIC(12,2),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    converted_at TIMESTAMPTZ
);

ALTER TABLE cart_handoffs ENABLE ROW LEVEL SECURITY;
CREATE INDEX idx_handoffs_host ON cart_handoffs(host_brand_id);
CREATE INDEX idx_handoffs_guest ON cart_handoffs(guest_brand_id);
CREATE INDEX idx_handoffs_created ON cart_handoffs(created_at DESC);

-- =====================================================
-- BRAND PERFORMANCE METRICS (for dashboard)
-- =====================================================
CREATE OR REPLACE VIEW brand_syndicate_metrics AS
SELECT
    -- As Host
    h.brand_id,
    h.total_clicks AS host_clicks,
    h.total_conversions AS host_conversions,
    h.total_revenue_generated AS host_revenue,
    h.total_commissions_earned AS host_earnings,
    
    -- As Guest
    g.total_clicks AS guest_clicks,
    g.total_conversions AS guest_conversions,
    g.total_revenue_generated AS guest_revenue,
    g.total_commissions_earned AS guest_payouts,
    
    -- Net
    COALESCE(h.total_commissions_earned, 0) - COALESCE(g.total_commissions_earned, 0) AS net_earnings
FROM brand_syndicate_pairings h
JOIN brand_syndicate_pairings g ON h.guest_brand_id = g.host_brand_id AND h.host_brand_id = g.guest_brand_id;

-- =====================================================
-- RPC FUNCTIONS
-- =====================================================

-- Find suitable partner brands for a given brand
CREATE OR REPLACE FUNCTION find_syndicate_partners(
    p_brand_id UUID,
    p_category TEXT DEFAULT NULL,
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    brand_id UUID,
    brand_name TEXT,
    brand_slug TEXT,
    logo_url TEXT,
    product_count BIGINT,
    avg_price NUMERIC,
    match_score FLOAT4
)
LANGUAGE sql STABLE
AS $$
    WITH brand_info AS (
        SELECT b.id, b.name, b.slug, b.logo_url
        FROM brands b
        WHERE b.id != p_brand_id
          AND b.is_active = true
    ),
    product_stats AS (
        SELECT bc.brand_id, COUNT(*) as cnt, AVG(bp.price) as avg_p
        FROM brand_catalogs bc
        JOIN brand_products bp ON bc.id = bp.catalog_id
        WHERE bp.is_active = true
        GROUP BY bc.brand_id
    ),
    rules AS (
        SELECT * FROM brand_syndicate_rules WHERE brand_id = p_brand_id
    )
    SELECT 
        bi.id,
        bi.name,
        bi.slug,
        bi.logo_url,
        COALESCE(ps.cnt, 0) as product_count,
        COALESCE(ps.avg_p, 0) as avg_price,
        CASE 
            WHEN ps.cnt > 0 THEN 0.8::float4
            ELSE 0.3::float4
        END as match_score
    FROM brand_info bi
    LEFT JOIN product_stats ps ON bi.id = ps.brand_id
    LEFT JOIN rules r ON true
    WHERE (r.blocked_partner_brand_ids IS NULL OR bi.id != ALL(r.blocked_partner_brand_ids))
      AND (r.approved_partner_brand_ids IS NULL OR array_length(r.approved_partner_brand_ids, 1) = 0 OR bi.id = ANY(r.approved_partner_brand_ids))
    ORDER BY match_score DESC, product_count DESC
    LIMIT p_limit;
$$;

-- Calculate affiliate commission for a transaction
CREATE OR REPLACE FUNCTION calculate_affiliate_commission(
    p_host_brand_id UUID,
    p_guest_brand_id UUID,
    p_order_total NUMERIC
)
RETURNS TABLE (
    host_commission NUMERIC,
    guest_cpa NUMERIC,
    platform_fee NUMERIC,
    host_rate NUMERIC,
    guest_rate NUMERIC
)
LANGUAGE sql STABLE
AS $$
    WITH host_rule AS (
        SELECT affiliate_commission_rate FROM brand_syndicate_rules WHERE brand_id = p_host_brand_id
    ),
    guest_rule AS (
        SELECT cpa_rate FROM brand_syndicate_rules WHERE brand_id = p_guest_brand_id
    ),
    pairing AS (
        SELECT host_commission_rate, guest_cpa_rate 
        FROM brand_syndicate_pairings 
        WHERE host_brand_id = p_host_brand_id AND guest_brand_id = p_guest_brand_id AND status = 'approved'
    )
    SELECT
        p_order_total * COALESCE(pairing.host_commission_rate, (SELECT affiliate_commission_rate FROM host_rule), 0.07),
        p_order_total * COALESCE(pairing.guest_cpa_rate, (SELECT cpa_rate FROM guest_rule), 0.10),
        p_order_total * 0.03,
        COALESCE(pairing.host_commission_rate, (SELECT affiliate_commission_rate FROM host_rule), 0.07),
        COALESCE(pairing.guest_cpa_rate, (SELECT cpa_rate FROM guest_rule), 0.10)
    FROM (SELECT 1) dummy
    LEFT JOIN pairing ON true;
$$;

-- =====================================================
-- STORAGE BUCKETS
-- =====================================================
INSERT INTO storage.buckets (id, name, public)
VALUES ('brand-logos', 'brand-logos', true)
ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- DONE
-- =====================================================
SELECT 'Cross-Brand Syndicate schema created successfully!' AS status;
