-- ============================================================
-- CREATOR PIPELINE — END-TO-END SCHEMA MIGRATION
-- Adds the columns that sections/creator-onboarding-flow.liquid,
-- sections/creator-upload-studio.liquid, and api/design_publish.py
-- now read/write.
--
-- Safe to run multiple times: every ALTER uses ADD COLUMN IF NOT EXISTS.
-- ============================================================

-- ------------------------------------------------------------
-- 1. `creators` — onboarding-flow profile fields
-- ------------------------------------------------------------
ALTER TABLE IF EXISTS creators
    ADD COLUMN IF NOT EXISTS narrative_name          TEXT DEFAULT '',
    ADD COLUMN IF NOT EXISTS brand_name              TEXT DEFAULT '',
    ADD COLUMN IF NOT EXISTS description             TEXT DEFAULT '',
    ADD COLUMN IF NOT EXISTS profile_photo_url       TEXT DEFAULT '',
    ADD COLUMN IF NOT EXISTS primary_platform        TEXT,
    ADD COLUMN IF NOT EXISTS tier                    TEXT DEFAULT 'basic',
    ADD COLUMN IF NOT EXISTS onboarding_completed    BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_at              TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_creators_narrative_name
    ON creators (LOWER(narrative_name));

-- Back-fill a sensible narrative_name for existing rows where it's blank.
UPDATE creators
   SET narrative_name = COALESCE(NULLIF(narrative_name, ''),
                                 brand_name,
                                 username || '''s Designs')
 WHERE narrative_name IS NULL OR narrative_name = '';

-- ------------------------------------------------------------
-- 2. `creator_designs` — upload-flow + publish-flow fields
-- ------------------------------------------------------------
ALTER TABLE IF EXISTS creator_designs
    ADD COLUMN IF NOT EXISTS source              TEXT DEFAULT 'creator_upload',  -- 'creator_upload' | 'ai_studio'
    ADD COLUMN IF NOT EXISTS placement           TEXT DEFAULT 'front',
    ADD COLUMN IF NOT EXISTS color               TEXT DEFAULT '',
    ADD COLUMN IF NOT EXISTS shopify_product_url TEXT DEFAULT '',
    ADD COLUMN IF NOT EXISTS product_type        TEXT,                           -- 'tshirt' | 'hoodie'
    ADD COLUMN IF NOT EXISTS selected_colors     JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS price_paise         INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS mockup_urls         JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS unique_product_id   TEXT,
    ADD COLUMN IF NOT EXISTS master_file_url     TEXT;

CREATE INDEX IF NOT EXISTS idx_creator_designs_status_new
    ON creator_designs(status)
 WHERE status IN ('draft', 'active', 'published');

-- Normalize legacy rows: anything with status NULL/empty becomes 'draft'
UPDATE creator_designs
   SET status = 'draft'
 WHERE status IS NULL OR status = '';

-- ------------------------------------------------------------
-- 3. Storage bucket for creator assets (uploads + avatars)
--    idempotent — Supabase ignores if it already exists.
-- ------------------------------------------------------------
INSERT INTO storage.buckets (id, name, public)
VALUES ('creator_assets', 'creator_assets', true)
ON CONFLICT (id) DO NOTHING;

-- Allow public reads & authenticated (or service_role) writes on creator_assets.
DROP POLICY IF EXISTS "creator_assets public read"  ON storage.objects;
DROP POLICY IF EXISTS "creator_assets owner write"  ON storage.objects;

CREATE POLICY "creator_assets public read" ON storage.objects
    FOR SELECT USING (bucket_id = 'creator_assets');

CREATE POLICY "creator_assets owner write" ON storage.objects
    FOR ALL USING (bucket_id = 'creator_assets')
    WITH CHECK (bucket_id = 'creator_assets');
