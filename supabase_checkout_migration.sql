-- ============================================
-- MY NARRATIVE — Checkout Schema Updates
-- Adds Shopify integration fields + tracking
-- Change ID: MOD-CHK-004-260922
-- ============================================

-- Add Shopify order fields to narrative_orders
ALTER TABLE narrative_orders ADD COLUMN IF NOT EXISTS shopify_order_id TEXT;
ALTER TABLE narrative_orders ADD COLUMN IF NOT EXISTS shopify_order_number TEXT;
ALTER TABLE narrative_orders ADD COLUMN IF NOT EXISTS parent_order_id TEXT;
ALTER TABLE narrative_orders ADD COLUMN IF NOT EXISTS tracking_urls JSONB DEFAULT '[]';
ALTER TABLE narrative_orders ADD COLUMN IF NOT EXISTS tracking_numbers JSONB DEFAULT '[]';
ALTER TABLE narrative_orders ADD COLUMN IF NOT EXISTS shipped_at TIMESTAMPTZ;
ALTER TABLE narrative_orders ADD COLUMN IF NOT EXISTS razorpay_order_id TEXT;

-- Add Shopify order field to narrative_payments
ALTER TABLE narrative_payments ADD COLUMN IF NOT EXISTS shopify_order_id TEXT;

-- Add parent_order_id to narrative_commissions (for brand sub-order linking)
ALTER TABLE narrative_commissions ADD COLUMN IF NOT EXISTS parent_order_id TEXT;

-- Add host affiliate fields to narrative_commissions
ALTER TABLE narrative_commissions ADD COLUMN IF NOT EXISTS host_affiliate_rate NUMERIC(5,2) DEFAULT 0;
ALTER TABLE narrative_commissions ADD COLUMN IF NOT EXISTS host_affiliate_amount NUMERIC(10,2) DEFAULT 0;

-- Indexes for new fields
CREATE INDEX IF NOT EXISTS idx_narrative_orders_shopify ON narrative_orders(shopify_order_id);
CREATE INDEX IF NOT EXISTS idx_narrative_orders_parent ON narrative_orders(parent_order_id);
CREATE INDEX IF NOT EXISTS idx_narrative_payments_shopify ON narrative_payments(shopify_order_id);
CREATE INDEX IF NOT EXISTS idx_narrative_commissions_parent ON narrative_commissions(parent_order_id);
