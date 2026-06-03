from http.server import BaseHTTPRequestHandler
import json
import os
import io
from datetime import datetime
from urllib.parse import urlparse

import boto3
import requests
from PIL import Image
from rectpack import newPacker


DPI = 300
ROLL_WIDTH_IN = 22
ROLL_WIDTH_PX = ROLL_WIDTH_IN * DPI  # 6600
CUT_MARGIN_IN = 0.5
CUT_MARGIN_PX = int(CUT_MARGIN_IN * DPI)  # 150


def get_supabase():
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception as e:
        print(f"[GANG] Supabase init error: {e}")
    return None


def s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def download_image(url):
    r = requests.get(url, timeout=45)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    return img


def choose_image_url(job):
    return (
        job.get("high_res_master_url")
        or job.get("design_file_url")
        or job.get("master_file_url")
        or ""
    )


def build_layout(images):
    """
    Pack images onto a fixed-width 22in roll with 0.5in cut margins.
    Uses rectpack with progressively taller bins until all images fit.
    """
    if not images:
        return [], 0

    rects = []
    for idx, img in enumerate(images):
        rects.append((img.width + 2 * CUT_MARGIN_PX, img.height + 2 * CUT_MARGIN_PX, idx))

    start_h = max(max(r[1] for r in rects), 2000)
    max_h = 120000
    bin_h = start_h

    while bin_h <= max_h:
        packer = newPacker(rotation=False)
        for w, h, rid in rects:
            packer.add_rect(w, h, rid=rid)
        packer.add_bin(ROLL_WIDTH_PX, bin_h, count=1)
        packer.pack()

        packed = packer.rect_list()
        if len(packed) == len(rects):
            placements = []
            used_h = 0
            for _, x, y, w, h, rid in packed:
                px = x + CUT_MARGIN_PX
                py = y + CUT_MARGIN_PX
                placements.append((rid, px, py))
                used_h = max(used_h, y + h)
            return placements, used_h

        bin_h *= 2

    raise RuntimeError("Could not pack all jobs into configured gang-sheet limits.")


def create_gang_sheet(jobs):
    images = []
    resolved_jobs = []
    for j in jobs:
        image_url = choose_image_url(j)
        if not image_url:
            continue
        try:
            img = download_image(image_url)
            images.append(img)
            resolved_jobs.append(j)
        except Exception as e:
            print(f"[GANG] Failed image download for job={j.get('id')}: {e}")

    if not images:
        return None, None, []

    placements, used_h = build_layout(images)
    canvas_h = max(used_h + CUT_MARGIN_PX, 2000)
    canvas = Image.new("RGBA", (ROLL_WIDTH_PX, canvas_h), (0, 0, 0, 0))

    used_job_ids = []
    for rid, x, y in placements:
        canvas.paste(images[rid], (x, y), images[rid])
        used_job_ids.append(resolved_jobs[rid].get("id"))

    png_buf = io.BytesIO()
    canvas.save(png_buf, format="PNG", optimize=True)
    png_bytes = png_buf.getvalue()

    pdf_buf = io.BytesIO()
    canvas.convert("RGB").save(pdf_buf, format="PDF", resolution=DPI)
    pdf_bytes = pdf_buf.getvalue()
    return png_bytes, pdf_bytes, used_job_ids


def upload_gang_sheet_assets(png_bytes, pdf_bytes):
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    region = os.environ.get("AWS_REGION", "us-east-1")
    if not bucket:
        raise RuntimeError("AWS_S3_BUCKET not configured")

    client = s3_client()
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    png_key = f"gang_sheets/gang_sheet_{stamp}.png"
    pdf_key = f"gang_sheets/gang_sheet_{stamp}.pdf"

    client.put_object(
        Bucket=bucket,
        Key=png_key,
        Body=png_bytes,
        ContentType="image/png",
    )
    client.put_object(
        Bucket=bucket,
        Key=pdf_key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )

    base = f"https://{bucket}.s3.{region}.amazonaws.com"
    return f"{base}/{png_key}", f"{base}/{pdf_key}"


class handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(payload, default=str).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/fulfillment/generate_gang_sheet":
            self.send_json(200, {
                "status": "ok",
                "message": "Use POST to generate today's DTF gang sheet.",
                "roll_width_px": ROLL_WIDTH_PX,
                "cut_margin_px": CUT_MARGIN_PX
            })
            return
        self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/fulfillment/generate_gang_sheet":
            self.send_json(404, {"error": "Not found"})
            return

        sb = get_supabase()
        if not sb:
            self.send_json(500, {"error": "Supabase not configured"})
            return

        try:
            res = (
                sb.table("design_orders")
                .select("id,shopify_order_id,unique_product_id,high_res_master_url,design_file_url,master_file_url,status,fulfillment_status")
                .eq("status", "paid")
                .eq("fulfillment_status", "unfulfilled")
                .execute()
            )
            jobs = res.data or []
            if not jobs:
                self.send_json(200, {"status": "ok", "message": "No eligible print jobs found.", "count": 0})
                return

            png_bytes, pdf_bytes, used_job_ids = create_gang_sheet(jobs)
            if not png_bytes:
                self.send_json(422, {"error": "No valid high-res print files could be fetched."})
                return

            png_url, pdf_url = upload_gang_sheet_assets(png_bytes, pdf_bytes)

            # Mark jobs as queued for batch fulfillment.
            if used_job_ids:
                (
                    sb.table("design_orders")
                    .update({
                        "fulfillment_status": "batch_ready",
                        "updated_at": datetime.utcnow().isoformat(),
                    })
                    .in_("id", used_job_ids)
                    .execute()
                )

            self.send_json(200, {
                "status": "ok",
                "count": len(used_job_ids),
                "gang_sheet_png_url": png_url,
                "gang_sheet_pdf_url": pdf_url,
                "roll_width_px": ROLL_WIDTH_PX,
                "cut_margin_px": CUT_MARGIN_PX
            })
        except Exception as e:
            print(f"[GANG] generation error: {e}")
            self.send_json(500, {"error": f"Gang sheet generation failed: {str(e)}"})
