-- =====================================================
-- MY NARRATIVE - COMPLETE DATABASE SETUP
-- Run this ONCE in Supabase SQL Editor
-- Safe to re-run: all statements use IF NOT EXISTS
-- =====================================================

-- =====================================================
-- STEP 1: CREATORS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS creators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shopify_customer_id TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    first_name TEXT DEFAULT '',
    avatar_url TEXT DEFAULT 'https://api.dicebear.com/7.x/avataaars/svg?seed=creator',
    commission_tier TEXT DEFAULT 'standard',
    commission_rate INTEGER DEFAULT 5,
    balance INTEGER DEFAULT 0,
    lifetime_earnings INTEGER DEFAULT 0,
    active_listings INTEGER DEFAULT 0,
    total_items_sold INTEGER DEFAULT 0,
    style_influence_rank TEXT DEFAULT 'rookie_designer',
    is_mega_influencer BOOLEAN DEFAULT FALSE,
    is_campus_ambassador BOOLEAN DEFAULT FALSE,
    social_links JSONB DEFAULT '{}',
    earnings_history JSONB DEFAULT '[]',
    stripe_connect_id TEXT,
    bank_details JSONB,
    total_followers INTEGER DEFAULT 0,
    average_rating NUMERIC(3,1) DEFAULT 4.5,
    bio TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE creators ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- STEP 2: CREATOR DESIGNS TABLE
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
    total_likes INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    category TEXT DEFAULT 'tee',
    tags JSONB DEFAULT '[]',
    shopify_product_id TEXT DEFAULT '',
    shopify_product_url TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE creator_designs ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- STEP 3: DESIGN LIKES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS design_likes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    design_id UUID REFERENCES creator_designs(id) ON DELETE CASCADE NOT NULL,
    user_identifier TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(design_id, user_identifier)
);

ALTER TABLE design_likes ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- STEP 4: CREATOR GHOST ITEMS TABLE
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

ALTER TABLE creator_ghost_items ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- STEP 5: CREATOR PAYOUTS TABLE
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

ALTER TABLE creator_payouts ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- STEP 6: CREATOR COMMISSIONS TABLE
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

ALTER TABLE creator_commissions ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- STEP 7: CAMPUS FESTS TABLE
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

