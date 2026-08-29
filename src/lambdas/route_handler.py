"""Lambda handler for the Route stage."""

from __future__ import annotations

import os
from typing import Any

from src.common import ClassifiedChunk, JobContext
from src.router import ChunkRouter


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    """Handle a Step Function invocation for routing to storage.

    Event shape (from previous Classify state):
        {
            "chunk_id": "...",
            "text": "...",
            "embedding": [...],
            "classification": {...},
            ...
        }
    """
    ctx = JobContext(
        job_id=event.get("job_id", ""),
        source_bucket=event.get("source_bucket", ""),
        source_key=event.get("source_key", ""),
        environment=os.environ.get("ENVIRONMENT", "dev"),
    )

    chunk = ClassifiedChunk.from_dict(event)
    router = ChunkRouter()
    result = router.handle(ctx, chunk)

    return {
        "chunk_id": result.chunk_id,
        "job_id": result.job_id,
        "status": "routed",
    }
