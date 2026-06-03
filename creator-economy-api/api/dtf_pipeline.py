from http.server import BaseHTTPRequestHandler
import base64
import hashlib
import hmac
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageEnhance


DPI = 300
A3_WIDTH_PX = 3508
A3_HEIGHT_PX = 4961
EDGE_MARGIN_MM = 15
GAP_MM = 10
MAX_DESIGNS_PER_PAGE = 4
PRESIGNED_URL_SECONDS = 3600

LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def env_truthy(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return default


def mm_to_px(mm: float) -> int:
    return int(round(mm * DPI / 25.4))


def json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, default=str).encode("utf-8")


def verify_shopify_hmac(body: bytes, hmac_header: str, secret: str) -> bool:
    if not secret:
        return True
    if not hmac_header:
        return False

    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(computed, hmac_header)


def parse_line_item_properties(properties: Any) -> Dict[str, str]:
    if isinstance(properties, dict):
        return {str(k): "" if v is None else str(v) for k, v in properties.items()}

    parsed: Dict[str, str] = {}
    if not isinstance(properties, list):
        return parsed

    for prop in properties:
        if not isinstance(prop, dict):
            continue
        name = prop.get("name") or prop.get("key")
        if not name:
            continue
        value = prop.get("value", "")
        parsed[str(name)] = "" if value is None else str(value)
    return parsed


def normalize_product_type(value: Any, fallback: str = "") -> str:
    raw = f"{value or ''} {fallback or ''}".strip().lower()
    if "hood" in raw:
        return "hoodie"
    if "tee" in raw or "t-shirt" in raw or "tshirt" in raw or "shirt" in raw:
        return "tee"
    return "tee"


def extract_customer(order: Dict[str, Any]) -> Dict[str, str]:
    customer = order.get("customer") or {}
    shipping = order.get("shipping_address") or {}
    email = (
        order.get("email")
        or customer.get("email")
        or order.get("contact_email")
        or "unknown"
    )
    first_name = customer.get("first_name") or shipping.get("first_name") or ""
    last_name = customer.get("last_name") or shipping.get("last_name") or ""
    full_name = order.get("name") or f"{first_name} {last_name}".strip()
    return {
        "id": str(customer.get("id") or ""),
        "email": str(email),
        "first_name": str(first_name),
        "last_name": str(last_name),
        "name": str(full_name or email),
    }


def extract_dtf_jobs(order: Dict[str, Any]) -> List[Dict[str, Any]]:
    order_id = str(order.get("id") or order.get("order_id") or "")
    order_number = str(order.get("order_number") or order.get("name") or order_id)
    customer = extract_customer(order)
    jobs: List[Dict[str, Any]] = []

    for index, item in enumerate(order.get("line_items") or []):
        props = parse_line_item_properties(item.get("properties") or [])
        design_uuid = (
            props.get("_design_uuid")
            or props.get("_unique_product_id")
            or props.get("design_uuid")
            or ""
        ).strip()
        if not design_uuid:
            continue

        line_item_id = str(item.get("id") or item.get("key") or index)
        product_type = normalize_product_type(
            props.get("_product_type") or item.get("product_type"),
            f"{item.get('title', '')} {item.get('variant_title', '')}",
        )
        source_url = (
            props.get("_design_file_url")
            or props.get("_design_url")
            or props.get("_design_preview_url")
            or props.get("Custom Design")
            or props.get("custom_design")
            or ""
        ).strip()

        jobs.append({
            "job_id": f"{order_id or 'order'}-{line_item_id}-{design_uuid}",
            "order_id": order_id,
            "order_number": order_number,
            "line_item_id": line_item_id,
            "design_uuid": design_uuid,
            "customer_email": customer["email"],
            "customer_name": customer["name"],
            "customer_id": customer["id"],
            "product_type": product_type,
            "quantity": max(1, safe_int(item.get("quantity"), 1)),
            "size": props.get("_size") or item.get("variant_title") or "",
            "color": props.get("_color") or "",
            "design_title": props.get("_design_title") or item.get("title") or design_uuid,
            "source_url": source_url,
            "s3_key": props.get("_design_s3_key") or "",
            "shopify_product_id": str(item.get("product_id") or ""),
            "shopify_variant_id": str(item.get("variant_id") or ""),
        })

    return jobs


