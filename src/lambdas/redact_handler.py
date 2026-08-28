"""Lambda handler for the Redact stage.

The Step Function Map state wraps each chunk in {"chunk": {...}}.
"""

from __future__ import annotations

import os

from src.common import JobContext, RedactedChunk
from src.redactor import PiiRedactor


def handler(event: dict, context: object) -> dict:
    """Handle a Step Function Map iteration for PII redaction."""
    ctx = JobContext(
        job_id=event.get("job_id", ""),
        source_bucket=event.get("source_bucket", ""),
        source_key=event.get("source_key", ""),
        environment=os.environ.get("ENVIRONMENT", "dev"),
    )

    # The Map state wraps each item in {"chunk": {...}}
    # We accept both the wrapped form and the bare chunk dict.
    if "chunk" in event and isinstance(event["chunk"], dict):
        chunk_data = event["chunk"]
    else:
        chunk_data = event

    # The chunk may come in with missing redaction fields (first time through).
    # Build a RedactedChunk, defaulting the redaction fields.
    if "redaction_count" not in chunk_data:
        from src.common import Chunk
        base = Chunk.from_dict({k: v for k, v in chunk_data.items() if k != "chunk"})
        chunk = RedactedChunk(
            **base.to_dict(),
            redaction_count=0,
            redaction_types=[],
            redaction_policy_version="",
            original_text_hash="",
        )
    else:
        chunk = RedactedChunk.from_dict(chunk_data)

    redactor = PiiRedactor()
    result = redactor.handle(ctx, chunk)
    return result.to_dict()
