"""Payment provider abstraction layer — Stripe + Razorpay."""
import json
import os
import requests


class PaymentProvider:
    """Base class for payment providers."""

    def create_checkout(self, brand_id: str, plan_tier: str, success_url: str, cancel_url: str) -> dict:
        raise NotImplementedError

    def handle_webhook(self, event_type: str, payload: dict) -> dict:
        raise NotImplementedError

    def cancel_subscription(self, subscription_id: str) -> bool:
        raise NotImplementedError

    def reactivate_subscription(self, subscription_id: str) -> bool:
        raise NotImplementedError

    def get_subscription_status(self, subscription_id: str) -> dict:
        raise NotImplementedError


class StripeProvider(PaymentProvider):
    """Stripe payment provider."""

    PLAN_PRICES = {
        "starter": {"inr": 299900, "usd": 4900},  # Price in paise/cents
        "growth": {"inr": 999900, "usd": 14900},
        "enterprise": {"inr": 2999900, "usd": 39900}
    }

    def __init__(self):
        self.secret_key = os.environ.get("STRIPE_SECRET_KEY", "")
        self.webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    def _request(self, method, path, data=None):
        if not self.secret_key:
            return None
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        url = f"https://api.stripe.com/v1{path}"
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                resp = requests.post(url, data=data, headers=headers, timeout=30)
            elif method == "DELETE":
                resp = requests.delete(url, headers=headers, timeout=30)
            else:
                resp = requests.request(method, url, data=data, headers=headers, timeout=30)
            return resp.json() if resp.text else None
        except Exception as e:
            print(f"⚠️ [Stripe] {e}")
            return None

    def create_checkout(self, brand_id: str, plan_tier: str, success_url: str, cancel_url: str) -> dict:
        import urllib.parse
        prices = self.PLAN_PRICES.get(plan_tier, self.PLAN_PRICES["starter"])

        # Determine currency based on brand location
        currency = "inr"  # Default, should be determined by brand's country

        data = {
            "mode": "subscription",
            "payment_method_types[]": "card",
            "line_items[0][price_data][currency]": currency,
            "line_items[0][price_data][product_data][name]": f"MyNarrative {plan_tier.title()} Plan",
            "line_items[0][price_data][recurring][interval]": "month",
            "line_items[0][price_data][unit_amount]": prices.get(currency, prices["inr"]),
            "line_items[0][quantity]": "1",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata[brand_id]": brand_id,
            "metadata[plan_tier]": plan_tier
        }

        result = self._request("POST", "/checkout/sessions", data)
        if result:
            return {"checkout_url": result.get("url"), "session_id": result.get("id")}
        return {"error": "Failed to create checkout session"}

    def handle_webhook(self, event_type: str, payload: dict) -> dict:
        """Handle Stripe webhook events."""
        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "invoice.paid": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_payment_failed,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
        }
        handler = handlers.get(event_type)
        if handler:
            return handler(payload)
        return {"handled": False}

    def _handle_checkout_completed(self, payload: dict) -> dict:
        session = payload.get("data", {}).get("object", {})
        brand_id = session.get("metadata", {}).get("brand_id")
        subscription_id = session.get("subscription")

        if brand_id and subscription_id:
            _sb_update_subscription(brand_id, {
                "status": "active",
                "stripe_subscription_id": subscription_id,
                "stripe_customer_id": session.get("customer")
            })
            _sb_log_event(brand_id, "subscription_activated", "stripe", payload)
        return {"handled": True}

    def _handle_invoice_paid(self, payload: dict) -> dict:
        invoice = payload.get("data", {}).get("object", {})
        subscription_id = invoice.get("subscription")
        if subscription_id:
            brand = _sb_get_brand_by_stripe_sub(subscription_id)
            if brand:
                _sb_update_subscription(brand["brand_id"], {
                    "monthly_recommendations_used": 0  # Reset monthly usage
                })
                _sb_log_event(brand["brand_id"], "invoice_paid", "stripe", payload)
        return {"handled": True}

    def _handle_payment_failed(self, payload: dict) -> dict:
        invoice = payload.get("data", {}).get("object", {})
        subscription_id = invoice.get("subscription")
        if subscription_id:
            brand = _sb_get_brand_by_stripe_sub(subscription_id)
            if brand:
                _sb_update_subscription(brand["brand_id"], {"status": "past_due"})
                _sb_log_event(brand["brand_id"], "payment_failed", "stripe", payload)
        return {"handled": True}

    def _handle_subscription_updated(self, payload: dict) -> dict:
        sub = payload.get("data", {}).get("object", {})
        subscription_id = sub.get("id")
        if subscription_id:
            brand = _sb_get_brand_by_stripe_sub(subscription_id)
            if brand:
                status_map = {"active": "active", "canceled": "cancelled", "past_due": "past_due"}
                new_status = status_map.get(sub.get("status"), sub.get("status"))
                _sb_update_subscription(brand["brand_id"], {"status": new_status})
        return {"handled": True}

    def _handle_subscription_deleted(self, payload: dict) -> dict:
        sub = payload.get("data", {}).get("object", {})
        subscription_id = sub.get("id")
        if subscription_id:
            brand = _sb_get_brand_by_stripe_sub(subscription_id)
            if brand:
                _sb_update_subscription(brand["brand_id"], {"status": "cancelled"})
                _sb_log_event(brand["brand_id"], "subscription_cancelled", "stripe", payload)
        return {"handled": True}

    def cancel_subscription(self, subscription_id: str) -> bool:
        result = self._request("POST", f"/subscriptions/{subscription_id}", {"cancel_at_period_end": "true"})
        return bool(result)

    def reactivate_subscription(self, subscription_id: str) -> bool:
        result = self._request("POST", f"/subscriptions/{subscription_id}", {"cancel_at_period_end": "false"})
        return bool(result)


