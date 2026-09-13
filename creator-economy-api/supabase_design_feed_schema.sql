-- Design Feed Schema Migration for My Narrative Creator Economy

-- ALTER creator_designs to add new columns
DO $$ BEGIN
  ALTER TABLE creator_designs 
    ADD COLUMN IF NOT EXISTS total_likes INTEGER DEFAULT 0;
  ALTER TABLE creator_designs 
    ADD COLUMN IF NOT EXISTS shopify_product_url TEXT DEFAULT '';
  -- shopify_product_id and flat_image_url already exist, keeping safe
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- CREATE TABLE design_likes
CREATE TABLE IF NOT EXISTS design_likes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  design_id UUID REFERENCES creator_designs(id) ON DELETE CASCADE NOT NULL,
  user_identifier TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(design_id, user_identifier)
);

-- Enable RLS on design_likes
ALTER TABLE design_likes ENABLE ROW LEVEL SECURITY;

-- RLS Policy: public can insert
CREATE POLICY "design_likes_allow_insert" ON design_likes
  FOR INSERT WITH CHECK (true);

-- RLS Policy: public can read
CREATE POLICY "design_likes_allow_read" ON design_likes
  FOR SELECT USING (true);

-- ALTER creators to add new columns
DO $$ BEGIN
  ALTER TABLE creators 
    ADD COLUMN IF NOT EXISTS total_followers INTEGER DEFAULT 0;
  ALTER TABLE creators 
    ADD COLUMN IF NOT EXISTS average_rating NUMERIC(3,1) DEFAULT 4.5;
  ALTER TABLE creators 
    ADD COLUMN IF NOT EXISTS bio TEXT DEFAULT '';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- CREATE INDEX for designs by likes
CREATE INDEX IF NOT EXISTS idx_designs_likes ON creator_designs(total_likes DESC);

-- CREATE INDEX for designs feed ordering
CREATE INDEX IF NOT EXISTS idx_designs_feed ON creator_designs(status, created_at DESC);

-- CREATE INDEX for design_likes lookup
CREATE INDEX IF NOT EXISTS idx_design_likes_design ON design_likes(design_id);

-- CREATE VIEW for public design feed
CREATE OR REPLACE VIEW public_design_feed AS
  SELECT 
    cd.id, 
    cd.title, 
    cd.description,
    cd.flux_editorial_image_url as image_url,
    cd.price, 
    cd.total_sales, 
    cd.total_likes,
    cd.category, 
    cd.tags, 
    cd.created_at,
    cd.shopify_product_id,
    c.username as creator_username,
    c.avatar_url as creator_avatar,
    c.style_influence_rank as creator_tier,
    c.bio as creator_bio
  FROM creator_designs cd
  JOIN creators c ON c.id = cd.creator_id
  WHERE cd.status = 'active'
  ORDER BY cd.created_at DESC;

SELECT 'Design feed schema migration complete!' AS status;
