"""Lambda handler for the Detect stage."""

from __future__ import annotations

import os
import uuid

from src.common import JobContext
from src.detect import FormatDetector


def _extract_s3_event(event: dict) -> dict:
    """Extract bucket/key/size from either a transformed event or a raw S3 EventBridge event.

    Supports:
    1. Transformed event: {source_bucket, source_key, size_bytes, job_id}
    2. Raw EventBridge S3 event: {detail.bucket.name, detail.object.key, detail.object.size}
    3. Step Function direct payload: {source_bucket, source_key, size_bytes}
    """
    # Form 1: already transformed
    if "source_bucket" in event and "source_key" in event:
        return {
            "bucket": event["source_bucket"],
            "key": event["source_key"],
            "size": event.get("size_bytes", 0),
        }
    # Form 2: raw EventBridge S3 event
    detail = event.get("detail", {})
    bucket_obj = detail.get("bucket", {})
    object_obj = detail.get("object", {})
    bucket = bucket_obj.get("name") if isinstance(bucket_obj, dict) else None
    key = object_obj.get("key") if isinstance(object_obj, dict) else None
    size = object_obj.get("size", 0) if isinstance(object_obj, dict) else 0
    if bucket and key:
        return {"bucket": bucket, "key": key, "size": size}
    # Fallback: empty
    return {"bucket": "", "key": "", "size": 0}


def handler(event: dict, context: object) -> dict:
    """Handle a Step Function invocation for format detection."""
    job_id = event.get("job_id") or str(uuid.uuid4())
    environment = os.environ.get("ENVIRONMENT", "dev")

    s3 = _extract_s3_event(event)
    bucket = s3["bucket"]
    key = s3["key"]
    size = s3["size"]

    ctx = JobContext(
        job_id=job_id,
        source_bucket=bucket,
        source_key=key,
        environment=environment,
    )

    detect_input = {
        "bucket": bucket,
        "key": key,
        "content_type": event.get("content_type", ""),
        "size": size,
    }

    detector = FormatDetector()
    result = detector.handle(ctx, detect_input)

    return {
        "job_id": result.job_id,
        "source_bucket": result.source_bucket,
        "source_key": result.source_key,
        "detected_format": result.detected_format,
        "detected_encoding": result.detected_encoding,
        "magic_bytes_verified": result.magic_bytes_verified,
        "size_bytes": result.size_bytes,
        "detected_at": result.detected_at,
    }
