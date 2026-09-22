-- Migration: Add Shopify Customer ID support
-- Run in Supabase SQL Editor

-- Add shopify_customer_id column to mn_user_profiles
ALTER TABLE mn_user_profiles
  ADD COLUMN IF NOT EXISTS shopify_customer_id TEXT UNIQUE;

CREATE INDEX IF NOT EXISTS idx_mn_user_profiles_shopify_id
  ON mn_user_profiles(shopify_customer_id);

-- Drop the OTP table (no longer needed)
DROP TABLE IF EXISTS mn_otp_codes;