def is_paid_order(order: Dict[str, Any], topic: str) -> bool:
    if topic == "orders/paid":
        return True
    status = str(order.get("financial_status") or "").lower()
    if status in {"paid", "authorized", "partially_paid"}:
        return True
    if topic in {"orders/create", "orders/updated"} and not status:
        return True
    return False


def http_download(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mynarrative-dtf/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def s3_client():
    import boto3

    return boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=env_first("AWS_REGION", default="ap-south-1"),
    )


def design_bucket() -> str:
    return env_first("S3_DESIGN_BUCKET_NAME", "S3_BUCKET_NAME", "AWS_S3_BUCKET", default="mynarrative-dtf")


def print_bucket() -> str:
    return env_first("S3_PRINT_BUCKET_NAME", "S3_BUCKET_NAME", "AWS_S3_BUCKET", default="mynarrative-dtf")


def download_design_asset(job: Dict[str, Any]) -> bytes:
    if job.get("source_url", "").startswith(("http://", "https://")):
        return http_download(job["source_url"])

    bucket = design_bucket()
    key = job.get("s3_key") or f"designs/{job['customer_email']}/{job['design_uuid']}.png"
    try:
        response = s3_client().get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    except Exception as s3_error:
        preview_base = env_first("DTF_PREVIEW_CDN_BASE", default="https://cdn.mynarrative.store/previews")
        preview_url = f"{preview_base.rstrip('/')}/{job['design_uuid']}.jpg"
        try:
            return http_download(preview_url)
        except Exception:
            raise RuntimeError(f"Design download failed for s3://{bucket}/{key}: {s3_error}")


def image_to_png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", dpi=(DPI, DPI), optimize=False)
    return output.getvalue()


def image_has_alpha(image: Image.Image) -> bool:
    if image.mode not in ("RGBA", "LA"):
        return False
    alpha = image.getchannel("A")
    extrema = alpha.getextrema()
    return bool(extrema and extrema[0] < 255)


