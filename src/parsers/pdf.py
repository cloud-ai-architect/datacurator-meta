"""PDF parser using PyPDF2 (Phase 1) and Docling (Phase 2).

For Phase 1, we use PyPDF2 for simplicity. Phase 2 will switch to Docling
for better table extraction and layout preservation.
"""

from __future__ import annotations

import io
import time

from src.common import (
    BaseLambda,
    DataCuratorModel,
    JobContext,
    ParsedDocument,
    ParseError,
    StructuredElement,
    stage,
)


@stage(name="parse-pdf", input_model=DataCuratorModel, output_model=ParsedDocument)
class PdfParser(BaseLambda):
    """Parse a PDF into text + page-level metadata using PyPDF2."""

    def setup(self) -> None:
        # Lazy import to keep cold start fast
        from PyPDF2 import PdfReader

        self._PdfReader = PdfReader

    def handle(self, ctx: JobContext, inp: DataCuratorModel) -> ParsedDocument:
        start = time.perf_counter()
        bucket = getattr(inp, "source_bucket", None) or ctx.source_bucket
        key = getattr(inp, "source_key", None) or ctx.source_key

        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            body = response["Body"].read()
            reader = self._PdfReader(io.BytesIO(body))

            text_parts: list[str] = []
            elements: list[StructuredElement] = []
            warnings: list[str] = []

            for page_idx, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text() or ""
                except Exception as exc:
                    warnings.append(f"page_{page_idx}_extract_failed: {exc}")
                    page_text = ""

                text_parts.append(page_text)
                elements.append(
                    StructuredElement(
                        element_type="paragraph",
                        text=page_text,
                        page=page_idx + 1,
                        position=page_idx,
                    )
                )

            text_content = "\n\n".join(text_parts)
            parse_duration_ms = int((time.perf_counter() - start) * 1000)

            try:
                import PyPDF2

                parser_version = PyPDF2.__version__
            except Exception:
                parser_version = "unknown"

            return ParsedDocument(
                job_id=ctx.job_id,
                source_bucket=bucket,
                source_key=key,
                detected_format="pdf",
                text_content=text_content,
                structured_elements=elements,
                page_count=len(reader.pages),
                language=None,  # PyPDF2 doesn't detect language
                parse_duration_ms=parse_duration_ms,
                parser_version=parser_version,
                warnings=warnings,
            )
        except Exception as exc:
            raise ParseError(f"Failed to parse PDF s3://{bucket}/{key}: {exc}") from exc
