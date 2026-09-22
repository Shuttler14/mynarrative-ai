/**
 * MY NARRATIVE — Shopify Web Pixel Extension
 * Captures merchant-side events for attribution
 *
 * Change ID: ADD-CHK-013-260922
 * Risk: HIGH — merchant attribution capture
 *
 * This script runs on the merchant's Shopify store.
 * It captures:
 *   - product_viewed
 *   - product_added_to_cart
 *   - checkout_started
 *   - checkout_completed
 *
 * And sends them to MN's attribution system.
 *
 * Install: Add to Shopify theme or via Shopify App Pixel
 */

(function() {
  'use strict';

  var MN_PIXEL_ENDPOINT = 'https://drishti-api-blond.vercel.app/api/webhooks/merchant-pixel';
  var MN_BRAND_ID = null; // Set by merchant during installation

  // ============================================
  // 1. CAPTURE MN CLICK ID
  // From UTM params or localStorage
  // ============================================
  function getMNClickId() {
    // Try URL params first
    var params = new URLSearchParams(window.location.search);
    var clickId = params.get('mn_click_id') || params.get('mnclk');

    // Try localStorage
    if (!clickId) {
      try {
        clickId = localStorage.getItem('mn_click_id');
      } catch (e) {}
    }

    // Try sessionStorage
    if (!clickId) {
      try {
        clickId = sessionStorage.getItem('mn_click_id');
      } catch (e) {}
    }

    return clickId;
  }

  // Store click_id if found in URL
  var currentClickId = getMNClickId();
  if (currentClickId) {
    try {
      localStorage.setItem('mn_click_id', currentClickId);
      sessionStorage.setItem('mn_click_id', currentClickId);
    } catch (e) {}
  }

  // ============================================
  // 2. GET MN PRODUCT ID
  // Via App Proxy or product metafield
  // ============================================
  function getMNProductId(productData) {
    // Check product metafield for MN Product ID
    if (productData && productData.metafields) {
      for (var i = 0; i < productData.metafields.length; i++) {
        if (productData.metafields[i].key === 'mn_product_id') {
          return productData.metafields[i].value;
        }
      }
    }

    // Check window object (set by Shopify App)
    if (window.__mn_product_id) {
      return window.__mn_product_id;
    }

    return null;
  }

  // ============================================
  // 3. SEND EVENT TO MN
  // ============================================
  function sendMNEvent(eventType, data) {
    if (!MN_BRAND_ID) {
      // Try to get brand ID from meta tag
      var meta = document.querySelector('meta[name="mn-brand-id"]');
      if (meta) {
        MN_BRAND_ID = meta.getAttribute('content');
      }
    }

    if (!MN_BRAND_ID) return;

    var payload = {
      merchant_brand_id: MN_BRAND_ID,
      event_type: eventType,
      mn_click_id: currentClickId,
      user_id: null, // Will be set by MN backend from click_id
      session_id: null,
      product_data: data.product || null,
      order_data: data.order || null,
    };

    // Use sendBeacon for reliability (fire-and-forget)
    if (navigator.sendBeacon) {
      var blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      navigator.sendBeacon(MN_PIXEL_ENDPOINT, blob);
    } else {
      // Fallback to fetch
      fetch(MN_PIXEL_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(function() {});
    }
  }

  // ============================================
  // 4. SHOPIFY WEB PIXEL API
  // ============================================
  if (typeof shopify !== 'undefined' && shopify.analytics) {
    // Subscribe to customer events
    shopify.analytics.subscribe('product_viewed', function(event) {
      sendMNEvent('product_viewed', {
        product: {
          product_id: event.productVariant ? event.productVariant.product.id : null,
          variant_id: event.productVariant ? event.productVariant.id : null,
          title: event.productVariant ? event.productVariant.product.title : null,
          price: event.productVariant ? event.productVariant.price : null,
          sku: event.productVariant ? event.productVariant.sku : null,
        }
      });
    });

    shopify.analytics.subscribe('product_added_to_cart', function(event) {
      sendMNEvent('product_added_to_cart', {
        product: {
          product_id: event.variant ? event.variant.product.id : null,
          variant_id: event.variant ? event.variant.id : null,
          title: event.variant ? event.variant.product.title : null,
          price: event.variant ? event.variant.price : null,
          quantity: event.quantity,
          sku: event.variant ? event.variant.sku : null,
        }
      });
    });

    shopify.analytics.subscribe('checkout_started', function(event) {
      sendMNEvent('checkout_started', {
        order: {
          checkout_id: event.checkout ? event.checkout.id : null,
          total: event.checkout ? event.checkout.totalPrice : null,
          line_items: event.checkout ? event.checkout.lineItems.map(function(item) {
            return {
              product_id: item.variant ? item.variant.product.id : null,
              variant_id: item.variant ? item.variant.id : null,
              title: item.title,
              price: item.variant ? item.variant.price : null,
              quantity: item.quantity,
              sku: item.variant ? item.variant.sku : null,
            };
          }) : [],
        }
      });
    });

    shopify.analytics.subscribe('checkout_completed', function(event) {
      var checkout = event.checkout;
      if (!checkout) return;

      sendMNEvent('checkout_completed', {
        order: {
          order_id: checkout.order ? checkout.order.id : checkout.id,
          checkout_id: checkout.id,
          total: checkout.totalPrice,
          currency: checkout.currency,
          line_items: checkout.lineItems.map(function(item) {
            return {
              id: item.id,
              product_id: item.variant ? item.variant.product.id : null,
              variant_id: item.variant ? item.variant.id : null,
              title: item.title,
              price: item.variant ? item.variant.price : null,
              quantity: item.quantity,
              sku: item.variant ? item.variant.sku : null,
            };
          }),
        }
      });

      // Clear stored click_id after successful purchase
      try {
        localStorage.removeItem('mn_click_id');
        sessionStorage.removeItem('mn_click_id');
      } catch (e) {}
    });
  }

  // ============================================
  // 5. FALLBACK: GA4-LIKE DATA LAYER
  // For non-Shopify or custom integrations
  // ============================================
  window.MNPixel = {
    setBrandId: function(brandId) {
      MN_BRAND_ID = brandId;
    },
    track: function(eventType, data) {
      sendMNEvent(eventType, data);
    },
    setClickId: function(clickId) {
      currentClickId = clickId;
      try {
        localStorage.setItem('mn_click_id', clickId);
        sessionStorage.setItem('mn_click_id', clickId);
      } catch (e) {}
    },
    getClickId: function() {
      return currentClickId;
    }
  };

})();
