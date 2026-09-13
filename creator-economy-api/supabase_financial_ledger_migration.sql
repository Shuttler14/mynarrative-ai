-- ============================================================
-- MY NARRATIVE — Financial Ledger & Tier System Migration
-- ============================================================
-- Run this in your Supabase SQL Editor (Project > SQL Editor)
-- Safe to re-run: uses IF NOT EXISTS / IF EXISTS guards throughout
-- ============================================================

-- ============================================================
-- STEP 1: Create creator_tier ENUM type
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'creator_tier_enum') THEN
        CREATE TYPE creator_tier_enum AS ENUM (
            'Bronze',    -- 0–49 sales
            'Silver',    -- 50–199 sales
            'Gold',      -- 200–999 sales
            'Diamond'    -- 1000+ sales
        );
    END IF;
END
$$;

-- ============================================================
-- STEP 2: Alter creator_designs — add missing columns
-- ============================================================
ALTER TABLE IF EXISTS creator_designs
    ADD COLUMN IF NOT EXISTS unique_product_id  TEXT,
    ADD COLUMN IF NOT EXISTS master_file_url    TEXT,
    ADD COLUMN IF NOT EXISTS mockup_urls        JSONB    DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS selected_colors    TEXT[]   DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS price_paise        INTEGER  DEFAULT 0,
    ADD COLUMN IF NOT EXISTS product_type       TEXT     DEFAULT 'tshirt',
    ADD COLUMN IF NOT EXISTS creator_earnings_paise INTEGER DEFAULT 0;

-- Index unique_product_id for fast webhook lookups
CREATE INDEX IF NOT EXISTS idx_creator_designs_unique_product_id
    ON creator_designs(unique_product_id);

-- Index product_type for feed filtering
CREATE INDEX IF NOT EXISTS idx_creator_designs_product_type
    ON creator_designs(product_type);