ALTER TABLE campus_fests ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- STEP 8: RLS POLICIES (all safe with DO blocks)
-- =====================================================
DO $$ BEGIN
    -- creators
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Service role full access creators' AND tablename='creators') THEN
        CREATE POLICY "Service role full access creators" ON creators FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Users can read own profile' AND tablename='creators') THEN
        CREATE POLICY "Users can read own profile" ON creators FOR SELECT USING (auth.uid()::text = shopify_customer_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Public can read mega influencers' AND tablename='creators') THEN
        CREATE POLICY "Public can read mega influencers" ON creators FOR SELECT USING (is_mega_influencer = true);
    END IF;

    -- creator_designs
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Service role full access designs' AND tablename='creator_designs') THEN
        CREATE POLICY "Service role full access designs" ON creator_designs FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Public can read active designs' AND tablename='creator_designs') THEN
        CREATE POLICY "Public can read active designs" ON creator_designs FOR SELECT USING (status = 'active');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Creators can manage own designs' AND tablename='creator_designs') THEN
        CREATE POLICY "Creators can manage own designs" ON creator_designs FOR ALL USING (
            EXISTS (SELECT 1 FROM creators WHERE creators.id = creator_designs.creator_id AND creators.shopify_customer_id = auth.uid()::text)
        );
    END IF;

    -- design_likes
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='design_likes_allow_insert' AND tablename='design_likes') THEN
        CREATE POLICY "design_likes_allow_insert" ON design_likes FOR INSERT WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='design_likes_allow_read' AND tablename='design_likes') THEN
        CREATE POLICY "design_likes_allow_read" ON design_likes FOR SELECT USING (true);
    END IF;

    -- creator_ghost_items
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Service role full access ghost_items' AND tablename='creator_ghost_items') THEN
        CREATE POLICY "Service role full access ghost_items" ON creator_ghost_items FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Creators can manage own ghost items' AND tablename='creator_ghost_items') THEN
        CREATE POLICY "Creators can manage own ghost items" ON creator_ghost_items FOR ALL USING (
            EXISTS (SELECT 1 FROM creators WHERE creators.id = creator_ghost_items.creator_id AND creators.shopify_customer_id = auth.uid()::text)
        );
    END IF;

    -- creator_payouts
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Service role full access payouts' AND tablename='creator_payouts') THEN
        CREATE POLICY "Service role full access payouts" ON creator_payouts FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Creators can view own payouts' AND tablename='creator_payouts') THEN
        CREATE POLICY "Creators can view own payouts" ON creator_payouts FOR SELECT USING (
            EXISTS (SELECT 1 FROM creators WHERE creators.id = creator_payouts.creator_id AND creators.shopify_customer_id = auth.uid()::text)
        );
    END IF;

    -- creator_commissions
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Service role full access commissions' AND tablename='creator_commissions') THEN
        CREATE POLICY "Service role full access commissions" ON creator_commissions FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Creators can view own commissions' AND tablename='creator_commissions') THEN
        CREATE POLICY "Creators can view own commissions" ON creator_commissions FOR SELECT USING (
            EXISTS (SELECT 1 FROM creators WHERE creators.id = creator_commissions.creator_id AND creators.shopify_customer_id = auth.uid()::text)
        );
    END IF;

    -- campus_fests
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Service role full access campus_fests' AND tablename='campus_fests') THEN
        CREATE POLICY "Service role full access campus_fests" ON campus_fests FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Public can read active fests' AND tablename='campus_fests') THEN
        CREATE POLICY "Public can read active fests" ON campus_fests FOR SELECT USING (is_active = true);
    END IF;
END $$;

-- =====================================================
-- STEP 9: INDEXES (all safe with IF NOT EXISTS)
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_creators_shopify_id ON creators(shopify_customer_id);
CREATE INDEX IF NOT EXISTS idx_creators_username ON creators(username);
CREATE INDEX IF NOT EXISTS idx_creators_mega ON creators(is_mega_influencer) WHERE is_mega_influencer = true;
CREATE INDEX IF NOT EXISTS idx_designs_creator ON creator_designs(creator_id);
CREATE INDEX IF NOT EXISTS idx_designs_status ON creator_designs(status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_designs_likes ON creator_designs(total_likes DESC);
CREATE INDEX IF NOT EXISTS idx_designs_feed ON creator_designs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_design_likes_design ON design_likes(design_id);
CREATE INDEX IF NOT EXISTS idx_commissions_creator ON creator_commissions(creator_id);
CREATE INDEX IF NOT EXISTS idx_commissions_date ON creator_commissions(created_at DESC);

-- =====================================================
-- STEP 10: STORAGE BUCKETS
-- =====================================================
INSERT INTO storage.buckets (id, name, public)
VALUES ('creator-avatars', 'creator-avatars', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO storage.buckets (id, name, public)
VALUES ('creator-designs', 'creator-designs', true)
ON CONFLICT (id) DO NOTHING;

-- Storage policies
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Public read creator avatars') THEN
        CREATE POLICY "Public read creator avatars" ON storage.objects FOR SELECT USING (bucket_id = 'creator-avatars');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Users upload creator avatars') THEN
        CREATE POLICY "Users upload creator avatars" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'creator-avatars' AND auth.uid()::text LIKE '%');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Public read creator designs') THEN
        CREATE POLICY "Public read creator designs" ON storage.objects FOR SELECT USING (bucket_id = 'creator-designs');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='Creators upload designs') THEN
        CREATE POLICY "Creators upload designs" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'creator-designs');
    END IF;
