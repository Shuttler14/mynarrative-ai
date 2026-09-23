-- Offer Intelligence Engine v1
-- Run in Supabase SQL Editor

-- Source registry (where we crawl from)
CREATE TABLE IF NOT EXISTS mn_offer_sources (
  source_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  issuer_bank TEXT,
  merchant_name TEXT,
  url TEXT NOT NULL,
  crawl_frequency_hours INTEGER DEFAULT 6,
  parser_id TEXT NOT NULL,
  last_crawled_at TIMESTAMPTZ,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Structured offers (core table)
CREATE TABLE IF NOT EXISTS mn_offers (
  offer_id TEXT PRIMARY KEY,
  merchant_name TEXT NOT NULL,
  merchant_url TEXT,
  bank_name TEXT NOT NULL,
  card_type TEXT,
  card_variants TEXT[] DEFAULT '{}',
  discount_type TEXT NOT NULL,
  discount_value NUMERIC(5,2) NOT NULL,
  max_discount NUMERIC(10,2),
  min_purchase NUMERIC(10,2),
  transaction_types TEXT[] DEFAULT '{non_emi}',
  applicable_categories TEXT[] DEFAULT '{}',
  excluded_categories TEXT[] DEFAULT '{}',
  applicable_products TEXT[] DEFAULT '{}',
  excluded_products TEXT[] DEFAULT '{}',
  exclusions TEXT[] DEFAULT '{}',
  valid_from TIMESTAMPTZ,
  valid_until TIMESTAMPTZ,
  terms TEXT,
  coupon_code TEXT,
  is_active BOOLEAN DEFAULT true,
  bank_verified BOOLEAN DEFAULT false,
  merchant_verified BOOLEAN DEFAULT false,
  checkout_verified BOOLEAN DEFAULT false,
  confidence_score NUMERIC(3,2) DEFAULT 0.5,
  last_verified_at TIMESTAMPTZ,
  source_url TEXT,
  raw_text TEXT,
  state TEXT DEFAULT 'discovered',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mn_offers_merchant ON mn_offers(merchant_name);
CREATE INDEX IF NOT EXISTS idx_mn_offers_bank ON mn_offers(bank_name);
CREATE INDEX IF NOT EXISTS idx_mn_offers_active ON mn_offers(is_active, valid_until);
CREATE INDEX IF NOT EXISTS idx_mn_offers_state ON mn_offers(state);
CREATE INDEX IF NOT EXISTS idx_mn_sources_active ON mn_offer_sources(is_active, last_crawled_at);