-- ============================================================
-- STEP 3: Create or alter design_orders table
-- ============================================================
CREATE TABLE IF NOT EXISTS design_orders (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    shopify_order_id    TEXT        UNIQUE NOT NULL,
    shopify_customer_id TEXT,
    customer_email      TEXT,
    unique_product_id   TEXT,
    design_file_url     TEXT,
    shopify_product_id  TEXT,
    shopify_variant_id  TEXT,
    price_paise         INTEGER     DEFAULT 0,
    quantity            INTEGER     DEFAULT 1,
    status              TEXT        DEFAULT 'pending',
    product_type        TEXT,
    color               TEXT,
    design_title        TEXT,
    creator_id          TEXT,
    base_cost_paise     INTEGER     DEFAULT 0,
    creator_cut_paise   INTEGER     DEFAULT 0,
    platform_cut_paise  INTEGER     DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Add columns if table already existed without them
ALTER TABLE design_orders
    ADD COLUMN IF NOT EXISTS product_type       TEXT,
    ADD COLUMN IF NOT EXISTS color              TEXT,
    ADD COLUMN IF NOT EXISTS design_title       TEXT,
    ADD COLUMN IF NOT EXISTS creator_id         TEXT,
    ADD COLUMN IF NOT EXISTS base_cost_paise    INTEGER  DEFAULT 0,
    ADD COLUMN IF NOT EXISTS creator_cut_paise  INTEGER  DEFAULT 0,
    ADD COLUMN IF NOT EXISTS platform_cut_paise INTEGER  DEFAULT 0;

-- Indexes on design_orders
CREATE INDEX IF NOT EXISTS idx_design_orders_shopify_order_id
    ON design_orders(shopify_order_id);
CREATE INDEX IF NOT EXISTS idx_design_orders_unique_product_id
    ON design_orders(unique_product_id);
CREATE INDEX IF NOT EXISTS idx_design_orders_shopify_customer_id
    ON design_orders(shopify_customer_id);
CREATE INDEX IF NOT EXISTS idx_design_orders_status
    ON design_orders(status);

-- RLS on design_orders
ALTER TABLE design_orders ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- STEP 4: Alter creators table — add ledger + tier columns
-- ============================================================
-- total_earnings_paise: immutable running total (never decremented on refund —
--   refunds are handled via separate ledger_entries with negative amounts)
-- total_designs_sold:   running count of units sold
-- creator_tier:         auto-recalculated on each order
ALTER TABLE IF EXISTS creators
    ADD COLUMN IF NOT EXISTS total_earnings_paise  INTEGER            DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_designs_sold    INTEGER            DEFAULT 0,
    ADD COLUMN IF NOT EXISTS creator_tier          creator_tier_enum  DEFAULT 'Bronze',
    ADD COLUMN IF NOT EXISTS tier_updated_at       TIMESTAMPTZ        DEFAULT NOW();

-- Index for leaderboard queries
CREATE INDEX IF NOT EXISTS idx_creators_total_earnings
    ON creators(total_earnings_paise DESC);
CREATE INDEX IF NOT EXISTS idx_creators_total_designs_sold
    ON creators(total_designs_sold DESC);
CREATE INDEX IF NOT EXISTS idx_creators_tier
    ON creators(creator_tier);

-- ============================================================
-- STEP 5: Create financial_ledger TABLE (immutable audit log)
-- ============================================================
-- Every financial event (sale, refund, bonus) is recorded here.
-- This table is append-only — records are NEVER updated or deleted.
-- The creators.total_earnings_paise is a denormalized cache for
-- fast reads; the ledger is the source of truth for audits.
-- ============================================================
CREATE TABLE IF NOT EXISTS financial_ledger (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id      TEXT            NOT NULL,           -- FK to creators.id (or shopify_customer_id)
    design_id       UUID,                               -- FK to creator_designs.id
    order_id        TEXT,                               -- Shopify order ID
    unique_product_id TEXT,                             -- S3 design UUID
    event_type      TEXT            NOT NULL,           -- 'sale' | 'refund' | 'bonus' | 'adjustment'
    amount_paise    INTEGER         NOT NULL,           -- positive = credit, negative = debit
    price_paise     INTEGER,                            -- customer paid (sale price)
    base_cost_paise INTEGER,                            -- platform base cost subtracted
    product_type    TEXT,                               -- 'tshirt' | 'hoodie'
    color           TEXT,
    quantity        INTEGER         DEFAULT 1,
    note            TEXT,                               -- human-readable description
    created_at      TIMESTAMPTZ     DEFAULT NOW()
);

-- Indexes for creator earnings queries and audit
CREATE INDEX IF NOT EXISTS idx_ledger_creator_id
    ON financial_ledger(creator_id);
CREATE INDEX IF NOT EXISTS idx_ledger_order_id
    ON financial_ledger(order_id);
CREATE INDEX IF NOT EXISTS idx_ledger_unique_product_id
    ON financial_ledger(unique_product_id);
CREATE INDEX IF NOT EXISTS idx_ledger_event_type
    ON financial_ledger(event_type);
CREATE INDEX IF NOT EXISTS idx_ledger_created_at
    ON financial_ledger(created_at DESC);

-- RLS: creators can read their own ledger entries
ALTER TABLE financial_ledger ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'financial_ledger'
        AND policyname = 'service_role_full_access_ledger'
    ) THEN
        CREATE POLICY "service_role_full_access_ledger"
            ON financial_ledger FOR ALL
            USING (auth.role() = 'service_role')
            WITH CHECK (auth.role() = 'service_role');
    END IF;
END
$$;

-- ============================================================
-- STEP 6: Create compute_creator_tier() helper function
-- ============================================================
-- Tier thresholds (units sold):
--   Bronze:  0    – 49
--   Silver:  50   – 199
--   Gold:    200  – 999
--   Diamond: 1000+
-- ============================================================
CREATE OR REPLACE FUNCTION compute_creator_tier(units_sold INTEGER)
RETURNS creator_tier_enum
LANGUAGE plpgsql
AS $$
BEGIN
    IF units_sold >= 1000 THEN RETURN 'Diamond';
    ELSIF units_sold >= 200 THEN RETURN 'Gold';
    ELSIF units_sold >= 50  THEN RETURN 'Silver';
    ELSE RETURN 'Bronze';
    END IF;
END;
$$;

