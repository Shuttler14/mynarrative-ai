-- Seed: Merchant × Bank Offers (realistic Indian market, Sep 2026)
-- Run AFTER supabase_offer_engine.sql

INSERT INTO mn_offers (offer_id, merchant_name, bank_name, card_type, card_variants, discount_type, discount_value, max_discount, min_purchase, transaction_types, applicable_categories, valid_from, valid_until, terms, bank_verified, merchant_verified, confidence_score, state) VALUES

-- Myntra offers
('OFF_MYN_001', 'Myntra', 'HDFC', 'credit', '{HDFC Regalia,HDFC Millennia,HDFC Infinia}', 'percentage', 10, 750, 3499, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% instant discount up to ₹750 on min txn of ₹3,499. Valid on HDFC credit cards.', true, true, 0.95, 'active'),
('OFF_MYN_002', 'Myntra', 'SBI', 'credit', '{SBI SimplyCLICK,SBI Prime,SBI Elite}', 'percentage', 10, 500, 2999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500 on min spend ₹2,999 with SBI credit cards.', true, true, 0.93, 'active'),
('OFF_MYN_003', 'Myntra', 'ICICI', 'credit', '{ICICI Amazon Pay,ICICI Coral,ICICI Sapphiro}', 'percentage', 10, 1000, 4999, '{non_emi}', '{fashion}', '2026-09-05', '2026-09-30', '10% instant discount up to ₹1,000. Min order ₹4,999. ICICI Bank credit cards only.', true, true, 0.92, 'active'),
('OFF_MYN_004', 'Myntra', 'Axis', 'credit', '{Axis Flipkart Axis,Axis Magnus,Axis Neo}', 'percentage', 10, 500, 2499, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500 on min ₹2,499. Axis Bank credit cards.', true, true, 0.90, 'active'),
('OFF_MYN_005', 'Myntra', 'Kotak', 'credit', '{Kotak 811,Kotak Royale Signature}', 'percentage', 10, 400, 1999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% instant discount up to ₹400. Min transaction ₹1,999.', true, true, 0.88, 'active'),
('OFF_MYN_006', 'Myntra', 'IDFC FIRST', 'credit', '{IDFC FIRST Wealth,IDFC FIRST Select}', 'percentage', 10, 600, 3499, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹600 on min ₹3,499. IDFC FIRST Bank credit cards.', true, false, 0.85, 'active'),
('OFF_MYN_007', 'Myntra', 'IndusInd', 'credit', '{IndusInd Legend,IndusInd Pinnacle}', 'percentage', 10, 500, 2999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500 on min ₹2,999.', true, false, 0.83, 'active'),
('OFF_MYN_008', 'Myntra', 'RBL', 'credit', '{RBL Shoprite,RBL Popcorn+}', 'percentage', 10, 300, 1999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹300 on min ₹1,999.', true, false, 0.82, 'active'),

-- Amazon offers
('OFF_AMZ_001', 'Amazon', 'HDFC', 'credit', '{HDFC Regalia,HDFC Millennia,HDFC Infinia,HDFC MoneyBack+}', 'percentage', 10, 1000, 5000, '{non_emi}', '{electronics,fashion,home}', '2026-09-01', '2026-09-30', '10% instant discount up to ₹1,000 on min ₹5,000. HDFC credit cards on Amazon.', true, true, 0.96, 'active'),
('OFF_AMZ_002', 'Amazon', 'ICICI', 'credit', '{ICICI Amazon Pay,ICICI Coral}', 'percentage', 5, 200, 1000, '{non_emi,emi}', '{all}', '2026-09-01', '2026-09-30', '5% back as Amazon Pay balance on ICICI Amazon Pay card. No min order.', true, true, 0.97, 'active'),
('OFF_AMZ_003', 'Amazon', 'SBI', 'credit', '{SBI SimplyCLICK,SBI Prime}', 'percentage', 10, 500, 3000, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500 on fashion. Min ₹3,000.', true, true, 0.91, 'active'),
('OFF_AMZ_004', 'Amazon', 'Axis', 'credit', '{Axis Flipkart Axis}', 'percentage', 5, 200, 1000, '{non_emi}', '{all}', '2026-09-01', '2026-09-30', '5% unlimited cashback on Axis Flipkart Axis card.', true, true, 0.94, 'active'),
('OFF_AMZ_005', 'Amazon', 'Kotak', 'credit', '{Kotak 811,Kotak League}', 'percentage', 10, 750, 5000, '{non_emi}', '{electronics}', '2026-09-10', '2026-09-30', '10% off up to ₹750 on electronics. Min ₹5,000.', true, true, 0.88, 'active'),

-- Flipkart offers
('OFF_FLP_001', 'Flipkart', 'HDFC', 'credit', '{HDFC Regalia,HDFC Millennia}', 'percentage', 10, 1000, 5000, '{non_emi}', '{electronics,fashion}', '2026-09-01', '2026-09-30', '10% instant discount up to ₹1,000 on min ₹5,000. HDFC credit cards.', true, true, 0.95, 'active'),
('OFF_FLP_002', 'Flipkart', 'SBI', 'credit', '{SBI SimplyCLICK,SBI Elite,SBI Prime}', 'percentage', 10, 500, 3000, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500 on fashion. Min ₹3,000.', true, true, 0.93, 'active'),
('OFF_FLP_003', 'Flipkart', 'Axis', 'credit', '{Axis Flipkart Axis,Axis Magnus}', 'percentage', 5, 200, 1000, '{non_emi}', '{all}', '2026-09-01', '2026-09-30', '5% unlimited cashback on Axis Flipkart Axis card.', true, true, 0.94, 'active'),
('OFF_FLP_004', 'Flipkart', 'ICICI', 'credit', '{ICICI Coral,ICICI Sapphiro}', 'percentage', 10, 750, 4999, '{non_emi}', '{electronics}', '2026-09-05', '2026-09-30', '10% off up to ₹750 on electronics. Min ₹4,999.', true, true, 0.90, 'active'),
('OFF_FLP_005', 'Flipkart', 'Kotak', 'credit', '{Kotak 811}', 'percentage', 10, 500, 3000, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500 on fashion.', true, true, 0.87, 'active'),

-- Ajio offers
('OFF_AJO_001', 'Ajio', 'HDFC', 'credit', '{HDFC Regalia,HDFC Millennia,HDFC Diners Club Black}', 'percentage', 15, 1000, 3999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '15% instant discount up to ₹1,000. Min ₹3,999. HDFC credit cards on Ajio.', true, true, 0.94, 'active'),
('OFF_AJO_002', 'Ajio', 'ICICI', 'credit', '{ICICI Coral,ICICI Sapphiro,ICICI Rubyx}', 'percentage', 15, 750, 2999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '15% off up to ₹750. Min ₹2,999. ICICI credit cards.', true, true, 0.92, 'active'),
('OFF_AJO_003', 'Ajio', 'SBI', 'credit', '{SBI SimplyCLICK,SBI Elite}', 'percentage', 10, 500, 2499, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500. Min ₹2,499.', true, true, 0.90, 'active'),
('OFF_AJO_004', 'Ajio', 'Axis', 'credit', '{Axis Flipkart Axis,Axis Neo}', 'percentage', 12, 600, 2999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '12% off up to ₹600. Min ₹2,999.', true, true, 0.89, 'active'),
('OFF_AJO_005', 'Ajio', 'Kotak', 'credit', '{Kotak 811,Kotak Royale}', 'percentage', 10, 500, 2499, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500. Min ₹2,499.', true, true, 0.87, 'active'),

-- Nykaa Fashion offers
('OFF_NYK_001', 'Nykaa Fashion', 'HDFC', 'credit', '{HDFC Regalia,HDFC Millennia}', 'percentage', 10, 500, 2999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500. Min ₹2,999. HDFC credit cards.', true, true, 0.91, 'active'),
('OFF_NYK_002', 'Nykaa Fashion', 'ICICI', 'credit', '{ICICI Amazon Pay,ICICI Coral}', 'percentage', 10, 400, 2499, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹400. Min ₹2,499.', true, true, 0.89, 'active'),
('OFF_NYK_003', 'Nykaa Fashion', 'SBI', 'credit', '{SBI SimplyCLICK}', 'percentage', 10, 300, 1999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹300. Min ₹1,999.', true, true, 0.87, 'active'),

-- Tata CLiQ offers
('OFF_TCL_001', 'Tata CLiQ', 'HDFC', 'credit', '{HDFC Regalia,HDFC Infinia}', 'percentage', 10, 750, 4999, '{non_emi}', '{fashion,electronics}', '2026-09-01', '2026-09-30', '10% off up to ₹750. Min ₹4,999. HDFC credit cards.', true, true, 0.92, 'active'),
('OFF_TCL_002', 'Tata CLiQ', 'ICICI', 'credit', '{ICICI Coral,ICICI Sapphiro}', 'percentage', 10, 500, 3999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500. Min ₹3,999.', true, true, 0.90, 'active'),
('OFF_TCL_003', 'Tata CLiQ', 'Axis', 'credit', '{Axis Magnus,Axis Neo}', 'percentage', 10, 500, 3499, '{non_emi}', '{fashion,electronics}', '2026-09-01', '2026-09-30', '10% off up to ₹500. Min ₹3,499.', true, true, 0.88, 'active'),

-- Meesho offers
('OFF_MS_001', 'Meesho', 'HDFC', 'credit', '{HDFC Millennia,HDFC MoneyBack+}', 'percentage', 5, 200, 999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '5% off up to ₹200. Min ₹999.', true, true, 0.88, 'active'),
('OFF_MS_002', 'Meesho', 'SBI', 'debit', '{SBI Debit}', 'percentage', 5, 150, 999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '5% off up to ₹150 on SBI debit cards.', true, true, 0.85, 'active'),

-- H&M offers (brand store)
('OFF_HM_001', 'H&M', 'HDFC', 'credit', '{HDFC Regalia,HDFC Millennia}', 'percentage', 10, 500, 3499, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500. Min ₹3,499.', true, true, 0.90, 'active'),
('OFF_HM_002', 'H&M', 'ICICI', 'credit', '{ICICI Coral}', 'percentage', 10, 400, 2999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹400. Min ₹2,999.', true, true, 0.88, 'active'),

-- Nike offers
('OFF_NKE_001', 'Nike', 'HDFC', 'credit', '{HDFC Regalia,HDFC Infinia}', 'percentage', 10, 750, 4999, '{non_emi}', '{fashion,sports}', '2026-09-01', '2026-09-30', '10% off up to ₹750. Min ₹4,999.', true, true, 0.92, 'active'),
('OFF_NKE_002', 'Nike', 'SBI', 'credit', '{SBI SimplyCLICK,SBI Prime}', 'percentage', 10, 500, 3499, '{non_emi}', '{fashion,sports}', '2026-09-01', '2026-09-30', '10% off up to ₹500. Min ₹3,499.', true, true, 0.90, 'active'),
('OFF_NKE_003', 'Nike', 'Axis', 'credit', '{Axis Flipkart Axis}', 'percentage', 10, 500, 3999, '{non_emi}', '{fashion,sports}', '2026-09-01', '2026-09-30', '10% off up to ₹500. Min ₹3,999.', true, true, 0.88, 'active'),

-- Adidas offers
('OFF_AD_001', 'Adidas', 'HDFC', 'credit', '{HDFC Regalia,HDFC Millennia}', 'percentage', 10, 500, 3499, '{non_emi}', '{fashion,sports}', '2026-09-01', '2026-09-30', '10% off up to ₹500. Min ₹3,499.', true, true, 0.91, 'active'),
('OFF_AD_002', 'Adidas', 'ICICI', 'credit', '{ICICI Coral,ICICI Sapphiro}', 'percentage', 10, 400, 2999, '{non_emi}', '{fashion,sports}', '2026-09-01', '2026-09-30', '10% off up to ₹400. Min ₹2,999.', true, true, 0.89, 'active'),

-- Puma offers
('OFF_PMA_001', 'Puma', 'HDFC', 'credit', '{HDFC Regalia,HDFC Millennia}', 'percentage', 10, 500, 2999, '{non_emi}', '{fashion,sports}', '2026-09-01', '2026-09-30', '10% off up to ₹500. Min ₹2,999.', true, true, 0.90, 'active'),
('OFF_PMA_002', 'Puma', 'SBI', 'credit', '{SBI SimplyCLICK}', 'percentage', 10, 400, 2499, '{non_emi}', '{fashion,sports}', '2026-09-01', '2026-09-30', '10% off up to ₹400. Min ₹2,499.', true, true, 0.88, 'active'),

-- Levi's offers
('OFF_LVS_001', "Levi's", 'HDFC', 'credit', '{HDFC Regalia,HDFC Millennia}', 'percentage', 10, 500, 3499, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500. Min ₹3,499.', true, true, 0.90, 'active'),
('OFF_LVS_002', "Levi's", 'ICICI', 'credit', '{ICICI Coral}', 'percentage', 10, 400, 2999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹400. Min ₹2,999.', true, true, 0.88, 'active'),

-- Westside offers
('OFF_WST_001', 'Westside', 'HDFC', 'credit', '{HDFC Regalia}', 'percentage', 10, 400, 2499, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹400. Min ₹2,499.', true, true, 0.87, 'active'),

-- Lifestyle offers
('OFF_LFS_001', 'Lifestyle', 'HDFC', 'credit', '{HDFC Regalia,HDFC Millennia}', 'percentage', 10, 500, 3499, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500. Min ₹3,499.', true, true, 0.89, 'active'),
('OFF_LFS_002', 'Lifestyle', 'SBI', 'credit', '{SBI SimplyCLICK,SBI Prime}', 'percentage', 10, 400, 2999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹400. Min ₹2,999.', true, true, 0.87, 'active'),

-- Shoppers Stop offers
('OFF_SS_001', 'Shoppers Stop', 'HDFC', 'credit', '{HDFC Regalia}', 'percentage', 10, 500, 3999, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹500. Min ₹3,999.', true, true, 0.88, 'active'),
('OFF_SS_002', 'Shoppers Stop', 'ICICI', 'credit', '{ICICI Coral,ICICI Sapphiro}', 'percentage', 10, 400, 3499, '{non_emi}', '{fashion}', '2026-09-01', '2026-09-30', '10% off up to ₹400. Min ₹3,499.', true, true, 0.86, 'active'),

-- Decathlon offers
('OFF_DCN_001', 'Decathlon', 'HDFC', 'credit', '{HDFC Millennia,HDFC MoneyBack+}', 'percentage', 5, 300, 1999, '{non_emi}', '{sports}', '2026-09-01', '2026-09-30', '5% off up to ₹300. Min ₹1,999.', true, true, 0.88, 'active'),
('OFF_DCN_002', 'Decathlon', 'SBI', 'debit', '{SBI Debit}', 'percentage', 5, 200, 1499, '{non_emi}', '{sports}', '2026-09-01', '2026-09-30', '5% off up to ₹200 on debit cards.', true, true, 0.85, 'active'),

-- Croma offers
('OFF_CRM_001', 'Croma', 'HDFC', 'credit', '{HDFC Regalia,HDFC Infinia,HDFC Diners Club Black}', 'percentage', 10, 1500, 10000, '{non_emi,emi}', '{electronics}', '2026-09-01', '2026-09-30', '10% off up to ₹1,500 on min ₹10,000. HDFC credit cards.', true, true, 0.93, 'active'),
('OFF_CRM_002', 'Croma', 'ICICI', 'credit', '{ICICI Coral,ICICI Sapphiro,ICICI Rubyx}', 'percentage', 10, 1000, 7999, '{non_emi}', '{electronics}', '2026-09-01', '2026-09-30', '10% off up to ₹1,000. Min ₹7,999.', true, true, 0.91, 'active'),
('OFF_CRM_003', 'Croma', 'Axis', 'credit', '{Axis Magnus,Axis Reserve}', 'percentage', 10, 1000, 8999, '{non_emi}', '{electronics}', '2026-09-01', '2026-09-30', '10% off up to ₹1,000. Min ₹8,999.', true, true, 0.89, 'active'),

-- Reliance Digital offers
('OFF_RD_001', 'Reliance Digital', 'HDFC', 'credit', '{HDFC Regalia,HDFC Infinia}', 'percentage', 10, 1500, 10000, '{non_emi,emi}', '{electronics}', '2026-09-01', '2026-09-30', '10% off up to ₹1,500 on min ₹10,000.', true, true, 0.92, 'active'),
('OFF_RD_002', 'Reliance Digital', 'ICICI', 'credit', '{ICICI Sapphiro,ICICI Rubyx}', 'percentage', 10, 1000, 8999, '{non_emi}', '{electronics}', '2026-09-01', '2026-09-30', '10% off up to ₹1,000. Min ₹8,999.', true, true, 0.90, 'active');
