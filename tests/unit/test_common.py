"""Unit tests for common models and base classes."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.common import (
    Chunk,
    ClassifiedChunk,
    Classification,
    DataCuratorModel,
    DetectResult,
    EmbeddedChunk,
    JobContext,
    ParsedDocument,
    RedactedChunk,
    StructuredElement,
)


class TestDetectResult:
    def test_valid(self):
        r = DetectResult(
            job_id="job-1",
            source_bucket="bucket",
            source_key="key",
            detected_format="pdf",
            detected_encoding="utf-8",
            magic_bytes_verified=True,
            detected_at="2026-08-27T00:00:00Z",
            size_bytes=1024,
        )
        assert r.detected_format == "pdf"
        assert r.size_bytes == 1024

    def test_invalid_format(self):
        with pytest.raises(ValidationError):
            DetectResult(
                job_id="job-1",
                source_bucket="bucket",
                source_key="key",
                detected_format="unknown_format",  # not in Literal
                detected_encoding="utf-8",
                magic_bytes_verified=True,
                detected_at="2026-08-27T00:00:00Z",
                size_bytes=1024,
            )


class TestParsedDocument:
    def test_basic(self):
        doc = ParsedDocument(
            job_id="job-1",
            detected_format="pdf",
            text_content="Hello world",
            structured_elements=[],
            page_count=1,
            language="en",
            parse_duration_ms=100,
            parser_version="test-1.0",
        )
        assert doc.text_content == "Hello world"
        assert doc.page_count == 1


class TestChunk:
    def test_default_chunk_id(self):
        c = Chunk(
            job_id="job-1",
            document_id="doc-1",
            chunk_index=0,
            text="test",
            token_count=1,
            chunk_strategy="semantic-v1",
        )
        assert c.chunk_id  # auto-generated UUID
        assert len(c.chunk_id) > 0


class TestClassification:
    def test_valid_confidence(self):
        c = Classification(
            category="general",
            tags=[],
            confidence=0.5,
            classifier_version="v1",
            model_used="rule-based",
        )
        assert c.confidence == 0.5

    def test_invalid_confidence(self):
        with pytest.raises(ValidationError):
            Classification(
                category="general",
                tags=[],
                confidence=1.5,  # > 1.0
                classifier_version="v1",
                model_used="rule-based",
            )


class TestJobContext:
    def test_default_started_at(self):
        ctx = JobContext(
            job_id="job-1",
            source_bucket="b",
            source_key="k",
            environment="dev",
        )
        assert ctx.started_at > 0
        assert ctx.cumulative_cost_usd == 0.0
