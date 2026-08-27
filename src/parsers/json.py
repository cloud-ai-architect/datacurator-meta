"""JSON / JSONL / NDJSON parser.

Handles three forms:
1. Single JSON object: `{"key": "value"}`
2. JSON array: `[{"key": "value"}, ...]`
3. Newline-delimited JSON: `{"key": "value"}\n{"key": "value"}\n...`

Renders as YAML-like text (better than JSON for semantic search).
"""

from __future__ import annotations

import io
import json
import time

import yaml

from src.common import (
    DataCuratorModel,
    JobContext,
    ParsedDocument,
    ParseError,
    BaseLambda,
    StructuredElement,
    stage,
)


@stage(name="parse-json", input_model=DataCuratorModel, output_model=ParsedDocument)
class JsonParser(BaseLambda):
    """Parse JSON/JSONL/NDJSON into text + structured elements."""

    def setup(self) -> None:
        pass

    def handle(self, ctx: JobContext, inp: DataCuratorModel) -> ParsedDocument:  # type: ignore[override]
        start = time.perf_counter()
        bucket = getattr(inp, "source_bucket", None) or ctx.source_bucket
        key = getattr(inp, "source_key", None) or ctx.source_key

        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            body = response["Body"].read().decode("utf-8")

            records: list[dict] = []
            warnings: list[str] = []

            # Try JSONL first
            try:
                for line in body.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    records.append(json.loads(line))
            except json.JSONDecodeError:
                # Not JSONL; try single JSON
                records = []
                try:
                    obj = json.loads(body)
                    if isinstance(obj, list):
                        records = obj
                    elif isinstance(obj, dict):
                        records = [obj]
                    else:
                        warnings.append("top_level_not_object_or_array")
                except json.JSONDecodeError as exc:
                    raise ParseError(f"Invalid JSON: {exc}") from exc

            # Render as YAML (more readable than JSON)
            text_parts: list[str] = []
            for i, rec in enumerate(records[:500]):
                try:
                    text_parts.append(f"--- Record {i + 1} ---\n{yaml.safe_dump(rec, sort_keys=False, allow_unicode=True)}")
                except yaml.YAMLError as exc:
                    warnings.append(f"record_{i}_yaml_dump_failed: {exc}")

            text_content = "\n\n".join(text_parts)

            elements = [
                StructuredElement(
                    element_type="table",
                    text=text_content,
                    metadata={"record_count": len(records)},
                    position=0,
                )
            ]

            parse_duration_ms = int((time.perf_counter() - start) * 1000)
            if len(records) > 500:
                warnings.append(f"truncated_to_500_records (full={len(records)})")

            return ParsedDocument(
                job_id=ctx.job_id,
                detected_format="json",
                text_content=text_content,
                structured_elements=elements,
                page_count=None,
                language=None,
                parse_duration_ms=parse_duration_ms,
                parser_version="stdlib-json-3.12",
                warnings=warnings,
            )
        except Exception as exc:
            raise ParseError(f"Failed to parse JSON s3://{bucket}/{key}: {exc}") from exc
