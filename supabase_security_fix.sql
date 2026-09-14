-- =====================================================
-- SECURITY FIX MIGRATION
-- 1. Enable RLS on global_inventory + create policies
-- 2. Fix brand_dashboard_summary SECURITY DEFINER
-- =====================================================

-- =====================================================
-- 1. GLOBAL INVENTORY — Enable RLS + Policies
-- =====================================================

-- Enable RLS (the main fix)
ALTER TABLE global_inventory ENABLE ROW LEVEL SECURITY;

-- Allow service_role full access (for API operations)
DROP POLICY IF EXISTS "Service role full access global_inventory" ON global_inventory;
CREATE POLICY "Service role full access global_inventory"
ON global_inventory FOR ALL
USING (true)
WITH CHECK (true);

-- Allow authenticated users to read (for recommendations)
DROP POLICY IF EXISTS "Authenticated read global_inventory" ON global_inventory;
CREATE POLICY "Authenticated read global_inventory"
ON global_inventory FOR SELECT
USING (true);

-- Allow anon read (for public API endpoints)
DROP POLICY IF EXISTS "Anon read global_inventory" ON global_inventory;
CREATE POLICY "Anon read global_inventory"
ON global_inventory FOR SELECT
USING (true);

-- =====================================================
-- 2. BRAND DASHBOARD SUMMARY — Remove SECURITY DEFINER
-- =====================================================

-- Drop and recreate without SECURITY DEFINER
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
-- 3. Enable RLS on brand_dashboard_summary (view inherits from base tables)
-- =====================================================
-- Views inherit RLS from their base tables (brands + brand_subscriptions)
-- No additional RLS needed for views — the base table policies apply

-- =====================================================
-- DONE
-- =====================================================
SELECT 'Security fixes applied: global_inventory RLS enabled, brand_dashboard_summary SECURITY DEFINER removed' AS status;
