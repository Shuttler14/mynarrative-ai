-- ============================================================
-- DTF pipeline columns for design_orders
-- Safe to run more than once.
-- ============================================================

ALTER TABLE IF EXISTS design_orders
  ADD COLUMN IF NOT EXISTS dtf_status TEXT DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS print_file_url TEXT,
  ADD COLUMN IF NOT EXISTS print_file_key TEXT,
  ADD COLUMN IF NOT EXISTS dtf_processed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS dtf_error TEXT;

CREATE INDEX IF NOT EXISTS idx_design_orders_dtf_status
  ON design_orders(dtf_status);

CREATE INDEX IF NOT EXISTS idx_design_orders_print_file_key
  ON design_orders(print_file_key);
