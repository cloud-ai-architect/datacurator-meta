"""Synthetic data generator for DataCurator demos and tests.

Generates a mixed-format corpus (PDFs, CSV, JSON, MD) and uploads to S3.
Used to:
- Smoke-test the end-to-end pipeline
- Provide demo data for the KB UI
- Power integration tests

Usage:
    python data-curator/generate.py --bucket datacurator-raw-dev --source demo
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3


def _seed_rng(seed: int) -> None:
    random.seed(seed)


def make_csv(num_rows: int = 100) -> str:
    """Generate a synthetic retail products CSV."""
    categories = ["apparel", "electronics", "home-goods", "beauty", "sports"]
    brands = ["Northwood", "Acme", "Globex", "Initech", "Hooli", "Vandelay"]
    rows = ["sku,name,category,brand,price_inr,stock,updated_at"]
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(num_rows):
        sku = f"SKU-{i:05d}"
        name = f"Product {i:03d}"
        cat = random.choice(categories)
        brand = random.choice(brands)
        price = round(random.uniform(99, 9999), 2)
        stock = random.randint(0, 500)
        ts = (base + timedelta(days=random.randint(0, 240))).isoformat()
        rows.append(f'{sku},"{name}",{cat},{brand},{price},{stock},{ts}')
    return "\n".join(rows) + "\n"


def make_jsonl(num_records: int = 50) -> str:
    """Generate synthetic order records as JSONL."""
    statuses = ["pending", "shipped", "delivered", "returned", "cancelled"]
    lines = []
    for i in range(num_records):
        record = {
            "order_id": f"ORD-{i:06d}",
            "customer_id": f"CUST-{random.randint(1, 200):04d}",
            "items": [
                {"sku": f"SKU-{random.randint(0, 99):05d}", "qty": random.randint(1, 5)}
                for _ in range(random.randint(1, 4))
            ],
            "total_inr": round(random.uniform(99, 50000), 2),
            "status": random.choice(statuses),
            "created_at": (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=random.randint(0, 240))).isoformat(),
        }
        lines.append(json.dumps(record))
    return "\n".join(lines) + "\n"


def make_markdown_policy() -> str:
    """Generate a synthetic returns policy as Markdown."""
    return """# Returns & Refunds Policy

## Overview

At our company, customer satisfaction is our top priority. If you are not
completely satisfied with your purchase, we are here to help.

## Return window

- **Standard items**: 30 days from delivery
- **Electronics**: 15 days from delivery
- **Final sale items**: No returns accepted

## Conditions

To be eligible for a return:

1. The item must be unused and in its original packaging
2. You must have the receipt or proof of purchase
3. The item must not be a final sale item

## Refund process

Once we receive your return, we will inspect the item and notify you of the
status of your refund. If approved, your refund will be processed within
7-10 business days.

## Contact

For questions about returns, please contact our support team at
support@example.com or call +1-555-123-4567.
"""


def make_html_faq() -> str:
    """Generate a synthetic HTML FAQ page."""
    faqs = [
        ("How do I track my order?", "Once your order ships, you will receive a tracking number via email. You can use this to track your package on our website."),
        ("What payment methods do you accept?", "We accept all major credit cards (Visa, Mastercard, Amex), PayPal, Apple Pay, and Google Pay."),
        ("Do you offer international shipping?", "Yes! We ship to over 50 countries. International shipping rates are calculated at checkout."),
        ("How do I contact customer support?", "Email us at support@example.com or use the live chat on our website. Our team is available 24/7."),
        ("Can I change or cancel my order?", "Orders can be modified or cancelled within 2 hours of placement. After that, please contact support."),
    ]
    rows = "\n".join(
        f"<h3>{q}</h3><p>{a}</p>" for q, a in faqs
    )
    return f"""<!DOCTYPE html>
<html>
<head><title>FAQ - Customer Help Center</title></head>
<body>
<h1>Frequently Asked Questions</h1>
{rows}
</body>
</html>"""


def make_pdf_bytes_simple(text: str) -> bytes:
    """Generate a minimal PDF (no library dependency).

    For the smoke test, we use a placeholder PDF (not a real PDF).
    In production, use Docling or reportlab for proper PDF generation.
    """
    # Minimal valid PDF (1 page, 1 line of text)
    content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
50 700 Td
({text[:50]}) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000109 00000 n
0000000209 00000 n
0000000300 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
367
%%EOF
"""
    return content.encode("latin-1")


def upload(s3_client, bucket: str, key: str, body: bytes | str, content_type: str) -> None:
    """Upload bytes/string to S3."""
    if isinstance(body, str):
        body = body.encode("utf-8")
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
    )
    print(f"  uploaded: s3://{bucket}/{key} ({len(body)} bytes)")


def generate_corpus(bucket: str, source: str, region: str, seed: int = 42) -> None:
    """Generate and upload the full synthetic corpus."""
    _seed_rng(seed)
    s3 = boto3.client("s3", region_name=region)

    today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    base_prefix = f"ingests/{source}/{today}"

    print(f"==> Generating synthetic corpus in s3://{bucket}/{base_prefix}")

    # 1. CSV (retail products)
    print("Generating products.csv (100 rows)...")
    upload(
        s3,
        bucket,
        f"{base_prefix}/products.csv",
        make_csv(100),
        "text/csv",
    )

    # 2. JSONL (orders)
    print("Generating orders.jsonl (50 records)...")
    upload(
        s3,
        bucket,
        f"{base_prefix}/orders.jsonl",
        make_jsonl(50),
        "application/json",
    )

    # 3. Markdown (returns policy)
    print("Generating returns-policy.md...")
    upload(
        s3,
        bucket,
        f"{base_prefix}/returns-policy.md",
        make_markdown_policy(),
        "text/markdown",
    )

    # 4. HTML (FAQ)
    print("Generating faq.html...")
    upload(
        s3,
        bucket,
        f"{base_prefix}/faq.html",
        make_html_faq(),
        "text/html",
    )

    # 5. PDF (product catalog)
    print("Generating catalog.pdf...")
    upload(
        s3,
        bucket,
        f"{base_prefix}/catalog.pdf",
        make_pdf_bytes_simple("Q3 2026 Product Catalog"),
        "application/pdf",
    )

    # 6. JSON (sample customer profile)
    print("Generating customer-profile.json...")
    upload(
        s3,
        bucket,
        f"{base_prefix}/customer-profile.json",
        json.dumps({
            "customer_id": "CUST-0042",
            "name": "Sample Customer",
            "email": "sample@example.com",
            "phone": "+1-555-123-4567",
            "preferences": {"language": "en", "currency": "INR"},
            "orders": 12,
            "lifetime_value_inr": 84500.0,
        }, indent=2),
        "application/json",
    )

    print()
    print("==> Done. 6 files uploaded.")
    print()
    print("Watch the pipeline run:")
    print("  aws logs tail /aws/vendedlogs/states/datacurator-pipeline-dev --follow --region ap-south-1")
    print()
    print("Open the KB UI:")
    print("  https://<cloudfront-domain-from-terraform-output>")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic data for DataCurator")
    parser.add_argument("--bucket", default="datacurator-raw-dev", help="S3 raw bucket")
    parser.add_argument("--source", default="demo", help="Source name (used in s3 prefix)")
    parser.add_argument("--region", default="ap-south-1", help="AWS region")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    try:
        generate_corpus(args.bucket, args.source, args.region, args.seed)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
