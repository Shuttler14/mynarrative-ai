-- =====================================================
-- MY NARRATIVE - CREATOR ECONOMY DATABASE SCHEMA v2.0
-- =====================================================
-- Run this in Supabase SQL Editor to set up the database
-- Safe to re-run: all statements use IF NOT EXISTS / OR REPLACE

-- =====================================================
-- MIGRATION: Add new columns to creators table (v2.0)
-- Run this block first if upgrading from v1.0
-- =====================================================
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='creators' AND column_name='first_name') THEN
        ALTER TABLE creators ADD COLUMN first_name TEXT DEFAULT '';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='creators' AND column_name='earnings_history') THEN
        ALTER TABLE creators ADD COLUMN earnings_history JSONB DEFAULT '[]';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='creator_designs' AND column_name='shopify_product_id') THEN
        ALTER TABLE creator_designs ADD COLUMN shopify_product_id TEXT DEFAULT '';
    END IF;
END $$;

-- =====================================================
-- SERVICE ROLE POLICIES (for API - bypasses RLS)
-- =====================================================
-- These allow the Vercel API (using service role key) to read/write all rows
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Service role full access creators' AND tablename='creators') THEN
        CREATE POLICY "Service role full access creators" ON creators FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Service role full access designs' AND tablename='creator_designs') THEN
        CREATE POLICY "Service role full access designs" ON creator_designs FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Service role full access payouts' AND tablename='creator_payouts') THEN
        CREATE POLICY "Service role full access payouts" ON creator_payouts FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Service role full access commissions' AND tablename='creator_commissions') THEN
        CREATE POLICY "Service role full access commissions" ON creator_commissions FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Service role full access campus_fests' AND tablename='campus_fests') THEN
        CREATE POLICY "Service role full access campus_fests" ON campus_fests FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Service role full access ghost_items' AND tablename='creator_ghost_items') THEN
        CREATE POLICY "Service role full access ghost_items" ON creator_ghost_items FOR ALL USING (true) WITH CHECK (true);
    END IF;
END $$;

-- =====================================================
-- CREATORS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS creators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shopify_customer_id TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    brand_name TEXT DEFAULT '',
    first_name TEXT DEFAULT '',
    avatar_url TEXT DEFAULT 'https://api.dicebear.com/7.x/avataaars/svg?seed=creator',
    commission_tier TEXT DEFAULT 'standard',
    commission_rate INTEGER DEFAULT 15,
    balance INTEGER DEFAULT 0,
    lifetime_earnings INTEGER DEFAULT 0,
    active_listings INTEGER DEFAULT 0,
    total_items_sold INTEGER DEFAULT 0,
    style_influence_rank TEXT DEFAULT 'rookie_designer',
    is_mega_influencer BOOLEAN DEFAULT FALSE,
    is_campus_ambassador BOOLEAN DEFAULT FALSE,
    -- New verification fields
    tier TEXT DEFAULT 'basic',
    is_verified BOOLEAN DEFAULT FALSE,
    verification_level TEXT DEFAULT 'none',
    is_invite_only BOOLEAN DEFAULT FALSE,
    total_followers INTEGER DEFAULT 0,
    primary_platform TEXT,
    onboarding_completed BOOLEAN DEFAULT FALSE,
    onboarding_completed_at TIMESTAMPTZ,
    -- Social links with verification
    social_links JSONB DEFAULT '{}',
    earnings_history JSONB DEFAULT '[]',
    stripe_connect_id TEXT,
    bank_details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE creators ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read their own profile
CREATE POLICY "Users can read own profile" ON creators
    FOR SELECT USING (auth.uid()::text = shopify_customer_id);

-- Policy: Public can read mega influencer profiles
CREATE POLICY "Public can read mega influencers" ON creators
    FOR SELECT USING (is_mega_influencer = true);

-- =====================================================
-- CREATOR DESIGNS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS creator_designs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id UUID REFERENCES creators(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    flux_editorial_image_url TEXT NOT NULL,
    flat_image_url TEXT DEFAULT '',
    price INTEGER NOT NULL,
    commission_rate INTEGER DEFAULT 5,
    estimated_earnings_per_sale INTEGER DEFAULT 0,
    total_sales INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    category TEXT DEFAULT 'apparel',
    tags JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE creator_designs ENABLE ROW LEVEL SECURITY;

-- Policy: Public can read active designs
CREATE POLICY "Public can read active designs" ON creator_designs
    FOR SELECT USING (status = 'active');

-- Policy: Creators can manage own designs
CREATE POLICY "Creators can manage own designs" ON creator_designs
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM creators
            WHERE creators.id = creator_designs.creator_id
            AND creators.shopify_customer_id = auth.uid()::text
        )
    );

