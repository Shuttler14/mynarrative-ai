-- ============================================
-- MY NARRATIVE — Attribution & Commission System
-- "Last eligible click + 30 days + line-item"
-- ============================================
-- Change ID: ADD-CHK-010-260922
-- Risk: CRITICAL — financial backbone
-- Revert: DROP all tables in reverse order
-- ============================================

-- ============================================
-- 1. PRODUCT REGISTRY
-- Permanent MN Product IDs that never change
-- ============================================
CREATE TABLE IF NOT EXISTS narrative_product_registry (
  mn_product_id TEXT PRIMARY KEY,              -- Permanent, never changes (MN-P-XXXXXXXX)
  brand_id TEXT NOT NULL,                       -- Owner brand
  shopify_product_id TEXT,                      -- Shopify's product ID
  shopify_variant_ids JSONB DEFAULT '[]',       -- All variant IDs mapped
  external_id TEXT,                             -- Marketplace SKU/ASIN
  canonical_url TEXT,                           -- Current product URL
  product_name TEXT NOT NULL,
  product_data JSONB DEFAULT '{}',              -- {name, price, images, category, etc}
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'deleted')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_product_registry_brand ON narrative_product_registry(brand_id);
CREATE INDEX idx_product_registry_shopify ON narrative_product_registry(shopify_product_id);
CREATE INDEX idx_product_registry_external ON narrative_product_registry(external_id);

-- ============================================
-- 2. CLICK TRACKING
-- Every product click gets a permanent network_click_id
-- ============================================
CREATE TABLE IF NOT EXISTS narrative_clicks (
  click_id TEXT PRIMARY KEY,                    -- MN-CLK-XXXXXXXX (permanent, never reused)
  mn_product_id TEXT NOT NULL REFERENCES narrative_product_registry(mn_product_id),
  host_brand_id TEXT NOT NULL,                  -- Brand that displayed the recommendation
  advertiser_brand_id TEXT NOT NULL,            -- Brand that owns the product
  user_id TEXT,
  session_id TEXT,
  fingerprint TEXT,                             -- Browser fingerprint for anonymous users
  campaign_id TEXT,                             -- Sponsored campaign (if any)
  vton_session_id TEXT,                         -- VTON session that led to this click
  source TEXT NOT NULL,                         -- 'widget', 'vton', 'outfit', 'search', 'catalog'
  source_detail TEXT,                           -- 'recommendation_card', 'vton_result', 'outfit_card'
  referrer_url TEXT,                            -- Where they came from
  destination_url TEXT,                         -- Where they're going
  attribution_window_days INTEGER DEFAULT 30,   -- How long this click is valid
  attributed BOOLEAN DEFAULT false,             -- Has this click been attributed to a purchase?
  attributed_at TIMESTAMPTZ,
  attributed_order_id TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  expires_at TIMESTAMPTZ DEFAULT (now() + INTERVAL '30 days')
);

CREATE INDEX idx_clicks_product ON narrative_clicks(mn_product_id);
CREATE INDEX idx_clicks_user ON narrative_clicks(user_id);
CREATE INDEX idx_clicks_session ON narrative_clicks(session_id);
CREATE INDEX idx_clicks_host ON narrative_clicks(host_brand_id);
CREATE INDEX idx_clicks_advertiser ON narrative_clicks(advertiser_brand_id);
CREATE INDEX idx_clicks_campaign ON narrative_clicks(campaign_id);
CREATE INDEX idx_clicks_expires ON narrative_clicks(expires_at);
CREATE INDEX idx_clicks_attributed ON narrative_clicks(attributed);