END $$;

-- =====================================================
-- STEP 11: FUNCTIONS & TRIGGERS
-- =====================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_creators_updated_at ON creators;
CREATE TRIGGER update_creators_updated_at
    BEFORE UPDATE ON creators
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_designs_updated_at ON creator_designs;
CREATE TRIGGER update_designs_updated_at
    BEFORE UPDATE ON creator_designs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Rank calculation function
CREATE OR REPLACE FUNCTION calculate_creator_rank(p_lifetime_earnings INTEGER)
RETURNS TEXT AS $$
BEGIN
    IF p_lifetime_earnings >= 500000 THEN RETURN 'platform_icon';
    ELSIF p_lifetime_earnings >= 150000 THEN RETURN 'style_architect';
    ELSIF p_lifetime_earnings >= 50000 THEN RETURN 'trendsetter';
    ELSIF p_lifetime_earnings >= 10000 THEN RETURN 'emerging_talent';
    ELSE RETURN 'rookie_designer';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Monthly earnings function
CREATE OR REPLACE FUNCTION get_creator_earnings_monthly(
    p_creator_id UUID,
    p_months INTEGER DEFAULT 6
)
RETURNS TABLE (month DATE, total_earnings INTEGER) AS $$
BEGIN
    RETURN QUERY
    SELECT
        DATE_TRUNC('month', cc.created_at)::DATE AS month,
        SUM(cc.amount)::INTEGER AS total_earnings
    FROM creator_commissions cc
    WHERE cc.creator_id = p_creator_id
        AND cc.created_at >= NOW() - (p_months || ' months')::INTERVAL
    GROUP BY DATE_TRUNC('month', cc.created_at)
    ORDER BY month DESC;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- STEP 12: VIEWS
-- =====================================================
CREATE OR REPLACE VIEW creator_dashboard_summary AS
SELECT
    c.id, c.shopify_customer_id, c.username, c.avatar_url,
    c.commission_tier, c.commission_rate, c.balance,
    c.lifetime_earnings, c.active_listings, c.total_items_sold,
    c.style_influence_rank, c.is_mega_influencer, c.is_campus_ambassador,
    c.created_at,
    (SELECT COUNT(*) FROM creator_designs cd WHERE cd.creator_id = c.id AND cd.status = 'active') AS total_active_designs,
    (SELECT COALESCE(SUM(amount), 0) FROM creator_commissions cc WHERE cc.creator_id = c.id AND cc.created_at >= NOW() - INTERVAL '30 days') AS last_30_days_earnings
FROM creators c;

CREATE OR REPLACE VIEW public_design_feed AS
SELECT
    cd.id, cd.title, cd.description,
    cd.flux_editorial_image_url AS image_url,
    cd.price, cd.total_sales, cd.total_likes,
    cd.category, cd.tags, cd.created_at,
    cd.shopify_product_id, cd.shopify_product_url,
    c.username AS creator_username,
    c.avatar_url AS creator_avatar,
    c.style_influence_rank AS creator_tier,
    c.bio AS creator_bio
FROM creator_designs cd
JOIN creators c ON c.id = cd.creator_id
WHERE cd.status = 'active'
ORDER BY cd.created_at DESC;

-- =====================================================
-- STEP 13: SEED DATA
-- =====================================================
INSERT INTO campus_fests (name, date, location, collective_pool, is_active)
VALUES
    ('UVCE Tech Fest 2024', '2024-03-15', 'Bangalore', 50000, true),
    ('NITK Spring Fest', '2024-03-22', 'Mangalore', 35000, true),
    ('BMS College Cultural Fest', '2024-02-28', 'Bangalore', 25000, false)
ON CONFLICT DO NOTHING;

-- =====================================================
-- DONE ✅
-- =====================================================
SELECT 'My Narrative database setup complete! All tables, policies, indexes, and views created.' AS status;
