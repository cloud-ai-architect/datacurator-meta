"""Lambda handler for the Parse stage.

The handler picks the right parser based on the detected_format from the
previous stage, then invokes it.
"""

from __future__ import annotations

import os

from src.common import JobContext, ParseError
from src.parsers.pdf import PdfParser
from src.parsers.csv import CsvParser
from src.parsers.json import JsonParser
from src.parsers.html import HtmlParser

PARSERS = {
    "pdf": PdfParser,
    "csv": CsvParser,
    "json": JsonParser,
    "html": HtmlParser,
}


def handler(event: dict, context: object) -> dict:
    """Handle a Step Function invocation for parsing.

    Event shape (from previous Detect state):
        {
            "job_id": "...",
            "source_bucket": "...",
            "source_key": "...",
            "detected_format": "pdf",
            ...
        }
    """
    detected_format = event.get("detected_format", "unknown")
    if detected_format not in PARSERS:
        raise ParseError(f"No parser for format: {detected_format}")

    ctx = JobContext(
        job_id=event.get("job_id", ""),
        source_bucket=event.get("source_bucket", ""),
        source_key=event.get("source_key", ""),
        environment=os.environ.get("ENVIRONMENT", "dev"),
    )

    parser_class = PARSERS[detected_format]
    parser = parser_class()

    # Convert dict to Pydantic model
    from src.common import DetectResult

    detect_result = DetectResult(**event)
    result = parser.handle(ctx, detect_result)

    return {
        "job_id": result.job_id,
        "detected_format": result.detected_format,
        "text_content": result.text_content,
        "page_count": result.page_count,
        "structured_elements": [e.model_dump() for e in result.structured_elements],
        "parse_duration_ms": result.parse_duration_ms,
        "parser_version": result.parser_version,
        "warnings": result.warnings,
    }