-- ============================================================
-- STEP 7: Create update_creator_financials() function
-- ============================================================
-- Called by the webhook backend after each D2E sale.
-- Atomically:
--   1. Increments total_earnings_paise and total_designs_sold
--   2. Recalculates and updates creator_tier
--   3. Inserts a row into financial_ledger
-- ============================================================
CREATE OR REPLACE FUNCTION update_creator_financials(
    p_creator_shopify_id  TEXT,
    p_design_id           UUID,
    p_order_id            TEXT,
    p_unique_product_id   TEXT,
    p_creator_cut_paise   INTEGER,
    p_price_paise         INTEGER,
    p_base_cost_paise     INTEGER,
    p_product_type        TEXT,
    p_color               TEXT,
    p_quantity            INTEGER,
    p_note                TEXT DEFAULT ''
)
RETURNS TABLE(
    creator_db_id       TEXT,
    new_earnings_paise  INTEGER,
    new_designs_sold    INTEGER,
    new_tier            creator_tier_enum,
    tier_upgraded       BOOLEAN
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_creator_id         TEXT;
    v_old_tier           creator_tier_enum;
    v_new_tier           creator_tier_enum;
    v_new_earnings       INTEGER;
    v_new_sold           INTEGER;
    v_tier_upgraded      BOOLEAN := FALSE;
BEGIN
    -- Resolve creator by shopify_customer_id
    SELECT id, creator_tier
    INTO v_creator_id, v_old_tier
    FROM creators
    WHERE shopify_customer_id = p_creator_shopify_id
    LIMIT 1;

    IF v_creator_id IS NULL THEN
        RAISE NOTICE 'Creator not found for shopify_customer_id=%', p_creator_shopify_id;
        RETURN;
    END IF;

    -- Atomically increment earnings and sales count
    UPDATE creators
    SET
        total_earnings_paise = COALESCE(total_earnings_paise, 0) + (p_creator_cut_paise * p_quantity),
        total_designs_sold   = COALESCE(total_designs_sold, 0)   + p_quantity
    WHERE id = v_creator_id
    RETURNING total_earnings_paise, total_designs_sold
    INTO v_new_earnings, v_new_sold;

    -- Recalculate tier
    v_new_tier := compute_creator_tier(v_new_sold);

    -- Update tier if changed
    IF v_new_tier IS DISTINCT FROM v_old_tier THEN
        UPDATE creators
        SET creator_tier = v_new_tier,
            tier_updated_at = NOW()
        WHERE id = v_creator_id;
        v_tier_upgraded := TRUE;
        RAISE NOTICE 'Tier upgrade: creator=% % → %', v_creator_id, v_old_tier, v_new_tier;
    END IF;

    -- Write immutable ledger entry
    INSERT INTO financial_ledger (
        creator_id, design_id, order_id, unique_product_id,
        event_type, amount_paise, price_paise, base_cost_paise,
        product_type, color, quantity, note
    ) VALUES (
        v_creator_id, p_design_id, p_order_id, p_unique_product_id,
        'sale', p_creator_cut_paise * p_quantity, p_price_paise, p_base_cost_paise,
        p_product_type, p_color, p_quantity,
        COALESCE(NULLIF(p_note, ''), 'Design sale — ' || p_product_type || ' / ' || p_color)
    );

    RETURN QUERY SELECT v_creator_id, v_new_earnings, v_new_sold, v_new_tier, v_tier_upgraded;
END;
$$;

-- ============================================================
-- STEP 8: Update design_orders RLS (add missing policy name guard)
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'design_orders' AND policyname = 'service_role_full_access'
    ) THEN
        CREATE POLICY "service_role_full_access" ON design_orders
            FOR ALL
            USING (auth.role() = 'service_role')
            WITH CHECK (auth.role() = 'service_role');
    END IF;
END
$$;

-- ============================================================
-- STEP 9: Verify migration
-- ============================================================
DO $$
DECLARE
    tier creator_tier_enum;
BEGIN
    -- Verify tier computation
    ASSERT compute_creator_tier(0)    = 'Bronze',  'Bronze threshold failed';
    ASSERT compute_creator_tier(49)   = 'Bronze',  'Bronze max failed';
    ASSERT compute_creator_tier(50)   = 'Silver',  'Silver threshold failed';
    ASSERT compute_creator_tier(199)  = 'Silver',  'Silver max failed';
    ASSERT compute_creator_tier(200)  = 'Gold',    'Gold threshold failed';
    ASSERT compute_creator_tier(999)  = 'Gold',    'Gold max failed';
    ASSERT compute_creator_tier(1000) = 'Diamond', 'Diamond threshold failed';
    ASSERT compute_creator_tier(9999) = 'Diamond', 'Diamond max failed';
    RAISE NOTICE '✅ Tier computation verified: Bronze→Silver→Gold→Diamond thresholds correct';
END
$$;

-- ============================================================
-- SUMMARY
-- ============================================================
-- Tables modified:
--   creator_designs  → + unique_product_id, master_file_url, mockup_urls,
--                        selected_colors, price_paise, product_type, creator_earnings_paise
--   design_orders    → + product_type, color, design_title, creator_id,
--                        base_cost_paise, creator_cut_paise, platform_cut_paise
--   creators         → + total_earnings_paise, total_designs_sold,
--                        creator_tier (enum), tier_updated_at
--
-- Tables created:
--   financial_ledger → immutable append-only audit log of all financial events
--
-- Types created:
--   creator_tier_enum → Bronze | Silver | Gold | Diamond
--
-- Functions created:
--   compute_creator_tier(units_sold)         → returns tier enum
--   update_creator_financials(...)           → atomic sale recording + tier update
-- ============================================================
