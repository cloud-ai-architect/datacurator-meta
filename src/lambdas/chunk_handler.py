"""Lambda handler for the Chunk stage."""

from __future__ import annotations

import os

from src.chunker import SemanticChunker
from src.common import JobContext, ParsedDocument


def handler(event: dict, context: object) -> dict:
    """Handle a Step Function invocation for chunking.

    Event shape (from previous Parse state):
        {
            "job_id": "...",
            "detected_format": "pdf",
            "text_content": "...",
            "structured_elements": [...],
            ...
        }

    Returns a list of chunks (Step Function will pass each to Redact via Map).
    """
    ctx = JobContext(
        job_id=event.get("job_id", ""),
        source_bucket=event.get("source_bucket", ""),
        source_key=event.get("source_key", ""),
        environment=os.environ.get("ENVIRONMENT", "dev"),
    )

    parsed = ParsedDocument(**event)
    chunker = SemanticChunker()
    chunks = chunker.handle(ctx, parsed)

    return {
        "job_id": ctx.job_id,
        "chunk_count": len(chunks),
        "chunks": [c.to_dict() for c in chunks],
    }

