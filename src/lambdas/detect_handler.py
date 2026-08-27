"""Lambda handler for the Detect stage."""

from __future__ import annotations

import json
import os
import time
import uuid

from src.detect import FormatDetector
from src.common import JobContext


def handler(event: dict, context: object) -> dict:
    """Handle a Step Function invocation for format detection.

    Event shape (from EventBridge -> Step Function):
        {
            "source_bucket": "datacurator-raw-dev",
            "source_key": "ingests/retailpulse/2026/08/27/file.pdf",
            "size_bytes": 12345,
            ...
        }
    """
    job_id = event.get("job_id") or str(uuid.uuid4())
    environment = os.environ.get("ENVIRONMENT", "dev")

    ctx = JobContext(
        job_id=job_id,
        source_bucket=event.get("source_bucket", ""),
        source_key=event.get("source_key", ""),
        environment=environment,
    )

    # The event may come from EventBridge (S3 ObjectCreated) or directly
    detect_input = {
        "bucket": event.get("source_bucket"),
        "key": event.get("source_key"),
        "content_type": event.get("content_type", ""),
        "size": event.get("size_bytes", 0),
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
