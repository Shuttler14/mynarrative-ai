-- ============================================
-- Seed: Indian Banks & Popular Card Variants
-- ============================================
-- Change ID: ADD-USR-002-260922

INSERT INTO mn_bank_cards (id, bank_name, card_type, card_variant, card_network, is_popular, annual_fee, reward_type) VALUES
-- HDFC Bank
('hdfc-credit-regalia', 'HDFC Bank', 'credit', 'Regalia Gold', 'Visa', true, '₹2,500', 'travel'),
('hdfc-credit-millennia', 'HDFC Bank', 'credit', 'Millennia', 'Visa', true, '₹1,000', 'cashback'),
('hdfc-credit-diners-club-black', 'HDFC Bank', 'credit', 'Diners Club Black', 'Diners Club', true, '₹10,000', 'travel'),
('hdfc-credit-infinia', 'HDFC Bank', 'credit', 'Infinia', 'Mastercard', true, '₹12,500', 'travel'),
('hdfc-credit-moneyback', 'HDFC Bank', 'credit', 'MoneyBack+', 'Visa', true, '₹500', 'cashback'),
('hdfc-credit-tata-neu-infinity', 'HDFC Bank', 'credit', 'Tata Neu Infinity', 'RuPay', true, '₹0', 'shopping'),
('hdfc-credit-biz-black', 'HDFC Bank', 'credit', 'Biz Black', 'Mastercard', false, '₹10,000', 'business'),
('hdfc-credit-freedom', 'HDFC Bank', 'credit', 'Freedom', 'Visa', false, '₹0', 'cashback'),
('hdfc-debit-mm', 'HDFC Bank', 'debit', 'Millennia Debit', 'Visa', true, '₹0', 'cashback'),
('hdfc-debit-regalia', 'HDFC Bank', 'debit', 'Regalia Debit', 'Visa', false, '₹0', 'rewards'),

-- ICICI Bank
('icici-credit-coral', 'ICICI Bank', 'credit', 'Coral', 'Visa', true, '₹500', 'rewards'),
('icici-credit-sapphiro', 'ICICI Bank', 'credit', 'Sapphiro', 'Visa', true, '₹6,000', 'travel'),
('icici-credit-emeralde', 'ICICI Bank', 'credit', 'Emeralde', 'Visa', true, '₹12,000', 'travel'),
('icici-credit-platinum-chip', 'ICICI Bank', 'credit', 'Platinum Chip', 'Visa', true, '₹0', 'rewards'),
('icici-credit-amazon-pay', 'ICICI Bank', 'credit', 'Amazon Pay', 'Visa', true, '₹0', 'cashback'),
('icici-credit-mmgc', 'ICICI Bank', 'credit', 'MakeMyTrip Gold', 'Visa', false, '₹1,000', 'travel'),
('icici-debit-platinum', 'ICICI Bank', 'debit', 'Platinum Debit', 'Visa', true, '₹0', 'rewards'),

-- SBI
('sbi-credit-cashback', 'SBI Card', 'credit', 'Cashback', 'Visa', true, '₹999', 'cashback'),
('sbi-credit-elite', 'SBI Card', 'credit', 'Elite', 'Visa', true, '₹4,999', 'travel'),
('sbi-credit-aurum', 'SBI Card', 'credit', 'Aurum', 'Mastercard', true, '₹10,000', 'premium'),
('sbi-credit SimplyCLICK', 'SBI Card', 'credit', 'SimplyCLICK', 'Visa', true, '₹499', 'shopping'),
('sbi-credit SimplySAVE', 'SBI Card', 'credit', 'SimplySAVE', 'Visa', true, '₹499', 'rewards'),
('sbi-debit-global', 'SBI Card', 'debit', 'Global Debit', 'Visa', true, '₹0', 'rewards'),

-- Axis Bank
('axis-credit-flipkart', 'Axis Bank', 'credit', 'Flipkart Axis', 'Mastercard', true, '₹500', 'shopping'),
('axis-credit-myzone', 'Axis Bank', 'credit', 'MyZone', 'Visa', true, '₹500', 'entertainment'),
('axis-credit-vistara', 'Axis Bank', 'credit', 'Vistara Infinite', 'Visa', true, '₹5,000', 'travel'),
('axis-credit-select', 'Axis Bank', 'credit', 'Select', 'Visa', false, '₹1,000', 'rewards'),
('axis-debit-premium', 'Axis Bank', 'debit', 'Premium Debit', 'Visa', true, '₹0', 'rewards'),