-- ============================================
-- 3. ATTRIBUTION EVENTS
-- Records every meaningful interaction for attribution
-- ============================================
CREATE TABLE IF NOT EXISTS narrative_attribution_events (
  event_id TEXT PRIMARY KEY,                    -- Unique event ID
  click_id TEXT NOT NULL REFERENCES narrative_clicks(click_id),
  mn_product_id TEXT NOT NULL REFERENCES narrative_product_registry(mn_product_id),
  user_id TEXT,
  session_id TEXT,
  host_brand_id TEXT NOT NULL,
  advertiser_brand_id TEXT NOT NULL,
  campaign_id TEXT,
  event_type TEXT NOT NULL,                     -- 'click', 'vton_view', 'add_to_cart', 'checkout_start', 'purchase'
  event_data JSONB DEFAULT '{}',                -- Additional context
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_attr_events_click ON narrative_attribution_events(click_id);
CREATE INDEX idx_attr_events_user ON narrative_attribution_events(user_id);
CREATE INDEX idx_attr_events_product ON narrative_attribution_events(mn_product_id);
CREATE INDEX idx_attr_events_type ON narrative_attribution_events(event_type);
CREATE INDEX idx_attr_events_created ON narrative_attribution_events(created_at);

-- ============================================
-- 4. COMMISSION LEDGER (Immutable)
-- Every financial event is a new row, never overwrite
-- ============================================
CREATE TABLE IF NOT EXISTS narrative_commission_ledger (
  event_id TEXT PRIMARY KEY,                    -- Unique event ID (idempotent)
  event_type TEXT NOT NULL,                     -- COMMISSION_CREATED, COMMISSION_CONFIRMED, COMMISSION_REVERSAL, COMMISSION_FINALIZED, COMMISSION_PAID
  idempotency_key TEXT UNIQUE,                  -- Prevents duplicate processing

  -- Source references
  order_id TEXT NOT NULL,                       -- Merchant order ID
  order_item_id TEXT,                           -- Line-item ID
  click_id TEXT,                                -- Links to attribution
  mn_product_id TEXT,                           -- Links to product registry

  -- Parties
  host_brand_id TEXT NOT NULL,                  -- Who displayed the recommendation
  advertiser_brand_id TEXT NOT NULL,            -- Who owns the product
  campaign_id TEXT,                             -- Sponsored campaign (if any)

  -- Financials
  gross_item_value NUMERIC(10,2) NOT NULL,
  discount NUMERIC(10,2) DEFAULT 0,
  tax NUMERIC(10,2) DEFAULT 0,
  shipping NUMERIC(10,2) DEFAULT 0,
  net_commissionable_value NUMERIC(10,2) NOT NULL,

  -- Platform commission
  commission_rate NUMERIC(5,2) NOT NULL,        -- e.g. 10.00
  commission_amount NUMERIC(10,2) NOT NULL,

  -- Host affiliate (cross-brand only)
  host_affiliate_rate NUMERIC(5,2) DEFAULT 0,   -- e.g. 7.00
  host_affiliate_amount NUMERIC(10,2) DEFAULT 0,

  -- Platform fee
  platform_fee NUMERIC(10,2) NOT NULL,

  -- Brand payout
  brand_payout NUMERIC(10,2) NOT NULL,

  -- Attribution
  attribution_confidence TEXT NOT NULL,         -- DIRECT, VERIFIED, ATTRIBUTED, UNVERIFIED
  attribution_window_days INTEGER,

  -- Status lifecycle
  status TEXT NOT NULL CHECK (status IN ('PENDING', 'CONFIRMED', 'VOIDED', 'REFUNDED', 'PARTIALLY_REFUNDED', 'DISPUTED', 'PAYABLE', 'PAID')),

  -- Reconciliation
  reconciled_at TIMESTAMPTZ,
  reconciled_source TEXT,                       -- 'webhook', 'reconciliation', 'manual'

  -- Refund tracking
  original_event_id TEXT,                       -- Links reversal to original commission
  refund_amount NUMERIC(10,2) DEFAULT 0,

  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_ledger_order ON narrative_commission_ledger(order_id);
CREATE INDEX idx_ledger_item ON narrative_commission_ledger(order_item_id);
CREATE INDEX idx_ledger_click ON narrative_commission_ledger(click_id);
CREATE INDEX idx_ledger_product ON narrative_commission_ledger(mn_product_id);
CREATE INDEX idx_ledger_host ON narrative_commission_ledger(host_brand_id);
CREATE INDEX idx_ledger_advertiser ON narrative_commission_ledger(advertiser_brand_id);
CREATE INDEX idx_ledger_status ON narrative_commission_ledger(status);
CREATE INDEX idx_ledger_event_type ON narrative_commission_ledger(event_type);
CREATE INDEX idx_ledger_idempotency ON narrative_commission_ledger(idempotency_key);
CREATE INDEX idx_ledger_created ON narrative_commission_ledger(created_at);

-- ============================================
-- 5. MERCHANT ORDERS (for reconciliation)
-- Tracks every order from merchant Shopify stores
-- ============================================
CREATE TABLE IF NOT EXISTS narrative_merchant_orders (
  id TEXT PRIMARY KEY,                          -- Internal ID
  shopify_order_id TEXT UNIQUE NOT NULL,
  merchant_brand_id TEXT NOT NULL,
  order_number TEXT,
  order_data JSONB NOT NULL,                    -- Full Shopify order snapshot
  financial_status TEXT,                         -- paid, pending, refunded, etc.
  fulfillment_status TEXT,                       -- fulfilled, partial, unfulfilled
  total_amount NUMERIC(10,2),
  line_items JSONB NOT NULL,                    -- All line items with product/variant IDs
  last_synced_at TIMESTAMPTZ NOT NULL,
  reconciled BOOLEAN DEFAULT false,
  reconciled_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_merchant_orders_shopify ON narrative_merchant_orders(shopify_order_id);
CREATE INDEX idx_merchant_orders_brand ON narrative_merchant_orders(merchant_brand_id);
CREATE INDEX idx_merchant_orders_reconciled ON narrative_merchant_orders(reconciled);
CREATE INDEX idx_merchant_orders_synced ON narrative_merchant_orders(last_synced_at);

-- ============================================
-- 6. RECONCILIATION LOG
-- Tracks every reconciliation run
-- ============================================
CREATE TABLE IF NOT EXISTS narrative_reconciliation_log (
  id TEXT PRIMARY KEY,
  run_type TEXT NOT NULL,                       -- 'scheduled', 'manual', 'triggered'
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  orders_checked INTEGER DEFAULT 0,
  orders_matched INTEGER DEFAULT 0,
  orders_discrepancy INTEGER DEFAULT 0,
  commissions_adjusted INTEGER DEFAULT 0,
  status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
  errors JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- 7. MERCHANT WEB PIXEL EVENTS
-- Events from Shopify Web Pixel on merchant sites
-- ============================================
CREATE TABLE IF NOT EXISTS narrative_pixel_events (
  id TEXT PRIMARY KEY,
  merchant_brand_id TEXT NOT NULL,
  click_id TEXT,                                -- Re-links to our click_id
  user_id TEXT,
  session_id TEXT,
  event_type TEXT NOT NULL,                     -- 'product_viewed', 'product_added_to_cart', 'checkout_started', 'checkout_completed'
  product_data JSONB,                           -- {product_id, variant_id, price, etc}
  order_data JSONB,                             -- {order_id, total, line_items, etc}
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_pixel_events_merchant ON narrative_pixel_events(merchant_brand_id);
CREATE INDEX idx_pixel_events_click ON narrative_pixel_events(click_id);
CREATE INDEX idx_pixel_events_type ON narrative_pixel_events(event_type);
CREATE INDEX idx_pixel_events_created ON narrative_pixel_events(created_at);

-- ============================================
-- 8. COMMISSION SETTLEMENTS
-- Tracks payout batches to brands
-- ============================================
CREATE TABLE IF NOT EXISTS narrative_settlements (
  id TEXT PRIMARY KEY,
  brand_id TEXT NOT NULL,
  settlement_period_start TIMESTAMPTZ NOT NULL,
  settlement_period_end TIMESTAMPTZ NOT NULL,
  total_orders INTEGER DEFAULT 0,
  total_gross_amount NUMERIC(10,2) DEFAULT 0,
  total_commission NUMERIC(10,2) DEFAULT 0,
  total_host_affiliate NUMERIC(10,2) DEFAULT 0,
  total_platform_fee NUMERIC(10,2) DEFAULT 0,
  total_brand_payout NUMERIC(10,2) DEFAULT 0,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  paid_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_settlements_brand ON narrative_settlements(brand_id);
CREATE INDEX idx_settlements_status ON narrative_settlements(status);

-- ============================================
-- 9. ATTEMPTED PURCHASE TRACKING
-- Products user tried to buy but didn't complete
-- ============================================
CREATE TABLE IF NOT EXISTS narrative_abandoned_checkouts (
  id TEXT PRIMARY KEY,
  click_id TEXT REFERENCES narrative_clicks(click_id),
  mn_product_id TEXT REFERENCES narrative_product_registry(mn_product_id),
  user_id TEXT,
  host_brand_id TEXT,
  advertiser_brand_id TEXT,
  cart_data JSONB,
  total_amount NUMERIC(10,2),
  abandoned_at TIMESTAMPTZ DEFAULT now(),
  recovered BOOLEAN DEFAULT false,
  recovered_at TIMESTAMPTZ,
  recovered_order_id TEXT
);

CREATE INDEX idx_abandoned_user ON narrative_abandoned_checkouts(user_id);
CREATE INDEX idx_abandoned_click ON narrative_abandoned_checkouts(click_id);
CREATE INDEX idx_abandoned_recovered ON narrative_abandoned_checkouts(recovered);

-- ============================================
-- RPC FUNCTIONS
-- ============================================

-- Get last eligible click for attribution
CREATE OR REPLACE FUNCTION get_last_eligible_click(
  p_user_id TEXT,
  p_mn_product_id TEXT,
  p_advertiser_brand_id TEXT
)
RETURNS TABLE (
  click_id TEXT,
  host_brand_id TEXT,
  campaign_id TEXT,
  created_at TIMESTAMPTZ
) AS $$
BEGIN
  RETURN QUERY
  SELECT c.click_id, c.host_brand_id, c.campaign_id, c.created_at
  FROM narrative_clicks c
  WHERE c.user_id = p_user_id
    AND c.mn_product_id = p_mn_product_id
    AND c.advertiser_brand_id = p_advertiser_brand_id
    AND c.attributed = false
    AND c.expires_at > now()
  ORDER BY c.created_at DESC
  LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Mark click as attributed
CREATE OR REPLACE FUNCTION mark_click_attributed(
  p_click_id TEXT,
  p_order_id TEXT
)
RETURNS void AS $$
BEGIN
  UPDATE narrative_clicks
  SET attributed = true,
      attributed_at = now(),
      attributed_order_id = p_order_id
  WHERE click_id = p_click_id;
END;
$$ LANGUAGE plpgsql;

-- Get commission summary for brand
CREATE OR REPLACE FUNCTION get_brand_commission_summary(
  p_brand_id TEXT,
  p_start_date TIMESTAMPTZ DEFAULT NULL,
  p_end_date TIMESTAMPTZ DEFAULT now()
)
RETURNS TABLE (
  total_orders BIGINT,
  total_gross NUMERIC(10,2),
  total_commission NUMERIC(10,2),
  total_host_affiliate NUMERIC(10,2),
  total_platform_fee NUMERIC(10,2),
  total_brand_payout NUMERIC(10,2)
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    COUNT(DISTINCT l.order_id)::BIGINT,
    COALESCE(SUM(l.gross_item_value), 0),
    COALESCE(SUM(l.commission_amount), 0),
    COALESCE(SUM(l.host_affiliate_amount), 0),
    COALESCE(SUM(l.platform_fee), 0),
    COALESCE(SUM(l.brand_payout), 0)
  FROM narrative_commission_ledger l
  WHERE (l.advertiser_brand_id = p_brand_id OR l.host_brand_id = p_brand_id)
    AND l.status NOT IN ('VOIDED', 'REFUNDED')
    AND l.created_at >= COALESCE(p_start_date, '2020-01-01'::TIMESTAMPTZ)
    AND l.created_at <= p_end_date;
END;
$$ LANGUAGE plpgsql;
