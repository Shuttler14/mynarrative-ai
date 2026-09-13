"""
Multi-Currency Support Module
Provides exchange rates, country detection, and price formatting for 6 currencies.
Base currency: INR (all internal pricing stays in INR).
"""

import os
import json

# Supported currencies with their symbols and formatting
CURRENCIES = {
    "INR": {"symbol": "₹", "name": "Indian Rupee", "decimals": 0, "position": "before"},
    "USD": {"symbol": "$", "name": "US Dollar", "decimals": 2, "position": "before"},
    "GBP": {"symbol": "£", "name": "British Pound", "decimals": 2, "position": "before"},
    "EUR": {"symbol": "€", "name": "Euro", "decimals": 2, "position": "before"},
    "AED": {"symbol": "د.إ", "name": "UAE Dirham", "decimals": 2, "position": "before"},
    "AUD": {"symbol": "A$", "name": "Australian Dollar", "decimals": 2, "position": "before"},
}

# Country code -> default currency mapping
COUNTRY_CURRENCY = {
    "IN": "INR",
    "US": "USD",
    "GB": "GBP",
    "DE": "EUR", "FR": "EUR", "IT": "EUR", "ES": "EUR", "NL": "EUR",
    "BE": "EUR", "AT": "EUR", "PT": "EUR", "IE": "EUR", "FI": "EUR",
    "GR": "EUR", "LU": "EUR", "CY": "EUR", "MT": "EUR", "SK": "EUR",
    "EE": "EUR", "LV": "EUR", "LT": "EUR", "SI": "EUR", "HR": "EUR",
    "AE": "AED", "SA": "AED", "QA": "AED", "KW": "AED", "BH": "AED", "OM": "AED",
    "AU": "AUD", "NZ": "AUD",
    "CA": "USD", "MX": "USD", "BR": "USD", "AR": "USD", "CL": "USD", "CO": "USD",
    "JP": "USD", "KR": "USD", "CN": "USD", "SG": "USD", "MY": "USD", "TH": "USD",
    "PH": "USD", "ID": "USD", "VN": "USD",
    "ZA": "USD", "NG": "USD", "KE": "USD", "EG": "USD",
}

# Exchange rates: 1 INR = X foreign currency (approximate, update periodically)
# These are approximate rates. In production, fetch from a live API.
EXCHANGE_RATES = {
    "INR": 1.0,
    "USD": 0.012,      # 1 INR ≈ 0.012 USD (1 USD ≈ 83.5 INR)
    "GBP": 0.0095,     # 1 INR ≈ 0.0095 GBP (1 GBP ≈ 105 INR)
    "EUR": 0.011,      # 1 INR ≈ 0.011 EUR (1 EUR ≈ 91 INR)
    "AED": 0.044,      # 1 INR ≈ 0.044 AED (1 AED ≈ 22.7 INR)
    "AUD": 0.018,      # 1 INR ≈ 0.018 AUD (1 AUD ≈ 55.5 INR)
}


def detect_currency_from_headers(headers):
    """
    Detect user's currency from Vercel geo headers and other request headers.
    Returns ISO currency code (e.g., 'USD', 'INR').
    """
    # Vercel provides these headers automatically
    country = (
        headers.get("x-vercel-ip-country")
        or headers.get("cf-ipcountry")
        or headers.get("x-country-code")
        or headers.get("x-forwarded-for-country")
    )

    if country:
        country = country.upper().strip()
        currency = COUNTRY_CURRENCY.get(country)
        if currency:
            return currency

    # Fallback: check Accept-Language header for locale hints
    accept_lang = headers.get("accept-language", "")
    if accept_lang:
        lang_lower = accept_lang.lower()
        if "en-in" in lang_lower or "hi" in lang_lower:
            return "INR"
        if "en-gb" in lang_lower:
            return "GBP"
        if "en-au" in lang_lower:
            return "AUD"
        if "ar" in lang_lower:
            return "AED"

    # Default to USD
    return "USD"


def convert_price(amount_paise, to_currency="INR"):
    """
    Convert price from INR paise to target currency.
    Returns the converted amount in the smallest unit of the target currency.
    """
    if to_currency == "INR":
        return amount_paise

    rate = EXCHANGE_RATES.get(to_currency, EXCHANGE_RATES["USD"])
    inr_rupees = amount_paise / 100.0
    foreign_amount = inr_rupees * rate

    # Round to appropriate decimals
    decimals = CURRENCIES[to_currency]["decimals"]
    if decimals == 0:
        return round(foreign_amount)
    return round(foreign_amount, decimals)


def convert_price_rupees(amount_rupees, to_currency="INR"):
    """
    Convert price from INR rupees to target currency.
    Returns the converted amount.
    """
    if to_currency == "INR":
        return amount_rupees

    rate = EXCHANGE_RATES.get(to_currency, EXCHANGE_RATES["USD"])
    foreign_amount = amount_rupees * rate

    decimals = CURRENCIES[to_currency]["decimals"]
    if decimals == 0:
        return round(foreign_amount)
    return round(foreign_amount, decimals)


def format_price(amount, currency="INR"):
    """
    Format a price amount with the correct currency symbol and decimals.
    """
    info = CURRENCIES.get(currency, CURRENCIES["INR"])
    decimals = info["decimals"]

    if decimals == 0:
        formatted = f"{int(round(amount)):,}"
    else:
        formatted = f"{amount:,.{decimals}f}"

    if info["position"] == "before":
        return f"{info['symbol']}{formatted}"
    return f"{formatted}{info['symbol']}"


def price_bounds_paise(currency="INR"):
    """
    Get min/max price bounds in paise for a given currency.
    Original bounds are in INR paise, converted to target currency.
    """
    TSHIRT_MIN_PAISE = 64900   # 649 INR
    TSHIRT_MAX_PAISE = 99900   # 999 INR
    HOODIE_MIN_PAISE = 119900  # 1199 INR
    HOODIE_MAX_PAISE = 189900  # 1899 INR

    return {
        "tshirt": {
            "min": convert_price(TSHIRT_MIN_PAISE, currency),
            "max": convert_price(TSHIRT_MAX_PAISE, currency),
        },
        "hoodie": {
            "min": convert_price(HOODIE_MIN_PAISE, currency),
            "max": convert_price(HOODIE_MAX_PAISE, currency),
        },
    }


def base_cost_paise(product_type="tshirt", currency="INR"):
    """
    Get production base cost in target currency.
    """
    TSHIRT_COST_PAISE = 50000   # 500 INR
    HOODIE_COST_PAISE = 90000   # 900 INR

    paise = TSHIRT_COST_PAISE if product_type == "tshirt" else HOODIE_COST_PAISE
    return convert_price(paise, currency)


def get_currency_info(currency="INR"):
    """Return full currency metadata."""
    return CURRENCIES.get(currency, CURRENCIES["INR"])


def parse_price(price_str: str) -> float:
    """
    Parse a price string like '₹1,299', '$19.99', 'Rs. 1299', '1299.00' into a float (INR).
    Strips currency symbols, commas, and whitespace.
    """
    import re
    if not price_str:
        return 0.0
    cleaned = re.sub(r'[₹$£€AED AUD\s]', '', str(price_str).strip())
    cleaned = re.sub(r'^(Rs\.?|INR)', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = cleaned.replace(',', '')
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0
