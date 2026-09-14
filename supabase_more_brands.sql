-- ═════════════════════════════════════════════════════════════════════════════
-- ADD MORE BRANDS AND PRODUCTS
-- Run this on fmganuxtqbquubtvvqdo Supabase project
-- ═════════════════════════════════════════════════════════════════════════════

-- ── Brand: H&M ──────────────────────────────────────────────────────────────
INSERT INTO brand_catalogs (id, brand_name, brand_slug, description, website_url, logo_url, is_active, subscription_tier, monthly_fee_inr, commission_rate)
VALUES (
  'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  'H&M',
  'hm',
  'Affordable fashion for everyone',
  'https://www.hm.com',
  'https://logo.clearbit.com/hm.com',
  true,
  'growth',
  15000,
  0.08
) ON CONFLICT (brand_slug) DO NOTHING;

-- H&M Products - Men
INSERT INTO brand_products (catalog_id, external_id, brand, title, description, price, currency, image_url, category, subcategory, tags, sizes, colors, material, gender, is_active)
SELECT
  'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  p.external_id, 'H&M', p.title, p.description, p.price, 'INR', p.image_url, p.category, p.subcategory, p.tags, p.sizes, p.colors, p.material, p.gender, true
FROM (VALUES
  ('hm-001', 'Slim Fit Oxford Shirt', 'Classic cotton oxford shirt with slim fit', 1499.0, 'https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=400', 'topwear', 'shirts', '["casual","smart-casual","work"]', '["S","M","L","XL","XXL"]', '["white","blue","pink"]', 'cotton', 'men'),
  ('hm-002', 'Regular Fit Chinos', 'Comfortable chinos for everyday wear', 1799.0, 'https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=400', 'bottomwear', 'chinos', '["casual","smart-casual"]', '["28","30","32","34","36"]', '["khaki","navy","olive"]', 'cotton', 'men'),
  ('hm-003', 'Premium Cotton T-Shirt', 'Essential crew neck t-shirt', 699.0, 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400', 'topwear', 't-shirts', '["casual","loungewear"]', '["S","M","L","XL"]', '["white","black","grey"]', 'cotton', 'men'),
  ('hm-004', 'Linen Blend Shorts', 'Relaxed fit linen shorts', 1299.0, 'https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=400', 'bottomwear', 'shorts', '["casual","summer"]', '["S","M","L","XL"]', '["beige","white","blue"]', 'linen', 'men'),
  ('hm-005', 'Oversized Hoodie', 'Warm fleece hoodie with oversized fit', 2499.0, 'https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=400', 'topwear', 'hoodies', '["casual","streetwear"]', '["S","M","L","XL","XXL"]', '["black","grey","forest"]', 'cotton', 'men')
) AS p(external_id, title, description, price, image_url, category, subcategory, tags, sizes, colors, material, gender)
WHERE NOT EXISTS (SELECT 1 FROM brand_products WHERE external_id = p.external_id);

-- H&M Products - Women
INSERT INTO brand_products (catalog_id, external_id, brand, title, description, price, currency, image_url, category, subcategory, tags, sizes, colors, material, gender, is_active)
SELECT
  'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  p.external_id, 'H&M', p.title, p.description, p.price, 'INR', p.image_url, p.category, p.subcategory, p.tags, p.sizes, p.colors, p.material, p.gender, true
FROM (VALUES
  ('hm-006', 'Midi Wrap Dress', 'Elegant wrap dress in soft viscose', 2999.0, 'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=400', 'dresses', 'midi', '["party","work","date"]', '["XS","S","M","L","XL"]', '["red","black","floral"]', 'viscose', 'women'),
  ('hm-007', 'High-Waist Mom Jeans', 'Classic mom jeans with high waist', 2299.0, 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=400', 'bottomwear', 'jeans', '["casual","streetwear"]', '["24","26","28","30"]', '["blue","black","light-blue"]', 'denim', 'women'),
  ('hm-008', 'Ribbed Knit Top', 'Fitted ribbed top with crew neck', 899.0, 'https://images.unsplash.com/photo-1485462537746-965f33f7f6a7?w=400', 'topwear', 'tops', '["casual","layering"]', '["XS","S","M","L"]', '["white","black","beige"]', 'cotton', 'women'),
  ('hm-009', 'Pleated Midi Skirt', 'Flowy pleated skirt for elegant looks', 1999.0, 'https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?w=400', 'bottomwear', 'skirts', '["party","work","brunch"]', '["XS","S","M","L"]', '["black","emerald","rose"]', 'polyester', 'women'),
  ('hm-010', 'Oversized Blazer', 'Relaxed fit blazer for layering', 3499.0, 'https://images.unsplash.com/photo-1591369822096-ffd140ec948f?w=400', 'topwear', 'blazers', '["work","smart-casual","party"]', '["XS","S","M","L","XL"]', '["black","camel","grey"]', 'polyester', 'women')
) AS p(external_id, title, description, price, image_url, category, subcategory, tags, sizes, colors, material, gender)
WHERE NOT EXISTS (SELECT 1 FROM brand_products WHERE external_id = p.external_id);

-- ── Brand: Nike ──────────────────────────────────────────────────────────────
INSERT INTO brand_catalogs (id, brand_name, brand_slug, description, website_url, logo_url, is_active, subscription_tier, monthly_fee_inr, commission_rate)
VALUES (
  'b2c3d4e5-f6a7-8901-bcde-f12345678901',
  'Nike',
  'nike',
  'Just Do It - Athletic & lifestyle footwear and apparel',
  'https://www.nike.com',
  'https://logo.clearbit.com/nike.com',
  true,
  'enterprise',
  25000,
  0.10
) ON CONFLICT (brand_slug) DO NOTHING;

-- Nike Products - Men
INSERT INTO brand_products (catalog_id, external_id, brand, title, description, price, currency, image_url, category, subcategory, tags, sizes, colors, material, gender, is_active)
SELECT
  'b2c3d4e5-f6a7-8901-bcde-f12345678901',
  p.external_id, 'Nike', p.title, p.description, p.price, 'INR', p.image_url, p.category, p.subcategory, p.tags, p.sizes, p.colors, p.material, p.gender, true
FROM (VALUES
  ('nike-001', 'Air Max 270', 'Iconic Air Max cushioning for all-day comfort', 12995.0, 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400', 'footwear', 'sneakers', '["casual","sport","streetwear"]', '["UK6","UK7","UK8","UK9","UK10","UK11"]', '["black","white","red"]', 'mesh', 'men'),
  ('nike-002', 'Dri-FIT Running Shorts', 'Lightweight running shorts with moisture-wicking', 2495.0, 'https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=400', 'bottomwear', 'shorts', '["sport","running","gym"]', '["S","M","L","XL"]', '["black","grey","blue"]', 'polyester', 'men'),
  ('nike-003', 'Tech Fleece Joggers', 'Premium joggers with Tech Fleece warmth', 6995.0, 'https://images.unsplash.com/photo-1552902865-b72c031ac5ea?w=400', 'bottomwear', 'joggers', '["casual","sport","streetwear"]', '["S","M","L","XL","XXL"]', '["black","grey","olive"]', 'fleece', 'men'),
  ('nike-004', 'Sportswear T-Shirt', 'Classic Nike tee with Swoosh logo', 2295.0, 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400', 'topwear', 't-shirts', '["casual","sport"]', '["S","M","L","XL","XXL"]', '["white","black","grey"]', 'cotton', 'men'),
  ('nike-005', 'Air Force 1 Low', 'Timeless Air Force 1 silhouette', 8195.0, 'https://images.unsplash.com/photo-1600269452121-4f2416e55c28?w=400', 'footwear', 'sneakers', '["casual","streetwear","sport"]', '["UK6","UK7","UK8","UK9","UK10"]', '["white","black","white-black"]', 'leather', 'men'),
  ('nike-006', 'Pro Training Tank', 'Breathable tank for intense workouts', 1995.0, 'https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?w=400', 'topwear', 'tank-tops', '["sport","gym","training"]', '["S","M","L","XL"]', '["black","white","grey"]', 'polyester', 'men')
) AS p(external_id, title, description, price, image_url, category, subcategory, tags, sizes, colors, material, gender)
WHERE NOT EXISTS (SELECT 1 FROM brand_products WHERE external_id = p.external_id);

-- Nike Products - Women
INSERT INTO brand_products (catalog_id, external_id, brand, title, description, price, currency, image_url, category, subcategory, tags, sizes, colors, material, gender, is_active)
SELECT
  'b2c3d4e5-f6a7-8901-bcde-f12345678901',
  p.external_id, 'Nike', p.title, p.description, p.price, 'INR', p.image_url, p.category, p.subcategory, p.tags, p.sizes, p.colors, p.material, p.gender, true
FROM (VALUES
  ('nike-007', 'Air Zoom Pegasus', 'Responsive running shoe with Zoom Air', 11895.0, 'https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=400', 'footwear', 'sneakers', '["sport","running","casual"]', '["UK3","UK4","UK5","UK6","UK7","UK8"]', '["pink","black","white"]', 'mesh', 'women'),
  ('nike-008', 'Yoga Sports Bra', 'Medium-support sports bra for yoga', 2995.0, 'https://images.unsplash.com/photo-1518310383802-640c2de311b2?w=400', 'topwear', 'sports-bras', '["sport","yoga","gym"]', '["XS","S","M","L"]', '["black","pink","lavender"]', 'nylon', 'women'),
  ('nike-009', 'Leggings with Pockets', 'High-waist leggings with side pockets', 4495.0, 'https://images.unsplash.com/photo-1506629082955-511b1aa562c8?w=400', 'bottomwear', 'leggings', '["sport","yoga","casual"]', '["XS","S","M","L","XL"]', '["black","grey","olive"]', 'nylon', 'women'),
  ('nike-010', 'Dri-FIT Adv Top', 'Premium training top with Dri-FIT', 3495.0, 'https://images.unsplash.com/photo-1485462537746-965f33f7f6a7?w=400', 'topwear', 'tops', '["sport","training","gym"]', '["XS","S","M","L"]', '["black","white","coral"]', 'polyester', 'women'),
  ('nike-011', 'Blazer Mid Vintage', 'Retro basketball-inspired sneaker', 8695.0, 'https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=400', 'footwear', 'sneakers', '["casual","streetwear","vintage"]', '["UK3","UK4","UK5","UK6","UK7"]', '["white","black","green"]', 'leather', 'women')
) AS p(external_id, title, description, price, image_url, category, subcategory, tags, sizes, colors, material, gender)
WHERE NOT EXISTS (SELECT 1 FROM brand_products WHERE external_id = p.external_id);

-- ── Brand: Sabyasachi (Luxury Indian) ───────────────────────────────────────
INSERT INTO brand_catalogs (id, brand_name, brand_slug, description, website_url, logo_url, is_active, subscription_tier, monthly_fee_inr, commission_rate)
VALUES (
  'c3d4e5f6-a7b8-9012-cdef-123456789012',
  'Sabyasachi',
  'sabyasachi',
  'Luxury Indian couture and bridal wear',
  'https://www.sabyasachi.com',
  'https://logo.clearbit.com/sabyasachi.com',
  true,
  'enterprise',
  50000,
  0.12
) ON CONFLICT (brand_slug) DO NOTHING;

-- Sabyasachi Products
INSERT INTO brand_products (catalog_id, external_id, brand, title, description, price, currency, image_url, category, subcategory, tags, sizes, colors, material, gender, is_active)
SELECT
  'c3d4e5f6-a7b8-9012-cdef-123456789012',
  p.external_id, 'Sabyasachi', p.title, p.description, p.price, 'INR', p.image_url, p.category, p.subcategory, p.tags, p.sizes, p.colors, p.material, p.gender, true
FROM (VALUES
  ('sab-001', 'Embroidered Anarkali', 'Hand-embroidered anarkali suit with intricate zardozi work', 85000.0, 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=400', 'dresses', 'anarkali', '["wedding","festive","party"]', '["S","M","L","XL"]', '["gold","maroon","emerald"]', 'silk', 'women'),
  ('sab-002', 'Brocade Sherwani', 'Opulent brocade sherwani for grooms', 125000.0, 'https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=400', 'ethnic', 'sherwani', '["wedding","festive","formal"]', '["38","40","42","44","46"]', '["gold","cream","royal-blue"]', 'silk', 'men'),
  ('sab-003', 'Lehenga Choli', 'Bridal lehenga with heavy embroidery', 195000.0, 'https://images.unsplash.com/photo-1585143420413-f81c7d1f8b4a?w=400', 'ethnic', 'lehenga', '["wedding","bridal"]', '["S","M","L"]', '["red","pink","gold"]', 'silk', 'women'),
  ('sab-004', 'Silk Saree with Blouse', 'Pure silk saree with embroidered blouse', 45000.0, 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=400', 'ethnic', 'saree', '["wedding","festive","formal"]', '["free-size"]', '["red","green","blue"]', 'silk', 'women'),
  ('sab-005', 'Printed Cotton Kurta', 'Hand-printed cotton kurta for men', 12000.0, 'https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=400', 'ethnic', 'kurta', '["casual","festive","work"]', '["S","M","L","XL","XXL"]', '["white","blue","green"]', 'cotton', 'men')
) AS p(external_id, title, description, price, image_url, category, subcategory, tags, sizes, colors, material, gender)
WHERE NOT EXISTS (SELECT 1 FROM brand_products WHERE external_id = p.external_id);

-- ── Brand: Allen Solly (Mid-range) ──────────────────────────────────────────
INSERT INTO brand_catalogs (id, brand_name, brand_slug, description, website_url, logo_url, is_active, subscription_tier, monthly_fee_inr, commission_rate)
VALUES (
  'd4e5f6a7-b8c9-0123-defa-234567890123',
  'Allen Solly',
  'allen-solly',
  'Smart casual and workwear for professionals',
  'https://www.allensolly.com',
  'https://logo.clearbit.com/allensolly.com',
  true,
  'starter',
  8000,
  0.07
) ON CONFLICT (brand_slug) DO NOTHING;

-- Allen Solly Products
INSERT INTO brand_products (catalog_id, external_id, brand, title, description, price, currency, image_url, category, subcategory, tags, sizes, colors, material, gender, is_active)
SELECT
  'd4e5f6a7-b8c9-0123-defa-234567890123',
  p.external_id, 'Allen Solly', p.title, p.description, p.price, 'INR', p.image_url, p.category, p.subcategory, p.tags, p.sizes, p.colors, p.material, p.gender, true
FROM (VALUES
  ('as-001', 'Slim Fit Formal Shirt', 'Premium cotton formal shirt', 2499.0, 'https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=400', 'topwear', 'shirts', '["work","formal","smart-casual"]', '["38","40","42","44"]', '["white","blue","pink"]', 'cotton', 'men'),
  ('as-002', 'Tailored Fit Trousers', 'Classic tailored trousers for work', 2999.0, 'https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=400', 'bottomwear', 'trousers', '["work","formal"]', '["28","30","32","34","36"]', '["black","navy","grey"]', 'polyester', 'men'),
  ('as-003', 'Polo T-Shirt', 'Classic polo with collar', 1799.0, 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400', 'topwear', 'polos', '["casual","smart-casual","work"]', '["S","M","L","XL","XXL"]', '["white","navy","red"]', 'cotton', 'men'),
  ('as-004', 'A-Line Midi Dress', 'Professional midi dress for work', 3999.0, 'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=400', 'dresses', 'midi', '["work","smart-casual","brunch"]', '["XS","S","M","L"]', '["black","navy","wine"]', 'polyester', 'women'),
  ('as-005', 'Straight Fit Jeans', 'Classic straight fit denim', 2799.0, 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=400', 'bottomwear', 'jeans', '["casual","work-casual"]', '["28","30","32","34","36"]', '["blue","black"]', 'denim', 'men'),
  ('as-006', 'Printed Kurta Set', 'Indo-western kurta with trousers', 4499.0, 'https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=400', 'ethnic', 'kurta-set', '["festive","casual","work"]', '["S","M","L","XL"]', '["blue","green","maroon"]', 'cotton', 'men')
) AS p(external_id, title, description, price, image_url, category, subcategory, tags, sizes, colors, material, gender)
WHERE NOT EXISTS (SELECT 1 FROM brand_products WHERE external_id = p.external_id);

-- ── Brand: FabIndia (Indian Ethnic) ─────────────────────────────────────────
INSERT INTO brand_catalogs (id, brand_name, brand_slug, description, website_url, logo_url, is_active, subscription_tier, monthly_fee_inr, commission_rate)
VALUES (
  'e5f6a7b8-c9d0-1234-efab-345678901234',
  'FabIndia',
  'fabindia',
  'Handcrafted Indian textiles and ethnic wear',
  'https://www.fabindia.com',
  'https://logo.clearbit.com/fabindia.com',
  true,
  'growth',
  12000,
  0.08
) ON CONFLICT (brand_slug) DO NOTHING;

-- FabIndia Products
INSERT INTO brand_products (catalog_id, external_id, brand, title, description, price, currency, image_url, category, subcategory, tags, sizes, colors, material, gender, is_active)
SELECT
  'e5f6a7b8-c9d0-1234-efab-345678901234',
  p.external_id, 'FabIndia', p.title, p.description, p.price, 'INR', p.image_url, p.category, p.subcategory, p.tags, p.sizes, p.colors, p.material, p.gender, true
FROM (VALUES
  ('fab-001', 'Block Print Cotton Kurta', 'Hand block-printed cotton kurta', 2490.0, 'https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=400', 'ethnic', 'kurta', '["casual","festive","work"]', '["S","M","L","XL","XXL"]', '["indigo","white","green"]', 'cotton', 'men'),
  ('fab-002', 'Chanderi Silk Saree', 'Elegant chanderi silk with zari border', 8990.0, 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=400', 'ethnic', 'saree', '["festive","formal","wedding"]', '["free-size"]', '["gold","cream","pink"]', 'silk', 'women'),
  ('fab-003', 'Handwoven Linen Shirt', 'Breathable handwoven linen shirt', 3290.0, 'https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=400', 'topwear', 'shirts', '["casual","smart-casual"]', '["S","M","L","XL"]', '["white","beige","blue"]', 'linen', 'men'),
  ('fab-004', 'Embroidered Cotton Dupatta', 'Hand-embroidered cotton dupatta', 1990.0, 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=400', 'accessories', 'dupatta', '["festive","ethnic","layering"]', '["free-size"]', '["multi","pink","blue"]', 'cotton', 'women'),
  ('fab-005', 'Khadi Cotton Pants', 'Comfortable handspun khadi pants', 2190.0, 'https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=400', 'bottomwear', 'pants', '["casual","work","ethnic"]', '["28","30","32","34"]', '["white","grey","brown"]', 'cotton', 'men'),
  ('fab-006', 'Angrakha Style Top', 'Traditional angrakha with modern fit', 3490.0, 'https://images.unsplash.com/photo-1485462537746-965f33f7f6a7?w=400', 'ethnic', 'top', '["festive","casual","boho"]', '["XS","S","M","L"]', '["red","yellow","blue"]', 'cotton', 'women')
) AS p(external_id, title, description, price, image_url, category, subcategory, tags, sizes, colors, material, gender)
WHERE NOT EXISTS (SELECT 1 FROM brand_products WHERE external_id = p.external_id);

-- ── Verify counts ───────────────────────────────────────────────────────────
SELECT brand_name, 
       (SELECT COUNT(*) FROM brand_products WHERE catalog_id = brand_catalogs.id) as product_count
FROM brand_catalogs 
WHERE is_active = true
ORDER BY brand_name;
