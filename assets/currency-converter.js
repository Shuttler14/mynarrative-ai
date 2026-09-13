/**
 * MY NARRATIVE — Client-Side Currency Converter
 * Detects user's country via IP, converts all INR prices on the page.
 * Base currency: INR (all Shopify product prices are stored in INR).
 */
(function () {
  "use strict";

  const INR_TO_USD = 0.012;
  const INR_TO_GBP = 0.0095;
  const INR_TO_EUR = 0.011;
  const INR_TO_AED = 0.044;
  const INR_TO_AUD = 0.018;

  const CURRENCY_MAP = {
    IN: { code: "INR", symbol: "\u20B9", rate: 1, decimals: 0 },
    US: { code: "USD", symbol: "$", rate: INR_TO_USD, decimals: 2 },
    GB: { code: "GBP", symbol: "\u00A3", rate: INR_TO_GBP, decimals: 2 },
    DE: { code: "EUR", symbol: "\u20AC", rate: INR_TO_EUR, decimals: 2 },
    FR: { code: "EUR", symbol: "\u20AC", rate: INR_TO_EUR, decimals: 2 },
    IT: { code: "EUR", symbol: "\u20AC", rate: INR_TO_EUR, decimals: 2 },
    ES: { code: "EUR", symbol: "\u20AC", rate: INR_TO_EUR, decimals: 2 },
    NL: { code: "EUR", symbol: "\u20AC", rate: INR_TO_EUR, decimals: 2 },
    AE: { code: "AED", symbol: "د.إ", rate: INR_TO_AED, decimals: 2 },
    SA: { code: "AED", symbol: "د.إ", rate: INR_TO_AED, decimals: 2 },
    AU: { code: "AUD", symbol: "A$", rate: INR_TO_AUD, decimals: 2 },
    NZ: { code: "AUD", symbol: "A$", rate: INR_TO_AUD, decimals: 2 },
    CA: { code: "USD", symbol: "$", rate: INR_TO_USD, decimals: 2 },
    JP: { code: "USD", symbol: "$", rate: INR_TO_USD, decimals: 2 },
    SG: { code: "USD", symbol: "$", rate: INR_TO_USD, decimals: 2 },
  };

  const DEFAULT_CURRENCY = CURRENCY_MAP["IN"];

  function formatPrice(amount, currency) {
    var decimals = currency.decimals;
    var formatted;
    if (decimals === 0) {
      formatted = Math.round(amount).toLocaleString("en-IN");
    } else {
      formatted = amount.toLocaleString("en-US", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
    }
    return currency.symbol + formatted;
  }

  function convertPrice(inrAmount, currency) {
    if (currency.code === "INR") return inrAmount;
    return inrAmount * currency.rate;
  }

  /**
   * Parse a price string like "₹699", "₹1,299", "699" into a number.
   */
  function parsePrice(text) {
    if (!text) return NaN;
    var cleaned = text.replace(/[^\d.]/g, "");
    return parseFloat(cleaned);
  }

  /**
   * Scan the DOM for price elements and convert them.
   * Looks for elements containing ₹ followed by a number.
   */
  function convertPricesOnPage(currency) {
    if (currency.code === "INR") return;

    // Find all text nodes and elements that contain INR prices
    var priceElements = document.querySelectorAll(
      [
        ".price",
        ".price-item",
        ".product-price",
        ".sale-price",
        ".compare-at-price",
        ".money",
        "[data-price]",
        ".card__price",
        ".collection-product-price",
        ".product-card__price",
        ".product__price",
        ".price__regular",
        ".price__sale",
        ".price--on-sale",
        ".ProductMeta__Price",
        ".product-single__price",
        ".product-single__price--sale",
        ".product-single__price--regular",
        // Broader selectors for any element with rupee symbol
      ].join(", ")
    );

    // Also search by text content containing ₹
    var allElements = document.querySelectorAll(
      "span, p, div, s, del, ins, strong, em, a"
    );

    var priceRegex = /[\u20B9](\d[\d,]*\.?\d*)/;

    function processElement(el) {
      // Skip if already converted
      if (el.dataset.currencyConverted) return;

      var text = el.textContent || "";
      var match = text.match(priceRegex);

      if (match) {
        var inrAmount = parsePrice(match[0]);
        if (isNaN(inrAmount) || inrAmount <= 0) return;

        var converted = convertPrice(inrAmount, currency);
        var newPrice = formatPrice(converted, currency);

        // Replace ₹ amount with converted price
        el.textContent = text.replace(priceRegex, newPrice);
        el.dataset.currencyConverted = "true";
        el.dataset.originalPrice = match[0];
      }
    }

    // Process targeted price elements
    priceElements.forEach(processElement);

    // Process all text-containing elements (broader scan)
    allElements.forEach(processElement);
  }

  /**
   * Convert prices stored in data attributes (e.g., data-price="69900" in paise).
   */
  function convertDataAttributePrices(currency) {
    if (currency.code === "INR") return;

    var paiseElements = document.querySelectorAll("[data-price-paise]");
    paiseElements.forEach(function (el) {
      var paise = parseInt(el.dataset.pricePaise, 10);
      if (isNaN(paise) || paise <= 0) return;
      var inrRupees = paise / 100;
      var converted = convertPrice(inrRupees, currency);
      el.textContent = formatPrice(converted, currency);
    });
  }

  /**
   * Detect user's country from Vercel geo headers via a lightweight API call,
   * or fall back to a free IP geolocation service.
   */
  async function detectCountry() {
    // Try Vercel edge headers first (works on Vercel deployments)
    try {
      var resp = await fetch("/api/health", { method: "HEAD" });
      var country = resp.headers.get("x-vercel-ip-country");
      if (country && CURRENCY_MAP[country.toUpperCase()]) {
        return country.toUpperCase();
      }
    } catch (e) {
      // ignore
    }

    // Fallback: free IP geolocation
    try {
      var resp = await fetch("https://ipapi.co/json/", {
        method: "GET",
        headers: { Accept: "application/json" },
      });
      var data = await resp.json();
      if (data && data.country_code && CURRENCY_MAP[data.country_code]) {
        return data.country_code;
      }
    } catch (e) {
      // ignore
    }

    return "IN"; // default to India
  }

  /**
   * Main entry point.
   */
  async function init() {
    var countryCode = await detectCountry();
    var currency = CURRENCY_MAP[countryCode] || DEFAULT_CURRENCY;

    // Store for other scripts
    window.__MN_CURRENCY__ = {
      code: currency.code,
      symbol: currency.symbol,
      rate: currency.rate,
      country: countryCode,
    };

    // Convert prices on page
    convertPricesOnPage(currency);
    convertDataAttributePrices(currency);

    // Re-run on dynamic content changes (SPA navigation, lazy loading)
    var observer = new MutationObserver(function () {
      convertPricesOnPage(currency);
      convertDataAttributePrices(currency);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  // Run on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
