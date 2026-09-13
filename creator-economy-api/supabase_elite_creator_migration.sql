-- ============================================================
-- ELITE CREATOR VERIFICATION — SCHEMA MIGRATION
-- Adds the columns that api/verify_social.py writes to when a
-- creator successfully proves ≥10k followers on any supported
-- social platform.
--
-- Safe to run multiple times.
-- ============================================================

ALTER TABLE IF EXISTS creators
    ADD COLUMN IF NOT EXISTS social_platform_verified   VARCHAR(32),
    ADD COLUMN IF NOT EXISTS verified_follower_count    INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS commission_tier            VARCHAR(32) DEFAULT 'standard',
    ADD COLUMN IF NOT EXISTS is_elite                   BOOLEAN     DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS elite_verified_at          TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS elite_verified_handle      VARCHAR(255);

-- A creator can be elite on at most one platform at a time (latest wins).
CREATE INDEX IF NOT EXISTS idx_creators_commission_tier
    ON creators (commission_tier);

CREATE INDEX IF NOT EXISTS idx_creators_is_elite
    ON creators (is_elite)
    WHERE is_elite = TRUE;

-- Back-fill: anything previously marked elite/mega should land in the new column.
-- Wrapped in DO so older schemas that never had `tier` / `is_mega_influencer`
-- don't crash the migration.
DO $$
DECLARE
    has_tier        BOOLEAN;
    has_mega        BOOLEAN;
    dyn_sql         TEXT;
    where_clauses   TEXT[] := ARRAY[]::TEXT[];
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'creators' AND column_name = 'tier'
    ) INTO has_tier;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'creators' AND column_name = 'is_mega_influencer'
    ) INTO has_mega;

    IF has_tier THEN
        where_clauses := array_append(where_clauses, 'tier = ''elite''');
    END IF;
    IF has_mega THEN
        where_clauses := array_append(where_clauses, 'is_mega_influencer = TRUE');
    END IF;

    IF array_length(where_clauses, 1) IS NOT NULL THEN
        dyn_sql := 'UPDATE creators
                       SET commission_tier = ''elite'',
                           is_elite        = TRUE
                     WHERE (' || array_to_string(where_clauses, ' OR ') || ')
                       AND (commission_tier IS NULL OR commission_tier = ''standard'')';
        EXECUTE dyn_sql;
    END IF;
END $$;

-- Back-fill standard for everybody else.
UPDATE creators
   SET commission_tier = 'standard'
 WHERE commission_tier IS NULL OR commission_tier = '';
