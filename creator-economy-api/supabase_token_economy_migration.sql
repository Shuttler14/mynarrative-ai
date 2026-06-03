-- ============================================================
-- MY NARRATIVE — Token Economy Migration
-- ============================================================
-- Adds ai_credits (Narrative Tokens) to the creators table.
-- Adds high_res_master_url to creator_designs for JIT upscaling.
-- Safe to re-run: uses IF NOT EXISTS / IF EXISTS guards.
-- Run in Supabase SQL Editor (Project > SQL Editor > New query)
-- ============================================================

-- ============================================================
-- STEP 1: Add ai_credits column to creators table
-- ============================================================
-- ai_credits = "Narrative Tokens"
-- Default: 3 (free tier creators start with 3 design generations)
-- Replenishment: +5 on each sale, +10 on sample kit purchase
-- Constraint: cannot go below 0
ALTER TABLE IF EXISTS creators
    ADD COLUMN IF NOT EXISTS ai_credits INTEGER NOT NULL DEFAULT 3
        CONSTRAINT ai_credits_non_negative CHECK (ai_credits >= 0),
    ADD COLUMN IF NOT EXISTS total_credits_earned INTEGER DEFAULT 3,
    ADD COLUMN IF NOT EXISTS total_credits_used   INTEGER DEFAULT 0;

-- ============================================================
-- STEP 2: Add high_res_master_url to creator_designs
-- ============================================================
-- low_res_master_url  = saved immediately during pipeline (512x512 web mockup)
-- high_res_master_url = set by JIT upscaling on first order (4x Replicate)
ALTER TABLE IF EXISTS creator_designs
    ADD COLUMN IF NOT EXISTS high_res_master_url  TEXT,
    ADD COLUMN IF NOT EXISTS upscaling_status     TEXT DEFAULT 'pending'
        CONSTRAINT upscaling_status_valid
            CHECK (upscaling_status IN ('pending','processing','complete','failed'));

-- Index for JIT upscaling webhook query
CREATE INDEX IF NOT EXISTS idx_creator_designs_upscaling_status
    ON creator_designs(upscaling_status);
CREATE INDEX IF NOT EXISTS idx_creator_designs_high_res
    ON creator_designs(high_res_master_url)
    WHERE high_res_master_url IS NULL;

-- ============================================================
-- STEP 3: Add credit_transactions to financial_ledger
-- ============================================================
-- Record token deductions and replenishments in a separate table
-- so the financial_ledger stays purely monetary.
CREATE TABLE IF NOT EXISTS credit_ledger (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id      TEXT        NOT NULL,
    event_type      TEXT        NOT NULL,  -- 'deduction'|'sale_replenishment'|'sample_replenishment'|'manual_grant'
    credits_delta   INTEGER     NOT NULL,  -- positive = credit, negative = deduction
    balance_after   INTEGER     NOT NULL,
    design_id       UUID,
    order_id        TEXT,
    note            TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_ledger_creator_id
    ON credit_ledger(creator_id);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_created_at
    ON credit_ledger(created_at DESC);

ALTER TABLE credit_ledger ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'credit_ledger'
        AND policyname = 'service_role_full_access_credits'
    ) THEN
        CREATE POLICY "service_role_full_access_credits"
            ON credit_ledger FOR ALL
            USING (auth.role() = 'service_role')
            WITH CHECK (auth.role() = 'service_role');
    END IF;
END
$$;

