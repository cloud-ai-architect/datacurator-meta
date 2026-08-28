"""Lambda handler for the Classify stage."""

from __future__ import annotations

import os

from src.classifier import RuleBasedClassifier
from src.common import EmbeddedChunk, JobContext


def handler(event: dict, context: object) -> dict:
    """Handle a Step Function invocation for classification.

    Event shape (from previous Embed state):
        {
            "chunk_id": "...",
            "text": "...",
            "embedding": [...],
            ...
        }
    """
    ctx = JobContext(
        job_id=event.get("job_id", ""),
        source_bucket=event.get("source_bucket", ""),
        source_key=event.get("source_key", ""),
        environment=os.environ.get("ENVIRONMENT", "dev"),
    )

    chunk = EmbeddedChunk.from_dict(event)
    classifier = RuleBasedClassifier()
    result = classifier.handle(ctx, chunk)

    return result.to_dict()

