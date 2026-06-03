-- =====================================================
-- MY NARRATIVE AI — SUPPORTING TABLES
-- User Looks, Flat-lay Cache, Recommendation Cache,
-- VTON Cache + RLS Policies
-- =====================================================
-- Run after supabase_schema.sql and supabase_global_inventory.sql

-- ─────────────────────────────────────────────────────
-- 1. USER LOOKS LIBRARY
-- ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_looks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  result_image_url TEXT NOT NULL,
  garments JSONB DEFAULT '[]',
  occasion TEXT DEFAULT '',
  vibe_id TEXT DEFAULT '',
  recommendation_context JSONB DEFAULT '{}',
  is_favorite BOOLEAN DEFAULT FALSE,
  is_deleted BOOLEAN DEFAULT FALSE,
  share_token TEXT UNIQUE DEFAULT encode(gen_random_bytes(12), 'hex'),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_looks_user ON user_looks(user_id) WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_user_looks_share ON user_looks(share_token);
CREATE INDEX IF NOT EXISTS idx_user_looks_occasion ON user_looks(occasion);


-- ─────────────────────────────────────────────────────
-- 2. FLAT-LAY CACHE
-- ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS flatlay_cache (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  original_url TEXT NOT NULL,
  original_url_hash TEXT NOT NULL,
  flat_lay_url TEXT NOT NULL,
  classification TEXT DEFAULT '',
  source_platform TEXT DEFAULT '',
  product_id TEXT DEFAULT '',
  garment_description TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_flatlay_cache_hash ON flatlay_cache(original_url_hash);
CREATE INDEX IF NOT EXISTS idx_flatlay_cache_product ON flatlay_cache(product_id) WHERE product_id != '';


-- ─────────────────────────────────────────────────────
-- 3. RECOMMENDATION CACHE
-- ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recommendation_cache (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cache_key TEXT UNIQUE NOT NULL,
  user_id TEXT NOT NULL,
  recommendation JSONB NOT NULL,
  marketplace_matches JSONB DEFAULT '[]',
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rec_cache_key ON recommendation_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_rec_cache_expires ON recommendation_cache(expires_at);


-- ─────────────────────────────────────────────────────
-- 4. VTON RESULT CACHE
-- ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vton_cache (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cache_key TEXT UNIQUE NOT NULL,
  result_url TEXT NOT NULL,
  original_replicate_url TEXT DEFAULT '',
  quality TEXT DEFAULT 'preview',
  garments_applied INTEGER DEFAULT 1,
  face_swapped BOOLEAN DEFAULT FALSE,
  processing_time_ms INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vton_cache_key ON vton_cache(cache_key);


-- ─────────────────────────────────────────────────────
-- 5. ROW LEVEL SECURITY — user_looks
-- ─────────────────────────────────────────────────────
ALTER TABLE user_looks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own looks"
  ON user_looks FOR SELECT
  USING (auth.uid()::text = user_id);

CREATE POLICY "Users insert own looks"
  ON user_looks FOR INSERT
  WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY "Users update own looks"
  ON user_looks FOR UPDATE
  USING (auth.uid()::text = user_id);

CREATE POLICY "Public read shared looks"
  ON user_looks FOR SELECT
  USING (share_token IS NOT NULL AND is_deleted = false);

CREATE POLICY "Service role full access looks"
  ON user_looks FOR ALL
  USING (true)
  WITH CHECK (true);


-- ─────────────────────────────────────────────────────
-- 6. STORAGE BUCKETS
-- (run via Supabase dashboard or management API)
-- ─────────────────────────────────────────────────────
-- INSERT INTO storage.buckets (id, name, public) VALUES ('user-looks', 'user-looks', true);
-- INSERT INTO storage.buckets (id, name, public) VALUES ('flatlay-cache', 'flatlay-cache', true);
-- INSERT INTO storage.buckets (id, name, public) VALUES ('vton-results', 'vton-results', true);
