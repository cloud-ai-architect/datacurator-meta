"""PII redactor.

Applies OPA Rego policies to redact PII from chunk text before embedding.
The policies are bundled into the Lambda deployment package so there's no
runtime S3 fetch.

Policies:
- pii-redaction.rego: defines PII patterns (email, phone, Aadhaar, credit card, SSN)
- retention.rego: data retention rules (Phase 3)

Why OPA? See ADR-0008 — policies as data, version-controlled, testable.
"""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import ClassVar

from src.common import (
    Chunk,
    DataCuratorModel,
    JobContext,
    BaseLambda,
    RedactedChunk,
    RedactionError,
    stage,
)

POLICY_VERSION = "pii-redaction-1.0.0"

# Fallback regex patterns in case OPA isn't available or fails.
# These are deliberately conservative (high precision, lower recall).
FALLBACK_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone_intl": re.compile(r"\+\d{1,3}[\s-]?\d{3,5}[\s-]?\d{3,5}[\s-]?\d{3,5}"),
    "phone_in": re.compile(r"\b\d{10}\b"),
    "aadhaar": re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    "ipv4": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
}


@stage(name="redact", input_model=Chunk, output_model=RedactedChunk)
class PiiRedactor(BaseLambda):
    """Apply PII redaction to a chunk.

    For Phase 1, uses compiled regex patterns directly. Phase 2 will
    integrate OPA in-process via the opa-python library.
    """

    # Override because we accept a list of chunks
    INPUT_MODEL: ClassVar[type[DataCuratorModel] | None] = Chunk
    OUTPUT_MODEL: ClassVar[type[DataCuratorModel] | None] = RedactedChunk

    def setup(self) -> None:
        self._patterns = FALLBACK_PATTERNS
        self._policy_path = Path(__file__).parent.parent / "policies" / "pii-redaction.rego"
        # Phase 2: load OPA bundle here

    def handle(self, ctx: JobContext, inp: Chunk) -> RedactedChunk:  # type: ignore[override]
        start = time.perf_counter()
        text = inp.text
        redaction_count = 0
        redaction_types: list[str] = []
        redacted_text = text

        for pii_type, pattern in self._patterns.items():
            matches = pattern.findall(redacted_text)
            if matches:
                redaction_count += len(matches)
                redaction_types.append(pii_type)
                # Replace with a token indicating the type
                redacted_text = pattern.sub(f"[REDACTED:{pii_type}]", redacted_text)

        original_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        self.log.info(
            "redactor.complete",
            job_id=ctx.job_id,
            chunk_id=inp.chunk_id,
            redaction_count=redaction_count,
            redaction_types=redaction_types,
            duration_ms=int((time.perf_counter() - start) * 1000),
        )

        # Carry every field forward from the input rather than listing them.
        # Hand-listed constructions silently dropped any field added to the
        # upstream model -- that is how source_bucket/source_key vanished
        # between Chunk and Route.
        carried = inp.to_dict()
        carried["text"] = redacted_text
        # inp may already be a RedactedChunk (the handler defaults the
        # redaction fields on first pass), so drop what we are about to set.
        for k in (
            "redaction_count",
            "redaction_types",
            "redaction_policy_version",
            "original_text_hash",
        ):
            carried.pop(k, None)

        return RedactedChunk(
            **carried,
            redaction_count=redaction_count,
            redaction_types=list(set(redaction_types)),
            redaction_policy_version=POLICY_VERSION,
            original_text_hash=original_hash,
        )