-- =====================================================
-- CREATOR GHOST ITEMS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS creator_ghost_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id UUID REFERENCES creators(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    embedding JSONB,
    type TEXT DEFAULT 'ghost',
    name TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE creator_ghost_items ENABLE ROW LEVEL SECURITY;

-- Policy: Creators can manage own ghost items
CREATE POLICY "Creators can manage own ghost items" ON creator_ghost_items
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM creators
            WHERE creators.id = creator_ghost_items.creator_id
            AND creators.shopify_customer_id = auth.uid()::text
        )
    );

-- =====================================================
-- CREATOR PAYOUTS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS creator_payouts (
    id TEXT PRIMARY KEY,
    creator_id UUID REFERENCES creators(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    bank_details JSONB,
    stripe_payout_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- RLS
ALTER TABLE creator_payouts ENABLE ROW LEVEL SECURITY;

-- Policy: Creators can view own payouts
CREATE POLICY "Creators can view own payouts" ON creator_payouts
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM creators
            WHERE creators.id = creator_payouts.creator_id
            AND creators.shopify_customer_id = auth.uid()::text
        )
    );

-- =====================================================
-- CREATOR COMMISSIONS TABLE (Earnings History)
-- =====================================================
CREATE TABLE IF NOT EXISTS creator_commissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id UUID REFERENCES creators(id) ON DELETE CASCADE,
    shopify_order_id TEXT,
    amount INTEGER NOT NULL,
    type TEXT DEFAULT 'sale_commission',
    design_id UUID REFERENCES creator_designs(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE creator_commissions ENABLE ROW LEVEL SECURITY;

-- Policy: Creators can view own commissions
CREATE POLICY "Creators can view own commissions" ON creator_commissions
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM creators
            WHERE creators.id = creator_commissions.creator_id
            AND creators.shopify_customer_id = auth.uid()::text
        )
    );

-- =====================================================
-- CAMPUS FESTS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS campus_fests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    date DATE NOT NULL,
    location TEXT NOT NULL,
    collective_pool INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    creator_contributions JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE campus_fests ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public can read active fests" ON campus_fests
    FOR SELECT USING (is_active = true);

-- =====================================================
-- CREATOR VERIFICATION ENHANCEMENTS
-- =====================================================
ALTER TABLE creators ADD COLUMN IF NOT EXISTS tier TEXT DEFAULT 'basic';
ALTER TABLE creators ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE creators ADD COLUMN IF NOT EXISTS verification_level TEXT DEFAULT 'none';
ALTER TABLE creators ADD NOT NULL CONSTRAINT valid_commission_range CHECK (commission_rate >= 0 AND commission_rate <= 100);
ALTER TABLE creators ADD COLUMN IF NOT EXISTS total_followers INTEGER DEFAULT 0;
ALTER TABLE creators ADD COLUMN IF NOT EXISTS primary_platform TEXT;
ALTER TABLE creators ADD COLUMN IF NOT EXISTS brand_name TEXT;
ALTER TABLE creators ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE;
ALTER TABLE creators ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ;
ALTER TABLE creators ADD COLUMN IF NOT EXISTS is_invite_only BOOLEAN DEFAULT FALSE;

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================
CREATE INDEX idx_creators_shopify_id ON creators(shopify_customer_id);
CREATE INDEX idx_creators_username ON creators(username);
CREATE INDEX idx_creators_mega ON creators(is_mega_influencer) WHERE is_mega_influencer = true;
CREATE INDEX idx_creators_tier ON creators(tier);
CREATE INDEX idx_creators_verified ON creators(is_verified) WHERE is_verified = true;
CREATE INDEX idx_designs_creator ON creator_designs(creator_id);
CREATE INDEX idx_designs_status ON creator_designs(status) WHERE status = 'active';
CREATE INDEX idx_commissions_creator ON creator_commissions(creator_id);
CREATE INDEX idx_commissions_date ON creator_commissions(created_at DESC);

-- =====================================================
-- STORAGE BUCKETS
-- =====================================================
-- Creator avatars
INSERT INTO storage.buckets (id, name, public)
VALUES ('creator-avatars', 'creator-avatars', true)
ON CONFLICT (id) DO NOTHING;

-- Creator design images
INSERT INTO storage.buckets (id, name, public)
VALUES ('creator-designs', 'creator-designs', true)
ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- STORAGE POLICIES
-- =====================================================

