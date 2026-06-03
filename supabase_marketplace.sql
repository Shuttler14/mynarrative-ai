-- =====================================================
-- MARKETPLACE SCRAPER — SCHEMA MIGRATION
-- Extends global_inventory for web-scraped products
-- and adds scrape audit log table.
-- =====================================================

-- ─── Extend global_inventory with marketplace fields ───

ALTER TABLE global_inventory ADD COLUMN IF NOT EXISTS source_platform TEXT DEFAULT '';
ALTER TABLE global_inventory ADD COLUMN IF NOT EXISTS original_price NUMERIC DEFAULT 0;
ALTER TABLE global_inventory ADD COLUMN IF NOT EXISTS discount_pct INTEGER DEFAULT 0;
ALTER TABLE global_inventory ADD COLUMN IF NOT EXISTS rating NUMERIC DEFAULT 0;
ALTER TABLE global_inventory ADD COLUMN IF NOT EXISTS reviews_count INTEGER DEFAULT 0;
ALTER TABLE global_inventory ADD COLUMN IF NOT EXISTS sizes JSONB DEFAULT '[]';
ALTER TABLE global_inventory ADD COLUMN IF NOT EXISTS scrape_timestamp TIMESTAMPTZ DEFAULT NOW();

-- ─── Indexes for marketplace query patterns ───

CREATE INDEX IF NOT EXISTS idx_gi_source_platform ON global_inventory(source_platform);
CREATE INDEX IF NOT EXISTS idx_gi_category ON global_inventory(category);
CREATE INDEX IF NOT EXISTS idx_gi_brand ON global_inventory(brand);
CREATE INDEX IF NOT EXISTS idx_gi_price ON global_inventory(price);

-- ─── Scrape audit log ───

CREATE TABLE IF NOT EXISTS marketplace_scrape_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  platform TEXT NOT NULL,
  query TEXT NOT NULL,
  category TEXT DEFAULT '',
  products_found INTEGER DEFAULT 0,
  products_ingested INTEGER DEFAULT 0,
  errors JSONB DEFAULT '[]',
  duration_ms INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
