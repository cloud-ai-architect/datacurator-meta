"""Lambda handler for the Parse stage.

The handler picks the right parser based on the detected_format from the
previous stage, then invokes it.
"""

from __future__ import annotations

import os
from typing import Any

from src.common import JobContext, ParseError
from src.parsers.csv import CsvParser
from src.parsers.html import HtmlParser
from src.parsers.json import JsonParser
from src.parsers.pdf import PdfParser
from src.parsers.text import TextParser

PARSERS = {
    "pdf": PdfParser,
    "csv": CsvParser,
    "json": JsonParser,
    "html": HtmlParser,
    "text": TextParser,
}


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
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

    detect_result = DetectResult.from_dict(event)
    result = parser.handle(ctx, detect_result)

    # Serialise from the model rather than hand-listing fields: the previous
    # literal dict silently dropped any field added to ParsedDocument, which
    # is how source_bucket/source_key went missing downstream.
    return result.to_dict()