-- Kotak Mahindra Bank
('kotak-credit-811', 'Kotak Mahindra Bank', 'credit', '811', 'Visa', true, '₹0', 'cashback'),
('kotak-credit-royale', 'Kotak Mahindra Bank', 'credit', 'Royale', 'Visa', true, '₹999', 'travel'),
('kotak-credit-league', 'Kotak Mahindra Bank', 'credit', 'League', 'Visa', false, '₹0', 'rewards'),
('kotak-debit-811', 'Kotak Mahindra Bank', 'debit', '811 Debit', 'Visa', true, '₹0', 'cashback'),

-- IDFC FIRST Bank
('idfc-credit-first-choose', 'IDFC FIRST Bank', 'credit', 'FIRST Select', 'Visa', true, '₹0', 'rewards'),
('idfc-credit-first-wealth', 'IDFC FIRST Bank', 'credit', 'FIRST Wealth', 'Visa', true, '₹0', 'travel'),
('idfc-debit-first', 'IDFC FIRST Bank', 'debit', 'FIRST Debit', 'Visa', true, '₹0', 'rewards'),

-- IndusInd Bank
('indusind-credit-pioneer', 'IndusInd Bank', 'credit', 'Pioneer Heritage', 'Visa', true, '₹3,000', 'travel'),
('indusind-credit-visa-signature', 'IndusInd Bank', 'credit', 'Visa Signature', 'Visa', false, '₹999', 'rewards'),
('indusind-debit-premium', 'IndusInd Bank', 'debit', 'Premium Debit', 'Visa', true, '₹0', 'rewards'),

-- RBL Bank
('rbl-credit-world-safari', 'RBL Bank', 'credit', 'World Safari', 'Mastercard', true, '₹3,000', 'travel'),
('rbl-credit-shoprite', 'RBL Bank', 'credit', 'Shoprite', 'Visa', true, '₹0', 'shopping'),
('rbl-debit-global', 'RBL Bank', 'debit', 'Global Debit', 'Visa', true, '₹0', 'rewards'),

-- American Express
('amex-charge-gold', 'American Express', 'credit', 'Gold Card', 'Amex', true, '₹0', 'rewards'),
('amex-charge-platinum', 'American Express', 'credit', 'Platinum Card', 'Amex', true, '₹60,000', 'premium'),
('amex-credit-mrcc', 'American Express', 'credit', 'MRCC', 'Amex', true, '₹1,000', 'rewards'),

-- Yes Bank
('yes-credit-finna', 'Yes Bank', 'credit', 'Finna', 'RuPay', true, '₹0', 'cashback'),
('yes-credit-pro', 'Yes Bank', 'credit', 'Pro', 'Visa', false, '₹999', 'rewards'),
('yes-debit-global', 'Yes Bank', 'debit', 'Global Debit', 'Visa', true, '₹0', 'rewards'),

-- Bank of Baroda
('bob-credit-vastra', 'Bank of Baroda', 'credit', 'Vastra', 'Visa', true, '₹0', 'rewards'),
('bob-credit-premium', 'Bank of Baroda', 'credit', 'Premium', 'Visa', false, '₹999', 'travel'),
('bob-debit-global', 'Bank of Baroda', 'debit', 'Global Debit', 'Visa', true, '₹0', 'rewards'),

-- Punjab National Bank
('pnb-credit-rupay', 'Punjab National Bank', 'credit', 'RuPay Platinum', 'RuPay', true, '₹0', 'rewards'),
('pnb-debit-global', 'Punjab National Bank', 'debit', 'Global Debit', 'Visa', true, '₹0', 'rewards'),

-- Canara Bank
('canara-credit-rupay', 'Canara Bank', 'credit', 'RuPay Platinum', 'RuPay', true, '₹0', 'rewards'),
('canara-debit-global', 'Canara Bank', 'debit', 'Global Debit', 'Visa', true, '₹0', 'rewards'),

-- Union Bank
('union-credit-rupay', 'Union Bank of India', 'credit', 'RuPay Platinum', 'RuPay', true, '₹0', 'rewards'),
('union-debit-global', 'Union Bank of India', 'debit', 'Global Debit', 'Visa', true, '₹0', 'rewards')
ON CONFLICT (id) DO NOTHING;
