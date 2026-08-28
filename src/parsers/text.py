"""Plain-text and Markdown parser.

Handles `.txt` and `.md` files. Decodes bytes with an encoding fallback
chain, then extracts structure: Markdown ATX/Setext headers become
`header` elements, fenced blocks become `code` elements, and blank-line
separated runs become `paragraph` elements.

No third-party dependency — this parser is stdlib-only, which keeps it
usable in the minimal Lambda layer.
"""

from __future__ import annotations

import codecs
import re
import time

from src.common import (
    DataCuratorModel,
    JobContext,
    ParsedDocument,
    ParseError,
    BaseLambda,
    StructuredElement,
    stage,
)

# UTF-16 is deliberately NOT in this chain: it decodes *any* even-length byte
# string without error, so trying it blind silently mangles cp1252 text into
# CJK garbage. It is only used when a BOM positively identifies it.
_ENCODINGS = ("utf-8", "cp1252", "latin-1")

_BOMS = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)

_ATX_HEADER = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
_SETEXT_UNDERLINE = re.compile(r"^(=+|-+)\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)(.*)$")


def _decode(body: bytes) -> tuple[str, str, list[str]]:
    """Decode bytes to text. Returns (text, encoding_used, warnings).

    A BOM is authoritative when present. Otherwise the chain is tried in
    order, ending at latin-1 which maps every byte and so always succeeds.
    """
    warnings: list[str] = []

    for bom, enc in _BOMS:
        if body.startswith(bom):
            try:
                return body.decode(enc), enc, warnings
            except (UnicodeDecodeError, LookupError):
                warnings.append(f"{enc} BOM present but content failed to decode as {enc}")
                break

    for enc in _ENCODINGS:
        try:
            return body.decode(enc), enc, warnings
        except (UnicodeDecodeError, LookupError):
            continue
    # Last resort: never fail the pipeline on an undecodable byte.
    warnings.append("undecodable bytes replaced; encoding could not be determined")
    return body.decode("utf-8", errors="replace"), "utf-8/replace", warnings


@stage(name="parse-text", input_model=DataCuratorModel, output_model=ParsedDocument)
class TextParser(BaseLambda):
    """Parse plain text and Markdown into text + structured elements."""

    def handle(self, ctx: JobContext, inp: DataCuratorModel) -> ParsedDocument:  # type: ignore[override]
        start = time.perf_counter()
        bucket = getattr(inp, "source_bucket", None) or ctx.source_bucket
        key = getattr(inp, "source_key", None) or ctx.source_key

        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            body = response["Body"].read()
        except Exception as exc:
            raise ParseError(f"Failed to read s3://{bucket}/{key}: {exc}") from exc

        try:
            text, encoding, warnings = _decode(body)
            is_markdown = str(key).lower().endswith((".md", ".markdown"))
            elements = self._extract(text, is_markdown)

            return ParsedDocument(
                job_id=ctx.job_id,
                source_bucket=bucket,
                source_key=key,
                detected_format="text",
                text_content=text,
                structured_elements=elements,
                page_count=None,
                language=None,
                parse_duration_ms=int((time.perf_counter() - start) * 1000),
                parser_version=f"stdlib-text/{encoding}",
                warnings=warnings,
            )
        except Exception as exc:
            raise ParseError(f"Failed to parse text s3://{bucket}/{key}: {exc}") from exc

    def _extract(self, text: str, is_markdown: bool) -> list[StructuredElement]:
        """Split into headers, code blocks, and paragraphs."""
        elements: list[StructuredElement] = []
        lines = text.splitlines()
        buffer: list[str] = []
        in_fence = False
        fence_marker = ""

        def flush_paragraph() -> None:
            if not buffer:
                return
            joined = "\n".join(buffer).strip()
            if joined:
                elements.append(
                    StructuredElement(
                        element_type="paragraph",
                        text=joined,
                        metadata={"lines": len(buffer)},
                        position=len(elements),
                    )
                )
            buffer.clear()

        for i, line in enumerate(lines):
            if is_markdown:
                fence = _FENCE.match(line)
                if fence and (not in_fence or fence.group(1) == fence_marker):
                    if in_fence:
                        elements.append(
                            StructuredElement(
                                element_type="code",
                                text="\n".join(buffer),
                                metadata={"lines": len(buffer)},
                                position=len(elements),
                            )
                        )
                        buffer.clear()
                        in_fence = False
                    else:
                        flush_paragraph()
                        in_fence = True
                        fence_marker = fence.group(1)
                    continue

                if in_fence:
                    buffer.append(line)
                    continue

                atx = _ATX_HEADER.match(line)
                if atx:
                    flush_paragraph()
                    elements.append(
                        StructuredElement(
                            element_type="header",
                            text=atx.group(2).strip(),
                            metadata={"level": len(atx.group(1))},
                            position=len(elements),
                        )
                    )
                    continue

                # Setext: a non-empty line underlined by === or ---
                if (
                    _SETEXT_UNDERLINE.match(line)
                    and i > 0
                    and lines[i - 1].strip()
                    and buffer
                ):
                    title = buffer.pop().strip()
                    flush_paragraph()
                    elements.append(
                        StructuredElement(
                            element_type="header",
                            text=title,
                            metadata={"level": 1 if line.startswith("=") else 2},
                            position=len(elements),
                        )
                    )
                    continue

            if line.strip():
                buffer.append(line)
            else:
                flush_paragraph()

        # Unterminated fence degrades to a paragraph rather than being dropped.
        flush_paragraph()
        return elements
