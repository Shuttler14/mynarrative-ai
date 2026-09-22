-- ============================================
-- MY NARRATIVE — User Data System
-- Style Intelligence Profile + Cards + Offers + Person Profiles
-- ============================================
-- Change ID: ADD-USR-001-260922
-- Risk: CRITICAL — user data backbone
-- ============================================

-- ============================================
-- 1. USER PROFILES
-- Core identity + basic info
-- ============================================
CREATE TABLE IF NOT EXISTS mn_user_profiles (
  user_id TEXT PRIMARY KEY,                    -- Firebase/Supabase auth ID or generated
  email TEXT,
  phone TEXT,
  display_name TEXT,
  avatar_url TEXT,
  gender TEXT CHECK (gender IN ('male', 'female', 'non_binary', 'prefer_not_to_say')),
  age_range TEXT CHECK (age_range IN ('16-20', '21-25', '26-30', '31-35', '36-40', '41-50', '50+')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  last_active_at TIMESTAMPTZ
);

-- ============================================
-- 2. PERSON PROFILES
-- Each person a user uploads (self + others)
-- ============================================
CREATE TABLE IF NOT EXISTS mn_person_profiles (
  person_id TEXT PRIMARY KEY,                  -- Generated UUID
  user_id TEXT NOT NULL REFERENCES mn_user_profiles(user_id),
  relationship TEXT CHECK (relationship IN ('self', 'partner', 'parent', 'sibling', 'friend', 'colleague', 'other')),
  label TEXT,                                  -- User-given label (e.g., "My sister", "Mom")
  is_self BOOLEAN DEFAULT false,
  
  -- Body profile (extracted from images or user input)
  height_cm INTEGER,
  body_type TEXT,                              -- slim, athletic, average, curvy, plus_size
  shoulder_structure TEXT,                     -- narrow, regular, broad
  torso_length TEXT,                           -- short, regular, long
  leg_proportion TEXT,                         -- short, regular, long
  fit_preference TEXT CHECK (fit_preference IN ('slim', 'regular', 'relaxed', 'oversized')),
  
  -- Style profile
  preferred_styles TEXT[] DEFAULT '{}',         -- minimalist, streetwear, classic, etc.
  preferred_colors TEXT[] DEFAULT '{}',         -- white, black, navy, etc.
  avoid_colors TEXT[] DEFAULT '{}',
  preferred_patterns TEXT[] DEFAULT '{}',       -- solid, stripes, floral, etc.
  
  -- Metadata
  image_count INTEGER DEFAULT 0,
  tryon_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_person_user ON mn_person_profiles(user_id);
CREATE INDEX idx_person_self ON mn_person_profiles(user_id, is_self);

-- ============================================
-- 3. USER MEDIA
-- Images uploaded by users (profile pics, try-on inputs)
-- ============================================
CREATE TABLE IF NOT EXISTS mn_user_media (
  media_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES mn_user_profiles(user_id),
  person_id TEXT REFERENCES mn_person_profiles(person_id),
  media_type TEXT CHECK (media_type IN ('profile_photo', 'tryon_input', 'tryon_output', 'closet_item')),
  storage_url TEXT NOT NULL,                   -- R2/S3 URL
  thumbnail_url TEXT,
  metadata JSONB DEFAULT '{}',                 -- dimensions, file size, etc
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_media_user ON mn_user_media(user_id);
CREATE INDEX idx_media_person ON mn_user_media(person_id);

-- ============================================
-- 4. SAVED CARDS
-- Bank cards for offer matching
-- ============================================
CREATE TABLE IF NOT EXISTS mn_saved_cards (
  card_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES mn_user_profiles(user_id),
  bank_name TEXT NOT NULL,                      -- HDFC, ICICI, SBI, etc.
  card_type TEXT NOT NULL CHECK (card_type IN ('credit', 'debit')),
  card_variant TEXT NOT NULL,                   -- Regalia Gold, Cashback, etc.
  card_network TEXT,                            -- Visa, Mastercard, RuPay, Amex
  is_primary BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_cards_user ON mn_saved_cards(user_id);

-- ============================================
-- 5. INDIAN BANKS & CARD VARIANTS
-- Reference data for card selection
-- ============================================
CREATE TABLE IF NOT EXISTS mn_bank_cards (
  id TEXT PRIMARY KEY,
  bank_name TEXT NOT NULL,
  card_type TEXT NOT NULL CHECK (card_type IN ('credit', 'debit')),
  card_variant TEXT NOT NULL,
  card_network TEXT,                            -- Visa, Mastercard, RuPay, Amex
  is_popular BOOLEAN DEFAULT false,             -- Show in top results
  annual_fee TEXT,                              -- "₹0", "₹500", "₹2,500"
  reward_type TEXT,                             -- cashback, travel, rewards, shopping
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_bank_cards_bank ON mn_bank_cards(bank_name);
CREATE INDEX idx_bank_cards_popular ON mn_bank_cards(is_popular);

-- ============================================
-- 6. MERCHANT OFFERS
-- Bank/card offers from merchants
-- ============================================
CREATE TABLE IF NOT EXISTS mn_merchant_offers (
  offer_id TEXT PRIMARY KEY,
  merchant_name TEXT NOT NULL,                  -- Myntra, Amazon, Flipkart, etc.
  merchant_url TEXT,
  
  -- Bank details
  bank_name TEXT NOT NULL,
  card_type TEXT CHECK (card_type IN ('credit', 'debit', 'both')),
  card_variants TEXT[] DEFAULT '{}',            -- Empty = all cards from bank
  
  -- Discount
  discount_type TEXT CHECK (discount_type IN ('percentage', 'flat')),
  discount_value NUMERIC(5,2) NOT NULL,        -- 10.00 = 10%, or 500.00 = ₹500
  max_discount NUMERIC(10,2),                  -- Cap (e.g., ₹1,000)
  min_purchase NUMERIC(10,2),                  -- Minimum order (e.g., ₹4,999)
  
  -- Validity
  valid_from TIMESTAMPTZ,
  valid_until TIMESTAMPTZ,
  
  -- Conditions
  applicable_categories TEXT[] DEFAULT '{}',    -- Empty = all categories
  applicable_products TEXT[] DEFAULT '{}',      -- Empty = all products
  terms TEXT,
  
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_offers_merchant ON mn_merchant_offers(merchant_name);
CREATE INDEX idx_offers_bank ON mn_merchant_offers(bank_name);
CREATE INDEX idx_offers_active ON mn_merchant_offers(is_active, valid_until);

-- ============================================
-- 7. TRY-ON SESSIONS
-- Track every VTON attempt with context
-- ============================================
CREATE TABLE IF NOT EXISTS mn_tryon_sessions (
  session_id TEXT PRIMARY KEY,
  user_id TEXT REFERENCES mn_user_profiles(user_id),
  person_id TEXT REFERENCES mn_person_profiles(person_id),
  
  -- Input
  person_image_url TEXT,
  garment_image_url TEXT,
  garment_name TEXT,
  occasion TEXT,
  
  -- Output
  vton_result_url TEXT,
  quality_score NUMERIC(3,2),
  processing_time_ms INTEGER,
  
  -- User feedback
  is_me BOOLEAN,                               -- "Was this you?" answer
  saved BOOLEAN DEFAULT false,
  relationship TEXT,                            -- If saved for someone else
  
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_tryon_user ON mn_tryon_sessions(user_id);
CREATE INDEX idx_tryon_person ON mn_tryon_sessions(person_id);

-- ============================================
-- 8. SAVED OUTFITS
-- ============================================
CREATE TABLE IF NOT EXISTS mn_saved_outfits (
  outfit_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES mn_user_profiles(user_id),
  person_id TEXT REFERENCES mn_person_profiles(person_id),
  
  -- Outfit data
  outfit_name TEXT,
  occasion TEXT,
  items JSONB NOT NULL,                         -- [{product_id, title, price, image_url, slot, source}]
  total_price NUMERIC(10,2),
  best_price NUMERIC(10,2),                     -- After card offers
  best_offer TEXT,                              -- Which offer applied
  
  -- VTON
  vton_image_url TEXT,
  
  -- Card applied
  card_id TEXT REFERENCES mn_saved_cards(card_id),
  
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_outfits_user ON mn_saved_outfits(user_id);
CREATE INDEX idx_outfits_person ON mn_saved_outfits(person_id);

-- ============================================
-- 9. RECOMMENDATION HISTORY
-- Every recommendation shown to user
-- ============================================
CREATE TABLE IF NOT EXISTS mn_recommendation_history (
  id TEXT PRIMARY KEY,
  user_id TEXT REFERENCES mn_user_profiles(user_id),
  session_id TEXT,
  
  -- Context
  occasion TEXT,
  style TEXT,
  gender TEXT,
  weather JSONB,
  
  -- Results
  recommendations JSONB NOT NULL,              -- Full recommendation payload
  outfit_count INTEGER,
  
  -- Interaction
  clicked_product TEXT,                         -- Which product they clicked
  added_to_cart TEXT,                           -- Which product they added
  purchased BOOLEAN DEFAULT false,
  
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_reco_user ON mn_recommendation_history(user_id);
CREATE INDEX idx_reco_created ON mn_recommendation_history(created_at);

-- ============================================
-- 10. USER PREFERENCES (key-value for flexibility)
-- ============================================
CREATE TABLE IF NOT EXISTS mn_user_preferences (
  user_id TEXT NOT NULL REFERENCES mn_user_profiles(user_id),
  pref_key TEXT NOT NULL,
  pref_value JSONB,
  updated_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (user_id, pref_key)
);

-- ============================================
-- RPC FUNCTIONS
-- ============================================

-- Get or create user profile
CREATE OR REPLACE FUNCTION get_or_create_user(
  p_user_id TEXT,
  p_email TEXT DEFAULT NULL,
  p_display_name TEXT DEFAULT NULL,
  p_gender TEXT DEFAULT NULL
)
RETURNS JSONB AS $$
DECLARE
  result JSONB;
BEGIN
  -- Try to get existing
  SELECT to_jsonb(up.*) INTO result
  FROM mn_user_profiles up
  WHERE up.user_id = p_user_id;
  
  -- Create if not exists
  IF result IS NULL THEN
    INSERT INTO mn_user_profiles (user_id, email, display_name, gender)
    VALUES (p_user_id, p_email, p_display_name, p_gender)
    RETURNING to_jsonb(mn_user_profiles.*) INTO result;
  END IF;
  
  -- Update last_active
  UPDATE mn_user_profiles SET last_active_at = now() WHERE user_id = p_user_id;
  
  RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Get user's saved cards with offer matching
CREATE OR REPLACE FUNCTION get_user_cards_with_offers(
  p_user_id TEXT
)
RETURNS TABLE (
  card_id TEXT,
  bank_name TEXT,
  card_type TEXT,
  card_variant TEXT,
  card_network TEXT,
  active_offers BIGINT
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    sc.card_id,
    sc.bank_name,
    sc.card_type,
    sc.card_variant,
    sc.card_network,
    COUNT(mo.offer_id) as active_offers
  FROM mn_saved_cards sc
  LEFT JOIN mn_merchant_offers mo ON 
    mo.bank_name = sc.bank_name
    AND (mo.card_type = sc.card_type OR mo.card_type = 'both')
    AND (mo.card_variants = '{}' OR sc.card_variant = ANY(mo.card_variants))
    AND mo.is_active = true
    AND (mo.valid_until IS NULL OR mo.valid_until > now())
  WHERE sc.user_id = p_user_id
  GROUP BY sc.card_id, sc.bank_name, sc.card_type, sc.card_variant, sc.card_network
  ORDER BY sc.is_primary DESC, sc.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Calculate best price for a product with user's cards
CREATE OR REPLACE FUNCTION calculate_best_price(
  p_product_price NUMERIC,
  p_merchant_name TEXT,
  p_category TEXT,
  p_user_id TEXT
)
RETURNS TABLE (
  original_price NUMERIC,
  best_price NUMERIC,
  discount NUMERIC,
  offer_description TEXT,
  card_used TEXT
) AS $$
DECLARE
  best_offer_record RECORD;
  calculated_price NUMERIC;
  offer_discount NUMERIC;
BEGIN
  original_price := p_product_price;
  best_price := p_product_price;
  discount := 0;
  offer_description := NULL;
  card_used := NULL;
  
  -- Find best applicable offer
  FOR best_offer_record IN
    SELECT 
      mo.*,
      sc.card_variant,
      sc.card_id
    FROM mn_saved_cards sc
    JOIN mn_merchant_offers mo ON 
      mo.bank_name = sc.bank_name
      AND (mo.card_type = sc.card_type OR mo.card_type = 'both')
      AND (mo.card_variants = '{}' OR sc.card_variant = ANY(mo.card_variants))
      AND mo.is_active = true
      AND (mo.valid_until IS NULL OR mo.valid_until > now())
      AND (mo.merchant_name = p_merchant_name OR p_merchant_name = '')
      AND (mo.applicable_categories = '{}' OR p_category = ANY(mo.applicable_categories))
      AND (mo.min_purchase IS NULL OR p_product_price >= mo.min_purchase)
    WHERE sc.user_id = p_user_id
    ORDER BY mo.discount_value DESC
    LIMIT 1
  LOOP
    -- Calculate discount
    IF best_offer_record.discount_type = 'percentage' THEN
      offer_discount := p_product_price * best_offer_record.discount_value / 100;
    ELSE
      offer_discount := best_offer_record.discount_value;
    END IF;
    
    -- Apply max discount cap
    IF best_offer_record.max_discount IS NOT NULL AND offer_discount > best_offer_record.max_discount THEN
      offer_discount := best_offer_record.max_discount;
    END IF;
    
    calculated_price := p_product_price - offer_discount;
    
    -- Update if this is better
    IF calculated_price < best_price THEN
      best_price := calculated_price;
      discount := offer_discount;
      offer_description := best_offer_record.discount_value || '% OFF via ' || best_offer_record.bank_name || ' ' || best_offer_record.card_variant;
      card_used := best_offer_record.bank_name || ' ' || best_offer_record.card_variant;
    END IF;
  END LOOP;
  
  RETURN NEXT;
END;
$$ LANGUAGE plpgsql;
