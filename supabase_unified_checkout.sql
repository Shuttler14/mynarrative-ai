-- ============================================
-- MY NARRATIVE — Unified Checkout System
-- ============================================

-- 1. User addresses (saved for checkout)
CREATE TABLE IF NOT EXISTS narrative_addresses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  label TEXT DEFAULT 'Home',
  full_name TEXT NOT NULL,
  phone TEXT NOT NULL,
  address_line1 TEXT NOT NULL,
  address_line2 TEXT,
  city TEXT NOT NULL,
  state TEXT NOT NULL,
  pincode TEXT NOT NULL,
  country TEXT DEFAULT 'IN',
  is_default BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_narrative_addresses_user ON narrative_addresses(user_id);

-- 2. Shopping cart (server-side, cross-brand)
CREATE TABLE IF NOT EXISTS narrative_cart (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  session_id TEXT,
  brand_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  variant_id TEXT,
  title TEXT NOT NULL,
  image_url TEXT,
  price NUMERIC(10,2) NOT NULL,
  compare_at_price NUMERIC(10,2),
  quantity INTEGER DEFAULT 1,
  size TEXT,
  color TEXT,
  category TEXT,
  product_url TEXT,
  added_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_narrative_cart_user ON narrative_cart(user_id);
CREATE INDEX idx_narrative_cart_session ON narrative_cart(session_id);
CREATE UNIQUE INDEX idx_narrative_cart_unique ON narrative_cart(user_id, product_id, variant_id);

-- 3. Orders (unified, multi-brand)
CREATE TABLE IF NOT EXISTS narrative_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_number TEXT UNIQUE NOT NULL,
  user_id TEXT NOT NULL,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded')),
  subtotal NUMERIC(10,2) NOT NULL,
  shipping_fee NUMERIC(10,2) DEFAULT 0,
  tax NUMERIC(10,2) DEFAULT 0,
  discount NUMERIC(10,2) DEFAULT 0,
  total NUMERIC(10,2) NOT NULL,
  currency TEXT DEFAULT 'INR',
  address_id UUID REFERENCES narrative_addresses(id),
  address_snapshot JSONB,
  payment_id TEXT,
  payment_method TEXT DEFAULT 'razorpay',
  payment_status TEXT DEFAULT 'pending' CHECK (payment_status IN ('pending', 'authorized', 'captured', 'failed', 'refunded')),
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_narrative_orders_user ON narrative_orders(user_id);
CREATE INDEX idx_narrative_orders_status ON narrative_orders(status);

-- 4. Order items (per brand, for routing)
CREATE TABLE IF NOT EXISTS narrative_order_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES narrative_orders(id) ON DELETE CASCADE,
  brand_id TEXT NOT NULL,
  brand_name TEXT,
  product_id TEXT NOT NULL,
  variant_id TEXT,
  title TEXT NOT NULL,
  image_url TEXT,
  price NUMERIC(10,2) NOT NULL,
  quantity INTEGER DEFAULT 1,
  size TEXT,
  color TEXT,
  category TEXT,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded')),
  brand_order_id TEXT,
  brand_tracking_url TEXT,
  commission_rate NUMERIC(5,2) DEFAULT 10.00,
  commission_amount NUMERIC(10,2) DEFAULT 0,
  brand_payout NUMERIC(10,2) DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_narrative_order_items_order ON narrative_order_items(order_id);
CREATE INDEX idx_narrative_order_items_brand ON narrative_order_items(brand_id);

-- 5. Payments ( Razorpay + splits)
CREATE TABLE IF NOT EXISTS narrative_payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES narrative_orders(id),
  razorpay_payment_id TEXT,
  razorpay_order_id TEXT,
  razorpay_signature TEXT,
  amount NUMERIC(10,2) NOT NULL,
  currency TEXT DEFAULT 'INR',
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'authorized', 'captured', 'failed', 'refunded')),
  method TEXT,
  fee NUMERIC(10,2) DEFAULT 0,
  net_amount NUMERIC(10,2) DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_narrative_payments_order ON narrative_payments(order_id);
CREATE INDEX idx_narrative_payments_razorpay ON narrative_payments(razorpay_payment_id);

-- 6. Commission ledger (immutable)
CREATE TABLE IF NOT EXISTS narrative_commissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES narrative_orders(id),
  order_item_id UUID NOT NULL REFERENCES narrative_order_items(id),
  brand_id TEXT NOT NULL,
  gross_amount NUMERIC(10,2) NOT NULL,
  commission_rate NUMERIC(5,2) NOT NULL,
  commission_amount NUMERIC(10,2) NOT NULL,
  platform_fee NUMERIC(10,2) NOT NULL,
  brand_payout NUMERIC(10,2) NOT NULL,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'paid', 'refunded')),
  paid_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_narrative_commissions_order ON narrative_commissions(order_id);
CREATE INDEX idx_narrative_commissions_brand ON narrative_commissions(brand_id);

-- 7. Brand payout tracking
CREATE TABLE IF NOT EXISTS narrative_brand_payouts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id TEXT NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  method TEXT DEFAULT 'bank_transfer',
  reference TEXT,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  processed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_narrative_brand_payouts_brand ON narrative_brand_payouts(brand_id);

-- 8. Cart sessions (for anonymous users)
CREATE TABLE IF NOT EXISTS narrative_cart_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT UNIQUE NOT NULL,
  user_id TEXT,
  fingerprint TEXT,
  cart_data JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT now(),
  expires_at TIMESTAMPTZ DEFAULT (now() + INTERVAL '7 days')
);

CREATE INDEX idx_narrative_cart_sessions_id ON narrative_cart_sessions(session_id);

-- RPC: Merge anonymous cart into user cart
CREATE OR REPLACE FUNCTION merge_cart_to_user(p_session_id TEXT, p_user_id TEXT)
RETURNS void AS $$
BEGIN
  -- Update anonymous cart items with user_id
  UPDATE narrative_cart
  SET user_id = p_user_id, session_id = NULL
  WHERE session_id = p_session_id;

  -- Delete session
  DELETE FROM narrative_cart_sessions WHERE session_id = p_session_id;
END;
$$ LANGUAGE plpgsql;

-- RPC: Generate unique order number
CREATE OR REPLACE FUNCTION generate_order_number()
RETURNS TEXT AS $$
DECLARE
  seq TEXT;
BEGIN
  seq := 'MN-' || TO_CHAR(now(), 'YYYYMMDD') || '-' || LPAD(FLOOR(RANDOM() * 9999)::TEXT, 4, '0');
  RETURN seq;
END;
$$ LANGUAGE plpgsql;
