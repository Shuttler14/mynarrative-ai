import base64
import hashlib
import hmac
import io
import json
import os
import sys
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "creator-economy-api", "api"))

import dtf_pipeline


def make_png(size=(640, 640)):
    image = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((120, 120, size[0] - 120, size[1] - 120), fill=(57, 165, 150, 255))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class DTFPipelineTests(unittest.TestCase):
    def test_shopify_hmac_verification(self):
        body = b'{"id":123}'
        secret = "test_secret"
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        header = base64.b64encode(digest).decode("utf-8")

        self.assertTrue(dtf_pipeline.verify_shopify_hmac(body, header, secret))
        self.assertFalse(dtf_pipeline.verify_shopify_hmac(body, "invalid", secret))

    def test_extract_dtf_jobs_from_shopify_order(self):
        order = {
            "id": 987,
            "order_number": 1001,
            "financial_status": "paid",
            "email": "buyer@example.com",
            "line_items": [{
                "id": 111,
                "title": "Oversized Hoodie",
                "quantity": 2,
                "properties": [
                    {"name": "_design_uuid", "value": "design-abc"},
                    {"name": "_product_type", "value": "hoodie"},
                    {"name": "_design_file_url", "value": "https://cdn.example.com/design.png"},
                    {"name": "_color", "value": "black"},
                ],
            }],
        }

        jobs = dtf_pipeline.extract_dtf_jobs(order)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["design_uuid"], "design-abc")
        self.assertEqual(jobs[0]["product_type"], "hoodie")
        self.assertEqual(jobs[0]["quantity"], 2)
        self.assertEqual(jobs[0]["customer_email"], "buyer@example.com")

    def test_unpaid_order_is_ignored(self):
        result = dtf_pipeline.process_order_payload(
            {
                "id": 100,
                "financial_status": "pending",
                "line_items": [{
                    "properties": [{"name": "_design_uuid", "value": "design-abc"}],
                }],
            },
            topic="orders/updated",
            dry_run=True,
        )

        self.assertEqual(result["status"], "ignored")
        self.assertEqual(result["reason"], "order_not_paid")

    def test_order_payload_dry_run_processes_pdf_end_to_end(self):
        order = {
            "id": 12345,
            "order_number": 2001,
            "financial_status": "paid",
            "email": "buyer@example.com",
            "customer": {"id": 77, "first_name": "Ada", "last_name": "Lovelace"},
            "line_items": [{
                "id": 222,
                "title": "Custom Tee",
                "variant_title": "M / White",
                "quantity": 1,
                "properties": [
                    {"name": "_design_uuid", "value": "design-xyz"},
                    {"name": "_product_type", "value": "tee"},
                ],
            }],
        }

        env = {
            "DTF_DRY_RUN": "1",
            "DTF_SKIP_OPENAI_SAFETY": "1",
            "DTF_DISABLE_REMBG": "1",
        }
        with patch.dict(os.environ, env, clear=False):
            result = dtf_pipeline.process_order_payload(
                order,
                topic="orders/updated",
                source_image_bytes=make_png(),
            )

        self.assertEqual(result["status"], "processed")
        self.assertEqual(result["jobs_found"], 1)
        job = result["jobs"][0]
        self.assertEqual(job["status"], "completed")
        self.assertIn("pdf_generated", job["steps_completed"])
        self.assertTrue(job["print_file_key"].endswith("-design-xyz.pdf"))
        self.assertTrue(job["dry_run"])

    def test_shopify_webhook_handler_dry_run_with_hmac(self):
        order = {
            "id": 12346,
            "financial_status": "paid",
            "email": "buyer@example.com",
            "line_items": [{
                "id": 333,
                "title": "Custom Tee",
                "quantity": 1,
                "properties": [{"name": "_design_uuid", "value": "design-hmac"}],
            }],
        }
        body = json_bytes = json.dumps(order).encode("utf-8")
        secret = "shopify_secret"
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        header = base64.b64encode(digest).decode("utf-8")

        env = {
            "SHOPIFY_WEBHOOK_SECRET": secret,
            "DTF_DRY_RUN": "1",
            "DTF_SKIP_OPENAI_SAFETY": "1",
            "DTF_DISABLE_REMBG": "1",
        }
        with patch.dict(os.environ, env, clear=False):
            original_download = dtf_pipeline.download_design_asset
            try:
                dtf_pipeline.download_design_asset = lambda job: make_png()
                status, result = dtf_pipeline.handle_shopify_webhook(
                    json_bytes,
                    {
                        "X-Shopify-Hmac-Sha256": header,
                        "X-Shopify-Topic": "orders/updated",
                    },
                )
            finally:
                dtf_pipeline.download_design_asset = original_download

        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "processed")
        self.assertEqual(result["jobs"][0]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
