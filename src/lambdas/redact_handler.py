"""Lambda handler for the Redact stage."""

from __future__ import annotations

import os

from src.common import JobContext, RedactedChunk
from src.redactor import PiiRedactor


def handler(event: dict, context: object) -> dict:
    """Handle a Step Function invocation for PII redaction.

    Event shape (single chunk from Map state):
        {
            "chunk_id": "...",
            "job_id": "...",
            "document_id": "...",
            "text": "...",
            ...
        }
    """
    ctx = JobContext(
        job_id=event.get("job_id", ""),
        source_bucket="",
        source_key="",
        environment=os.environ.get("ENVIRONMENT", "dev"),
    )

    chunk = RedactedChunk(**event) if "redaction_count" in event else _dict_to_chunk(event)
    redactor = PiiRedactor()
    result = redactor.handle(ctx, chunk)

    return result.model_dump()


def _dict_to_chunk(d: dict) -> RedactedChunk:
    """Convert dict to RedactedChunk (filling redaction fields with defaults)."""
    from src.common import Chunk

    base = Chunk(**d)
    return RedactedChunk(
        **base.model_dump(),
        redaction_count=0,
        redaction_types=[],
        redaction_policy_version="",
        original_text_hash="",
    )
