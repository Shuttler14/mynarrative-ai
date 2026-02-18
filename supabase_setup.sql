-- ========================================
-- SUPABASE DATABASE SETUP FOR DIGITAL TWIN
-- ========================================
-- Run this SQL in your Supabase SQL Editor
-- Dashboard > SQL Editor > New Query > Paste & Run

-- 1. CREATE PROFILES TABLE
-- Stores user's Digital Twin (master photo)
CREATE TABLE IF NOT EXISTS profiles (
  id TEXT PRIMARY KEY,  -- Shopify Customer ID
  twin_photo_url TEXT,  -- URL to master photo in storage
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Allow users to read/write their own profile
CREATE POLICY "Users can manage own profile"
  ON profiles
  FOR ALL
  USING (id = current_setting('request.jwt.claims')::json->>'sub');

-- 2. CREATE CLOSET_ITEMS TABLE
-- Stores individual wardrobe items
CREATE TABLE IF NOT EXISTS closet_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,  -- Shopify Customer ID
  image_url TEXT NOT NULL,  -- URL to item photo
  category TEXT,  -- 'tops', 'bottoms', 'shoes', 'accessories'
  color TEXT,  -- 'red', 'blue', etc.
  tags TEXT[],  -- ['casual', 'summer', 'work']
  created_at TIMESTAMP DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE closet_items ENABLE ROW LEVEL SECURITY;

-- Allow users to manage their own items
CREATE POLICY "Users can manage own closet items"
  ON closet_items
  FOR ALL
  USING (user_id = current_setting('request.jwt.claims')::json->>'sub');

-- 3. CREATE STORAGE BUCKETS
-- NOTE: You need to create these buckets in the Supabase Dashboard
-- Dashboard > Storage > Create Bucket

-- Bucket 1: digital-twins (for master photos)
-- Bucket 2: closet (for wardrobe items)

-- After creating buckets, set their policies:

-- Policy for digital-twins bucket:
-- Name: "Public read access"
-- SQL:
CREATE POLICY "Public read access for digital twins"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'digital-twins');

-- Policy for closet bucket:
CREATE POLICY "Public read access for closet items"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'closet');

-- Policy to allow authenticated users to upload to their folder:
CREATE POLICY "Users can upload to own folder in digital-twins"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'digital-twins' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can upload to own folder in closet"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'closet' AND auth.uid()::text = (storage.foldername(name))[1]);

-- ========================================
-- VERIFICATION QUERIES
-- ========================================
-- Run these to verify setup:

-- Check if tables exist:
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('profiles', 'closet_items');

-- Check if buckets exist:
SELECT * FROM storage.buckets WHERE name IN ('digital-twins', 'closet');

-- ========================================
-- DONE! 
-- ========================================
-- Next Steps:
-- 1. Copy your Supabase URL and Key from Settings > API
-- 2. Add to Vercel environment variables:
--    SUPABASE_URL=https://xxxxx.supabase.co
--    SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