-- ============================================================
-- STEP 4: SQL function — atomically deduct 1 credit
-- ============================================================
CREATE OR REPLACE FUNCTION deduct_ai_credit(p_creator_shopify_id TEXT, p_design_id UUID DEFAULT NULL)
RETURNS TABLE(
    success         BOOLEAN,
    new_balance     INTEGER,
    message         TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_creator_id    TEXT;
    v_current       INTEGER;
    v_new_balance   INTEGER;
BEGIN
    -- Find creator by shopify_customer_id
    SELECT id, ai_credits
    INTO v_creator_id, v_current
    FROM creators
    WHERE shopify_customer_id = p_creator_shopify_id
    LIMIT 1;

    IF v_creator_id IS NULL THEN
        RETURN QUERY SELECT FALSE, 0, 'Creator not found'::TEXT;
        RETURN;
    END IF;

    IF v_current <= 0 THEN
        RETURN QUERY SELECT FALSE, v_current,
            'Insufficient Narrative Tokens. Make a sale or purchase a Sample Kit to earn more.'::TEXT;
        RETURN;
    END IF;

    -- Atomically deduct 1 credit
    UPDATE creators
    SET ai_credits       = ai_credits - 1,
        total_credits_used = COALESCE(total_credits_used, 0) + 1
    WHERE id = v_creator_id
    RETURNING ai_credits INTO v_new_balance;

    -- Write to credit_ledger
    INSERT INTO credit_ledger (creator_id, event_type, credits_delta, balance_after, design_id, note)
    VALUES (v_creator_id, 'deduction', -1, v_new_balance, p_design_id,
            'AI design generation — 1 Narrative Token used');

    RETURN QUERY SELECT TRUE, v_new_balance,
        format('Token used. %s Narrative Tokens remaining.', v_new_balance)::TEXT;
END;
$$;

-- ============================================================
-- STEP 5: SQL function — replenish credits on sale
-- ============================================================
CREATE OR REPLACE FUNCTION replenish_ai_credits(
    p_creator_shopify_id TEXT,
    p_credits_to_add     INTEGER,
    p_order_id           TEXT,
    p_event_type         TEXT DEFAULT 'sale_replenishment',
    p_note               TEXT DEFAULT ''
)
RETURNS TABLE(
    creator_db_id   TEXT,
    old_balance     INTEGER,
    new_balance     INTEGER,
    credits_added   INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_creator_id  TEXT;
    v_old_balance INTEGER;
    v_new_balance INTEGER;
BEGIN
    SELECT id, ai_credits
    INTO v_creator_id, v_old_balance
    FROM creators
    WHERE shopify_customer_id = p_creator_shopify_id
    LIMIT 1;

    IF v_creator_id IS NULL THEN
        RETURN;
    END IF;

    UPDATE creators
    SET ai_credits          = ai_credits + p_credits_to_add,
        total_credits_earned = COALESCE(total_credits_earned, 0) + p_credits_to_add
    WHERE id = v_creator_id
    RETURNING ai_credits INTO v_new_balance;

    INSERT INTO credit_ledger (creator_id, event_type, credits_delta, balance_after, order_id, note)
    VALUES (v_creator_id, p_event_type, p_credits_to_add, v_new_balance, p_order_id,
            COALESCE(NULLIF(p_note,''), format('+%s Narrative Tokens from %s', p_credits_to_add, p_event_type)));

    RETURN QUERY SELECT v_creator_id, v_old_balance, v_new_balance, p_credits_to_add;
END;
$$;

-- ============================================================
-- STEP 6: Self-verification
-- ============================================================
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    -- Check ai_credits column exists
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns
    WHERE table_name = 'creators' AND column_name = 'ai_credits';
    ASSERT col_count = 1, 'ai_credits column missing from creators table';

    -- Check high_res_master_url column exists
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns
    WHERE table_name = 'creator_designs' AND column_name = 'high_res_master_url';
    ASSERT col_count = 1, 'high_res_master_url column missing from creator_designs table';

    -- Check credit_ledger table exists
    SELECT COUNT(*) INTO col_count
    FROM information_schema.tables
    WHERE table_name = 'credit_ledger';
    ASSERT col_count = 1, 'credit_ledger table missing';

    RAISE NOTICE '✅ Token Economy migration verified: ai_credits, high_res_master_url, credit_ledger all present';
END
$$;

-- ============================================================
-- SUMMARY
-- ============================================================
-- creators table:      + ai_credits (default 3), total_credits_earned, total_credits_used
-- creator_designs:     + high_res_master_url, upscaling_status
-- NEW TABLE:           credit_ledger (immutable token transaction log)
-- NEW FUNCTIONS:       deduct_ai_credit(), replenish_ai_credits()
-- ============================================================
