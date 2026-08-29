"""CSV / TSV parser using stdlib csv (no external deps).

Converts tabular data into a text representation suitable for chunking.
We render the CSV as both:
1. Markdown table (preserves structure)
2. Row-by-row prose (improves recall in semantic search)
"""

from __future__ import annotations

import csv
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

MAX_ROWS = 500
MAX_COL_WIDTH = 80


@stage(name="parse-csv", input_model=DataCuratorModel, output_model=ParsedDocument)
class CsvParser(BaseLambda):
    """Parse CSV/TSV into text + structured elements (stdlib only)."""

    def setup(self) -> None:
        pass

    def handle(self, ctx: JobContext, inp: DataCuratorModel) -> ParsedDocument:
        start = time.perf_counter()
        bucket = getattr(inp, "source_bucket", None) or ctx.source_bucket
        key = getattr(inp, "source_key", None) or ctx.source_key

        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            body = response["Body"].read().decode("utf-8", errors="replace")

            # Auto-detect separator: TSV if .tsv, otherwise CSV
            separator = "\t" if key.lower().endswith(".tsv") else ","
            # Sniff for delimiter if ambiguous (CSV with tabs, etc.)
            if separator == "," and "\t" in body.splitlines()[0] if body.splitlines() else False:
                separator = "\t"

            reader = csv.reader(io.StringIO(body), delimiter=separator)
            rows = list(reader)
            if not rows:
                raise ParseError(f"Empty CSV file: s3://{bucket}/{key}")  # noqa: TRY301

            headers = [h.strip() for h in rows[0]]
            data_rows = rows[1 : MAX_ROWS + 1]
            truncated = len(rows) - 1 > MAX_ROWS

            # Render as markdown table
            md_table_lines = [
                "| " + " | ".join(self._truncate(h) for h in headers) + " |",
                "| " + " | ".join(["---"] * len(headers)) + " |",
            ]
            for row in data_rows:
                # Pad short rows, truncate long rows
                cells = [self._truncate(self._cell(row, i, headers)) for i in range(len(headers))]
                md_table_lines.append("| " + " | ".join(cells) + " |")
            md_table = "\n".join(md_table_lines)

            # Render as row-by-row prose for better recall
            prose_parts: list[str] = []
            for row in data_rows:
                row_text = " | ".join(
                    f"{headers[i] if i < len(headers) else f'col{i + 1}'}: {self._cell(row, i, headers)}"
                    for i in range(len(row))
                    if self._cell(row, i, headers)
                )
                if row_text:
                    prose_parts.append(row_text)

            text_content = (
                f"# CSV Data ({len(data_rows)}{'+' if truncated else ''} of {len(rows) - 1} rows)\n\n"
                f"{md_table}\n\n## Row-by-row\n\n" + "\n".join(prose_parts)
            )

            elements = [
                StructuredElement(
                    element_type="table",
                    text=md_table,
                    metadata={
                        "row_count": len(data_rows),
                        "column_count": len(headers),
                        "columns": headers,
                        "truncated": truncated,
                    },
                    position=0,
                )
            ]

            parse_duration_ms = int((time.perf_counter() - start) * 1000)

            warnings: list[str] = []
            if truncated:
                warnings.append(f"truncated_to_{MAX_ROWS}_rows (full={len(rows) - 1})")

            return ParsedDocument(
                job_id=ctx.job_id,
                source_bucket=bucket,
                source_key=key,
                detected_format="csv",
                text_content=text_content,
                structured_elements=elements,
                page_count=None,
                language=None,
                parse_duration_ms=parse_duration_ms,
                parser_version="stdlib-csv-3.12",
                warnings=warnings,
            )
        except Exception as exc:
            raise ParseError(f"Failed to parse CSV s3://{bucket}/{key}: {exc}") from exc

    def _cell(self, row: list[str], idx: int, headers: list[str]) -> str:
        """Get cell value, padding with empty string if row is short."""
        return row[idx].strip() if idx < len(row) else ""

    def _truncate(self, s: str) -> str:
        """Truncate a string to fit table column width."""
        s = s.replace("|", "\\|").replace("\n", " ")
        return s[:MAX_COL_WIDTH] + "…" if len(s) > MAX_COL_WIDTH else s