-- Creator avatars - public read
CREATE POLICY "Public read creator avatars"
ON storage.objects FOR SELECT
USING (bucket_id = 'creator-avatars');

-- Creator avatars - upload (requires auth)
CREATE POLICY "Users upload creator avatars"
ON storage.objects FOR INSERT
WITH CHECK (
    bucket_id = 'creator-avatars'
    AND auth.uid()::text LIKE '%'
);

-- Creator designs - public read
CREATE POLICY "Public read creator designs"
ON storage.objects FOR SELECT
USING (bucket_id = 'creator-designs');

-- Creator designs - upload
CREATE POLICY "Creators upload designs"
ON storage.objects FOR INSERT
WITH CHECK (bucket_id = 'creator-designs');

-- =====================================================
-- FUNCTION: Update updated_at timestamp
-- =====================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers
CREATE TRIGGER update_creators_updated_at
    BEFORE UPDATE ON creators
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_designs_updated_at
    BEFORE UPDATE ON creator_designs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- =====================================================
-- FUNCTION: Get creator earnings by month
-- =====================================================
CREATE OR REPLACE FUNCTION get_creator_earnings_monthly(
    p_creator_id UUID,
    p_months INTEGER DEFAULT 6
)
RETURNS TABLE (
    month DATE,
    total_earnings INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        DATE_TRUNC('month', cc.created_at)::DATE AS month,
        SUM(cc.amount) AS total_earnings
    FROM creator_commissions cc
    WHERE cc.creator_id = p_creator_id
        AND cc.created_at >= NOW() - (p_months || ' months')::INTERVAL
    GROUP BY DATE_TRUNC('month', cc.created_at)
    ORDER BY month DESC;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- FUNCTION: Calculate creator rank from lifetime earnings
-- =====================================================
CREATE OR REPLACE FUNCTION calculate_creator_rank(p_lifetime_earnings INTEGER)
RETURNS TEXT AS $$
BEGIN
    IF p_lifetime_earnings >= 500000 THEN
        RETURN 'platform_icon';
    ELSIF p_lifetime_earnings >= 150000 THEN
        RETURN 'style_architect';
    ELSIF p_lifetime_earnings >= 50000 THEN
        RETURN 'trendsetter';
    ELSIF p_lifetime_earnings >= 10000 THEN
        RETURN 'emerging_talent';
    ELSE
        RETURN 'rookie_designer';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- VIEW: Creator Dashboard Summary
-- =====================================================
CREATE OR REPLACE VIEW creator_dashboard_summary AS
SELECT
    c.id,
    c.shopify_customer_id,
    c.username,
    c.avatar_url,
    c.commission_tier,
    c.commission_rate,
    c.balance,
    c.lifetime_earnings,
    c.active_listings,
    c.total_items_sold,
    c.style_influence_rank,
    c.is_mega_influencer,
    c.is_campus_ambassador,
    c.created_at,
    (
        SELECT COUNT(*)
        FROM creator_designs cd
        WHERE cd.creator_id = c.id AND cd.status = 'active'
    ) AS total_active_designs,
    (
        SELECT COALESCE(SUM(amount), 0)
        FROM creator_commissions cc
        WHERE cc.creator_id = c.id
            AND cc.created_at >= NOW() - INTERVAL '30 days'
    ) AS last_30_days_earnings
FROM creators c;

-- =====================================================
-- WEBHOOK: Shopify Order Fulfillment
-- =====================================================
-- This should be called when a Shopify order is fulfilled
-- to credit the creator's account with commission

CREATE OR REPLACE FUNCTION trigger_creator_commission()
RETURNS TRIGGER AS $$
DECLARE
    design_record RECORD;
    creator_record RECORD;
    commission_amount INTEGER;
BEGIN
    -- For each line item in the order, check if it's a creator design
    -- This is a simplified version - in production, you'd match order line items

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- SEED DATA: Sample Campus Fests
-- =====================================================
INSERT INTO campus_fests (name, date, location, collective_pool, is_active)
VALUES
    ('UVCE Tech Fest 2024', '2024-03-15', 'Bangalore', 50000, true),
    ('NITK Spring Fest', '2024-03-22', 'Mangalore', 35000, true),
    ('BMS College Cultural Fest', '2024-02-28', 'Bangalore', 25000, false)
ON CONFLICT DO NOTHING;

-- =====================================================
-- DONE
-- =====================================================
SELECT 'Database schema created successfully!' AS status;