-- OTP table for auth flow
-- Run in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS mn_otp_codes (
  id SERIAL PRIMARY KEY,
  email TEXT NOT NULL,
  otp_code TEXT NOT NULL,
  is_used BOOLEAN DEFAULT false,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mn_otp_email
  ON mn_otp_codes(email, is_used, created_at DESC);

-- Auto-cleanup old OTPs
CREATE OR REPLACE FUNCTION cleanup_old_otps()
RETURNS void AS $$
BEGIN
  DELETE FROM mn_otp_codes WHERE created_at < now() - interval '1 hour';
END;
$$ LANGUAGE plpgsql;
