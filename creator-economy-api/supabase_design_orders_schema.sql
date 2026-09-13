-- ============================================================
-- CREATE design_orders TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS design_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shopify_order_id TEXT UNIQUE NOT NULL,
    shopify_customer_id TEXT,
    customer_email TEXT,
    unique_product_id TEXT,
    design_file_url TEXT,
    shopify_product_id TEXT,
    shopify_variant_id TEXT,
    price_paise INTEGER,
    quantity INTEGER DEFAULT 1,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Enable RLS and add service role full access policy
-- ============================================================
ALTER TABLE design_orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_full_access" ON design_orders
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ============================================================
-- Add indexes
-- ============================================================
CREATE INDEX idx_design_orders_shopify_order_id ON design_orders(shopify_order_id);
CREATE INDEX idx_design_orders_shopify_customer_id ON design_orders(shopify_customer_id);
CREATE INDEX idx_design_orders_unique_product_id ON design_orders(unique_product_id);

-- ============================================================
-- ALTER creator_designs TABLE to add new columns
-- ============================================================
ALTER TABLE IF EXISTS creator_designs
ADD COLUMN IF NOT EXISTS unique_product_id TEXT,
ADD COLUMN IF NOT EXISTS master_file_url TEXT,
ADD COLUMN IF NOT EXISTS mockup_urls JSONB DEFAULT '{}';