class RazorpayProvider(PaymentProvider):
    """Razorpay payment provider."""

    PLAN_PRICES = {
        "starter": 299900,  # In paise
        "growth": 999900,
        "enterprise": 2999900
    }

    def __init__(self):
        self.key_id = os.environ.get("RAZORPAY_KEY_ID", "")
        self.key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")

    def _request(self, method, path, data=None):
        if not self.key_id or not self.key_secret:
            return None
        import base64
        auth = base64.b64encode(f"{self.key_id}:{self.key_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json"
        }
        url = f"https://api.razorpay.com/v1{path}"
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                resp = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == "DELETE":
                resp = requests.delete(url, headers=headers, timeout=30)
            else:
                resp = requests.request(method, url, json=data, headers=headers, timeout=30)
            return resp.json() if resp.text else None
        except Exception as e:
            print(f"⚠️ [Razorpay] {e}")
            return None

    def create_checkout(self, brand_id: str, plan_tier: str, success_url: str, cancel_url: str) -> dict:
        plan_id = os.environ.get(f"RAZORPAY_PLAN_{plan_tier.upper()}", "")
        if not plan_id:
            return {"error": f"Razorpay plan not configured for {plan_tier}"}

        result = self._request("POST", "/subscriptions", {
            "plan_id": plan_id,
            "customer_notify": 1,
            "notes": {"brand_id": brand_id, "plan_tier": plan_id}
        })

        if result:
            return {"subscription_id": result.get("id"), "short_url": result.get("short_url")}
        return {"error": "Failed to create Razorpay subscription"}

    def handle_webhook(self, event_type: str, payload: dict) -> dict:
        handlers = {
            "subscription.activated": self._handle_activated,
            "subscription.charged": self._handle_charged,
            "subscription.cancelled": self._handle_cancelled,
            "subscription.paused": self._handle_paused,
        }
        handler = handlers.get(event_type)
        if handler:
            return handler(payload)
        return {"handled": False}

    def _handle_activated(self, payload: dict) -> dict:
        subscription = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        brand_id = subscription.get("notes", {}).get("brand_id")
        if brand_id:
            _sb_update_subscription(brand_id, {"status": "active"})
            _sb_log_event(brand_id, "subscription_activated", "razorpay", payload)
        return {"handled": True}

    def _handle_charged(self, payload: dict) -> dict:
        subscription = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        brand_id = subscription.get("notes", {}).get("brand_id")
        if brand_id:
            _sb_update_subscription(brand_id, {"monthly_recommendations_used": 0})
            _sb_log_event(brand_id, "invoice_paid", "razorpay", payload)
        return {"handled": True}

    def _handle_cancelled(self, payload: dict) -> dict:
        subscription = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        brand_id = subscription.get("notes", {}).get("brand_id")
        if brand_id:
            _sb_update_subscription(brand_id, {"status": "cancelled"})
            _sb_log_event(brand_id, "subscription_cancelled", "razorpay", payload)
        return {"handled": True}

    def _handle_paused(self, payload: dict) -> dict:
        subscription = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        brand_id = subscription.get("notes", {}).get("brand_id")
        if brand_id:
            _sb_update_subscription(brand_id, {"status": "paused"})
        return {"handled": True}

    def cancel_subscription(self, subscription_id: str) -> bool:
        result = self._request("POST", f"/subscriptions/{subscription_id}/cancel")
        return bool(result)

    def reactivate_subscription(self, subscription_id: str) -> bool:
        result = self._request("POST", f"/subscriptions/{subscription_id}/resume")
        return bool(result)


# ── Helper functions ──────────────────────────────────────────────────────

def _get_supabase_url():
    return os.environ.get("SUPABASE_URL", "")

def _get_supabase_key():
    return os.environ.get("SUPABASE_KEY", "")


def _sb_request(method, path, payload=None):
    url = _get_supabase_url()
    key = _get_supabase_key()
    if not url or not key:
        return None
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    full_url = f"{url.rstrip('/')}{path}"
    try:
        if method == "GET":
            resp = requests.get(full_url, headers=headers, timeout=15)
        elif method == "POST":
            resp = requests.post(full_url, json=payload, headers=headers, timeout=15)
        elif method == "PATCH":
            resp = requests.patch(full_url, json=payload, headers=headers, timeout=15)
        else:
            resp = requests.request(method, full_url, json=payload, headers=headers, timeout=15)
        return resp.json() if resp.text else None
    except Exception:
        return None


def _sb_update_subscription(brand_id: str, data: dict):
    _sb_request("PATCH", f"/rest/v1/brand_subscriptions?brand_id=eq.{brand_id}", data)


def _sb_log_event(brand_id: str, event_type: str, provider: str, payload: dict):
    _sb_request("POST", "/rest/v1/subscription_events", {
        "brand_id": brand_id,
        "event_type": event_type,
        "provider": provider,
        "payload": payload
    })


def _sb_get_brand_by_stripe_sub(subscription_id: str) -> dict:
    result = _sb_request("GET", f"/rest/v1/brand_subscriptions?stripe_subscription_id=eq.{subscription_id}&select=brand_id")
    if result and len(result) > 0:
        return result[0]
    return None


def get_provider(provider_name: str) -> PaymentProvider:
    """Get payment provider by name."""
    if provider_name == "stripe":
        return StripeProvider()
    elif provider_name == "razorpay":
        return RazorpayProvider()
    raise ValueError(f"Unknown provider: {provider_name}")