def basic_white_background_removal(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = []
    for r, g, b, a in rgba.getdata():
        if r > 245 and g > 245 and b > 245 and a > 200:
            pixels.append((r, g, b, 0))
        else:
            pixels.append((r, g, b, a))
    rgba.putdata(pixels)
    return rgba


def remove_background(image_bytes: bytes, allow_rembg: bool = True) -> Tuple[bytes, str]:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    if image_has_alpha(image):
        return image_to_png_bytes(image), "already_transparent"

    if allow_rembg and not env_truthy("DTF_DISABLE_REMBG"):
        try:
            from rembg import remove

            output = remove(image_bytes)
            cleaned = Image.open(io.BytesIO(output)).convert("RGBA")
            return image_to_png_bytes(cleaned), "rembg"
        except Exception as exc:
            print(f"[DTF] rembg failed, using white-threshold fallback: {exc}")

    cleaned = basic_white_background_removal(image)
    return image_to_png_bytes(cleaned), "basic_threshold"


def upscale_for_print(image_bytes: bytes, min_width: int = 3000, min_height: int = 3000) -> Tuple[bytes, Dict[str, Any]]:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    original_size = image.size
    width, height = image.size
    scale = max(1.0, float(min_width) / width, float(min_height) / height)

    if scale > 1:
        image = image.resize((int(width * scale), int(height * scale)), LANCZOS)
        image = ImageEnhance.Sharpness(image).enhance(1.35)
        image = ImageEnhance.Contrast(image).enhance(1.05)

    if image.width % 2:
        image = image.crop((0, 0, image.width - 1, image.height))
    if image.height % 2:
        image = image.crop((0, 0, image.width, image.height - 1))

    return image_to_png_bytes(image), {
        "original_size": original_size,
        "final_size": image.size,
        "scale": scale,
    }


def run_content_safety_check(image_bytes: bytes) -> Dict[str, Any]:
    if env_truthy("DTF_SKIP_OPENAI_SAFETY") or not os.environ.get("OPENAI_API_KEY"):
        return {"is_safe": True, "flags": [], "skipped": True}

    payload = {
        "model": env_first("OPENAI_MODERATION_MODEL", default="omni-moderation-latest"),
        "input": [{
            "type": "image_url",
            "image_url": {
                "url": "data:image/png;base64," + base64.b64encode(image_bytes).decode("utf-8")
            },
        }],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/moderations",
        data=json_bytes(payload),
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        if env_truthy("DTF_FAIL_OPEN_ON_SAFETY_ERROR"):
            return {"is_safe": True, "flags": ["safety_check_error"], "error": str(exc)}
        return {"is_safe": False, "flags": ["safety_check_error"], "error": str(exc)}

    results = data.get("results") or []
    if not results:
        return {"is_safe": True, "flags": []}
    result = results[0]
    categories = result.get("categories") or {}
    scores = result.get("category_scores") or {}
    flags = [name for name, flagged in categories.items() if flagged]
    is_safe = not flags
    return {"is_safe": is_safe, "flags": flags, "scores": scores}


def cell_boxes(count: int) -> List[Tuple[int, int, int, int]]:
    margin = mm_to_px(EDGE_MARGIN_MM)
    gap = mm_to_px(GAP_MM)
    usable_w = A3_WIDTH_PX - 2 * margin
    usable_h = A3_HEIGHT_PX - 2 * margin

    if count <= 1:
        return [(margin, margin, margin + usable_w, margin + usable_h)]

    if count == 2:
        cell_w = (usable_w - gap) // 2
        return [
            (margin, margin, margin + cell_w, margin + usable_h),
            (margin + cell_w + gap, margin, margin + 2 * cell_w + gap, margin + usable_h),
        ]

    cell_w = (usable_w - gap) // 2
    cell_h = (usable_h - gap) // 2
    return [
        (margin, margin, margin + cell_w, margin + cell_h),
        (margin + cell_w + gap, margin, margin + 2 * cell_w + gap, margin + cell_h),
        (margin, margin + cell_h + gap, margin + cell_w, margin + 2 * cell_h + gap),
        (margin + cell_w + gap, margin + cell_h + gap, margin + 2 * cell_w + gap, margin + 2 * cell_h + gap),
    ][:count]


def paste_centered(canvas: Image.Image, source: Image.Image, box: Tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = box
    max_w = x2 - x1
    max_h = y2 - y1
    scale = min(float(max_w) / source.width, float(max_h) / source.height, 1.0)
    placed = source
    if scale < 1:
        placed = source.resize((int(source.width * scale), int(source.height * scale)), LANCZOS)
    x = x1 + (max_w - placed.width) // 2
    y = y1 + (max_h - placed.height) // 2
    canvas.paste(placed, (x, y), placed)


def create_a3_pdf(processed_png: bytes, job: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
    image = Image.open(io.BytesIO(processed_png)).convert("RGBA")
    copies = max(1, safe_int(job.get("quantity"), 1))
    pages: List[Image.Image] = []
    remaining = copies

    while remaining > 0:
        page_count = min(MAX_DESIGNS_PER_PAGE, remaining)
        page = Image.new("RGB", (A3_WIDTH_PX, A3_HEIGHT_PX), "white")
        for box in cell_boxes(page_count):
            paste_centered(page, image, box)
        pages.append(page)
        remaining -= page_count

    output = io.BytesIO()
    first, rest = pages[0], pages[1:]
    first.save(
        output,
        format="PDF",
        resolution=DPI,
        save_all=bool(rest),
        append_images=rest,
    )
    return output.getvalue(), {
        "pages": len(pages),
        "copies": copies,
        "sheet": "A3",
        "dpi": DPI,
    }


def upload_pdf_to_s3(pdf_bytes: bytes, job: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    safe_order_id = urllib.parse.quote(str(job.get("order_id") or "manual"), safe="")
    safe_uuid = urllib.parse.quote(str(job["design_uuid"]), safe="")
    safe_line = urllib.parse.quote(str(job.get("line_item_id") or "line"), safe="")
    key = f"print-queue/{safe_order_id}/{safe_line}-{safe_uuid}.pdf"

    if dry_run:
        return {
            "bucket": print_bucket(),
            "key": key,
            "url": f"dry-run://{print_bucket()}/{key}",
            "presigned_url": f"dry-run://{print_bucket()}/{key}?expires={PRESIGNED_URL_SECONDS}",
            "bytes": len(pdf_bytes),
        }

    bucket = print_bucket()
    client = s3_client()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
        Metadata={
            "order_id": str(job.get("order_id") or ""),
            "design_uuid": str(job.get("design_uuid") or ""),
            "product_type": str(job.get("product_type") or ""),
        },
    )
    presigned = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=PRESIGNED_URL_SECONDS,
    )
    region = env_first("AWS_REGION", default="ap-south-1")
    public_base = env_first("DTF_PRINT_CDN_BASE", default=f"https://{bucket}.s3.{region}.amazonaws.com")
    return {
        "bucket": bucket,
        "key": key,
        "url": f"{public_base.rstrip('/')}/{key}",
        "presigned_url": presigned,
        "bytes": len(pdf_bytes),
    }


def post_json(url: str, payload: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json_bytes(payload),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {"body": body}
        return {"status_code": response.status, "response": data}


def notify_operator(job: Dict[str, Any], upload: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    payload = {
        "order_id": job.get("order_id"),
        "order_number": job.get("order_number"),
        "design_uuid": job.get("design_uuid"),
        "presigned_url": upload.get("presigned_url"),
        "print_file_url": upload.get("url"),
        "print_file_key": upload.get("key"),
        "product_type": job.get("product_type"),
        "quantity": job.get("quantity"),
        "size": job.get("size"),
        "color": job.get("color"),
        "customer_name": job.get("customer_name"),
        "customer_email": job.get("customer_email"),
        "dispatch_by_date": job.get("dispatch_by_date") or "",
    }
    webhook_url = os.environ.get("DTF_OPERATOR_WEBHOOK_URL", "")
    if dry_run or not webhook_url:
        return {"sent": False, "reason": "dry_run" if dry_run else "not_configured", "payload": payload}
    try:
        return {"sent": True, **post_json(webhook_url, payload, timeout=12)}
    except Exception as exc:
        return {"sent": False, "error": str(exc), "payload": payload}


def alert_slack(message: str, details: Dict[str, Any]) -> None:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        return
    try:
        post_json(webhook_url, {"text": message, "details": details}, timeout=5)
    except Exception as exc:
        print(f"[DTF] Slack alert failed: {exc}")


def supabase_headers() -> Tuple[str, str, Dict[str, str]]:
    url = os.environ.get("SUPABASE_URL", "")
    key = env_first("SUPABASE_SERVICE_KEY", "SUPABASE_KEY")
    return url, key, {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Prefer": "return=minimal",
    }


def update_design_order_dtf_status(job: Dict[str, Any], status: str, upload: Optional[Dict[str, Any]] = None, error: str = "") -> None:
    url, key, headers = supabase_headers()
    if not url or not key or not job.get("order_id"):
        return

    patch = {
        "dtf_status": status,
        "dtf_error": error[:500] if error else None,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if status == "completed":
        patch["dtf_processed_at"] = datetime.utcnow().isoformat()
    if upload:
        patch["print_file_url"] = upload.get("url")
        patch["print_file_key"] = upload.get("key")

    params = {
        "shopify_order_id": f"eq.{job['order_id']}",
        "unique_product_id": f"eq.{job['design_uuid']}",
    }
    endpoint = f"{url.rstrip('/')}/rest/v1/design_orders?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(endpoint, data=json_bytes(patch), headers=headers, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as exc:
        print(f"[DTF] Supabase dtf_status update skipped/failed: {exc}")


def update_shopify_order_with_print_file(job: Dict[str, Any], upload: Dict[str, Any]) -> None:
    store_url = env_first("SHOPIFY_STORE_URL", "SHOPIFY_SHOP_DOMAIN").strip().rstrip("/")
    token = env_first("SHOPIFY_ADMIN_ACCESS_TOKEN", "SHOPIFY_ACCESS_TOKEN").strip()
    api_version = env_first("SHOPIFY_API_VERSION", default="2024-01")
    order_id = str(job.get("order_id") or "")
    print_url = upload.get("url") or upload.get("presigned_url")

    if not store_url or not token or not order_id or not print_url:
        return
    if not store_url.startswith(("http://", "https://")):
        store_url = f"https://{store_url}"

    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    metafield_url = f"{store_url}/admin/api/{api_version}/orders/{order_id}/metafields.json"
    body = {
        "metafield": {
            "namespace": "dtf",
            "key": f"print_file_{job.get('line_item_id')}",
            "type": "url",
            "value": print_url,
        }
    }
    try:
        req = urllib.request.Request(metafield_url, data=json_bytes(body), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15):
            pass
    except Exception as exc:
        print(f"[DTF] Shopify print-file metafield update failed: {exc}")


def trigger_personality_card(job: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    webhook_url = os.environ.get("PERSONALITY_CARD_WEBHOOK_URL", "")
    if dry_run or not webhook_url:
        return {"sent": False, "reason": "dry_run" if dry_run else "not_configured"}
    try:
        return {"sent": True, **post_json(webhook_url, {"order_id": job.get("order_id")}, timeout=3)}
    except Exception as exc:
        return {"sent": False, "error": str(exc)}


def process_dtf_job(
    job: Dict[str, Any],
    source_image_bytes: Optional[bytes] = None,
    dry_run: Optional[bool] = None,
) -> Dict[str, Any]:
    dry_run = env_truthy("DTF_DRY_RUN") if dry_run is None else dry_run
    started = time.time()
    steps: List[str] = []
    upload: Optional[Dict[str, Any]] = None

    try:
        update_design_order_dtf_status(job, "processing")

        image_bytes = source_image_bytes if source_image_bytes is not None else download_design_asset(job)
        steps.append("download")

        safety = run_content_safety_check(image_bytes)
        if not safety.get("is_safe"):
            update_design_order_dtf_status(job, "failed", error=f"Content flagged: {safety.get('flags')}")
            return {
                "status": "unsafe",
                "design_uuid": job["design_uuid"],
                "steps_completed": steps,
                "content_safety": safety,
                "processing_time_seconds": round(time.time() - started, 3),
            }
        steps.append("content_safety")

        transparent_bytes, bg_method = remove_background(image_bytes, allow_rembg=not dry_run)
        steps.append("background_removed")

        upscaled_bytes, image_meta = upscale_for_print(transparent_bytes)
        steps.append("upscaled")

        pdf_bytes, pdf_meta = create_a3_pdf(upscaled_bytes, job)
        steps.append("pdf_generated")

        upload = upload_pdf_to_s3(pdf_bytes, job, dry_run=dry_run)
        steps.append("uploaded")

        operator = notify_operator(job, upload, dry_run=dry_run)
        steps.append("operator_notified" if operator.get("sent") else "operator_notification_skipped")

        update_shopify_order_with_print_file(job, upload)
        update_design_order_dtf_status(job, "completed", upload=upload)
        card = trigger_personality_card(job, dry_run=dry_run)

        return {
            "status": "completed",
            "design_uuid": job["design_uuid"],
            "order_id": job.get("order_id"),
            "line_item_id": job.get("line_item_id"),
            "product_type": job.get("product_type"),
            "quantity": job.get("quantity"),
            "steps_completed": steps,
            "background_method": bg_method,
            "image": image_meta,
            "pdf": pdf_meta,
            "print_file_url": upload.get("url"),
            "print_file_key": upload.get("key"),
            "presigned_url": upload.get("presigned_url"),
            "operator_notification": operator,
            "personality_card": card,
            "processing_time_seconds": round(time.time() - started, 3),
            "dry_run": dry_run,
        }
    except Exception as exc:
        error = str(exc)
        update_design_order_dtf_status(job, "failed", upload=upload, error=error)
        alert_slack("[DTF] Print pipeline failed", {"job": job, "error": error})
        return {
            "status": "failed",
            "design_uuid": job.get("design_uuid"),
            "order_id": job.get("order_id"),
            "steps_completed": steps,
            "error": error,
            "processing_time_seconds": round(time.time() - started, 3),
            "dry_run": dry_run,
        }


def process_order_payload(
    order: Dict[str, Any],
    topic: str = "",
    source_image_bytes: Optional[bytes] = None,
    dry_run: Optional[bool] = None,
) -> Dict[str, Any]:
    topic = (topic or "").lower()
    if order.get("cancelled_at"):
        return {"status": "ignored", "reason": "cancelled_order", "order_id": order.get("id")}
    if not is_paid_order(order, topic):
        return {
            "status": "ignored",
            "reason": "order_not_paid",
            "order_id": order.get("id"),
            "financial_status": order.get("financial_status"),
        }

    jobs = extract_dtf_jobs(order)
    if not jobs:
        return {"status": "ignored", "reason": "no_dtf_line_items", "order_id": order.get("id")}

    results = [
        process_dtf_job(job, source_image_bytes=source_image_bytes, dry_run=dry_run)
        for job in jobs
    ]
    failed = [result for result in results if result.get("status") not in {"completed", "unsafe"}]
    unsafe = [result for result in results if result.get("status") == "unsafe"]
    status = "processed"
    if failed:
        status = "partial_error" if len(failed) < len(results) else "error"
    elif unsafe:
        status = "flagged"

    return {
        "status": status,
        "order_id": order.get("id"),
        "order_number": order.get("order_number") or order.get("name"),
        "jobs_found": len(jobs),
        "jobs": results,
    }


def handle_shopify_webhook(body: bytes, headers: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    secret = os.environ.get("SHOPIFY_WEBHOOK_SECRET", "")
    hmac_header = headers.get("X-Shopify-Hmac-Sha256") or headers.get("x-shopify-hmac-sha256") or ""
    if not verify_shopify_hmac(body, hmac_header, secret):
        return 401, {"error": "Unauthorized - invalid Shopify HMAC"}

    try:
        order = json.loads(body.decode("utf-8"))
    except Exception:
        return 400, {"error": "Invalid JSON"}

    topic = headers.get("X-Shopify-Topic") or headers.get("x-shopify-topic") or ""
    return 200, process_order_payload(order, topic=topic)


def manual_process_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    design_uuid = payload.get("design_uuid") or payload.get("unique_product_id")
    if not design_uuid:
        return {"status": "error", "error": "design_uuid is required"}

    job = {
        "job_id": payload.get("job_id") or f"manual-{design_uuid}",
        "order_id": payload.get("order_id") or f"manual-{int(time.time())}",
        "order_number": payload.get("order_number") or "manual",
        "line_item_id": payload.get("line_item_id") or "manual",
        "design_uuid": design_uuid,
        "customer_email": payload.get("customer_email") or payload.get("user_email") or payload.get("user_id") or "manual",
        "customer_name": payload.get("customer_name") or "Manual DTF Job",
        "customer_id": payload.get("customer_id") or "",
        "product_type": normalize_product_type(payload.get("product_type")),
        "quantity": max(1, safe_int(payload.get("quantity"), 1)),
        "size": payload.get("size") or "",
        "color": payload.get("color") or "",
        "design_title": payload.get("design_title") or payload.get("title") or design_uuid,
        "source_url": payload.get("design_url") or payload.get("source_url") or "",
        "s3_key": payload.get("s3_key") or "",
        "shopify_product_id": payload.get("shopify_product_id") or "",
        "shopify_variant_id": payload.get("shopify_variant_id") or "",
    }
    dry_run_raw = payload.get("dry_run")
    dry_run = None if dry_run_raw is None else str(dry_run_raw).lower() in {"1", "true", "yes", "on"}
    return process_dtf_job(job, dry_run=dry_run)


class handler(BaseHTTPRequestHandler):
    def send_json(self, status_code: int, payload: Dict[str, Any]) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-Shopify-Hmac-Sha256, X-Shopify-Topic, X-Shopify-Shop-Domain",
        )
        self.end_headers()
        self.wfile.write(json_bytes(payload))

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-Shopify-Hmac-Sha256, X-Shopify-Topic, X-Shopify-Shop-Domain",
        )
        self.end_headers()

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path in {
            "/api/dtf/health",
            "/api/webhook/shopify/health",
            "/api/dtf_pipeline",
            "/api/webhook/shopify",
        }:
            self.send_json(200, {
                "status": "ok",
                "service": "My Narrative DTF pipeline",
                "routes": [
                    "POST /api/webhook/shopify",
                    "POST /api/dtf/process",
                    "GET /api/dtf/health",
                ],
                "dry_run": env_truthy("DTF_DRY_RUN"),
                "s3_bucket": print_bucket(),
            })
            return
        self.send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        content_length = safe_int(self.headers.get("Content-Length"), 0)
        body = self.rfile.read(content_length)

        if path in {"/api/webhook/shopify", "/api/dtf_pipeline"}:
            status, payload = handle_shopify_webhook(body, dict(self.headers))
            self.send_json(status, payload)
            return

        if path in {"/api/dtf/process", "/api/process-design"}:
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                self.send_json(400, {"error": "Invalid JSON"})
                return

            api_key = os.environ.get("DTF_API_KEY", "")
            auth = self.headers.get("Authorization", "")
            if api_key and auth != f"Bearer {api_key}":
                self.send_json(401, {"error": "Unauthorized"})
                return

            result = manual_process_payload(payload)
            self.send_json(200 if result.get("status") != "error" else 400, result)
            return

        self.send_json(404, {"error": "Not found"})
