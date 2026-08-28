"""Provenance must survive every pipeline stage.

Each stage used to hand-list the fields it copied forward, so any field
added to an upstream model was silently dropped. That is how source_bucket
and source_key vanished between Chunk and Route, leaving DynamoDB to reject
the empty GSI key. These tests fail if a stage stops carrying fields.
"""

from __future__ import annotations

import pytest

from src.common import (
    Chunk,
    EmbeddedChunk,
    JobContext,
    RedactedChunk,
)
from src.classifier import RuleBasedClassifier
from src.redactor import PiiRedactor


BUCKET = "datacurator-dev-raw"
KEY = "inbox/report.md"


@pytest.fixture
def ctx():
    return JobContext(
        job_id="j1", source_bucket=BUCKET, source_key=KEY, environment="dev"
    )


@pytest.fixture
def chunk():
    return Chunk(
        job_id="j1",
        document_id="d1",
        source_bucket=BUCKET,
        source_key=KEY,
        text="Patient presented with chest pain.",
        token_count=6,
    )


def _as_redacted(c: Chunk) -> RedactedChunk:
    """Mirror what redact_handler does on the first pass."""
    return RedactedChunk(
        **c.to_dict(),
        redaction_count=0,
        redaction_types=[],
        redaction_policy_version="",
        original_text_hash="",
    )


class TestProvenanceSurvivesStages:
    def test_chunk_model_carries_provenance(self, chunk):
        assert chunk.source_bucket == BUCKET
        assert chunk.source_key == KEY

    def test_redact_carries_provenance(self, ctx, chunk):
        out = PiiRedactor().handle(ctx, _as_redacted(chunk))
        assert out.source_bucket == BUCKET
        assert out.source_key == KEY

    def test_redact_does_not_duplicate_its_own_fields(self, ctx, chunk):
        """Regression: to_dict() already held the redaction fields, so
        re-passing them raised "got multiple values for keyword argument"."""
        out = PiiRedactor().handle(ctx, _as_redacted(chunk))
        assert isinstance(out, RedactedChunk)

    def test_classify_carries_provenance(self, ctx, chunk):
        embedded = EmbeddedChunk(
            **_as_redacted(chunk).to_dict(),
            embedding=[0.0] * 8,
            embedding_dim=8,
            embedding_duration_ms=1,
        )
        out = RuleBasedClassifier().handle(ctx, embedded)
        assert out.source_bucket == BUCKET
        assert out.source_key == KEY

    def test_redact_preserves_unrelated_fields(self, ctx, chunk):
        out = PiiRedactor().handle(ctx, _as_redacted(chunk))
        assert out.document_id == "d1"
        assert out.token_count == 6
        assert out.job_id == "j1"
