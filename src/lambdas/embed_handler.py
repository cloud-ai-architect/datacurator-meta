"""Lambda handler for the Embed stage."""

from __future__ import annotations

import os
from typing import Any

from src.common import JobContext, RedactedChunk
from src.embedder import BedrockEmbedder


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    """Handle a Step Function invocation for embedding.

    Event shape (from previous Redact state):
        {
            "chunk_id": "...",
            "text": "...",  # redacted
            "redaction_count": 3,
            ...
        }
    """
    ctx = JobContext(
        job_id=event.get("job_id", ""),
        source_bucket=event.get("source_bucket", ""),
        source_key=event.get("source_key", ""),
        environment=os.environ.get("ENVIRONMENT", "dev"),
    )

    chunk = RedactedChunk.from_dict(event)
    embedder = BedrockEmbedder()
    result = embedder.handle(ctx, chunk)

    return result.to_dict()
