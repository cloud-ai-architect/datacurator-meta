"""CSV / TSV parser using pandas.

Converts tabular data into a text representation suitable for chunking.
We render the CSV as both:
1. Markdown table (preserves structure)
2. Row-by-row prose (improves recall in semantic search)
"""

from __future__ import annotations

import io
import time

import pandas as pd

from src.common import (
    DataCuratorModel,
    JobContext,
    ParsedDocument,
    ParseError,
    BaseLambda,
    StructuredElement,
    stage,
)


@stage(name="parse-csv", input_model=DataCuratorModel, output_model=ParsedDocument)
class CsvParser(BaseLambda):
    """Parse CSV/TSV into text + structured elements."""

    def setup(self) -> None:
        # pandas imported lazily
        pass

    def handle(self, ctx: JobContext, inp: DataCuratorModel) -> ParsedDocument:  # type: ignore[override]
        start = time.perf_counter()
        bucket = getattr(inp, "source_bucket", None) or ctx.source_bucket
        key = getattr(inp, "source_key", None) or ctx.source_key

        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            body = response["Body"].read()

            # Auto-detect separator
            separator = "\t" if key.lower().endswith(".tsv") else ","

            df = pd.read_csv(io.BytesIO(body), sep=separator, dtype=str, keep_default_na=False)

            # Render as markdown table (truncate for huge files)
            md_table = df.head(500).to_markdown(index=False)

            # Render as row-by-row prose for better recall
            prose_parts: list[str] = []
            for _, row in df.head(500).iterrows():
                row_text = " | ".join(f"{col}: {val}" for col, val in row.items() if val)
                if row_text:
                    prose_parts.append(row_text)

            text_content = f"# CSV Data\n\n{md_table}\n\n## Row-by-row\n\n" + "\n".join(prose_parts)

            elements = [
                StructuredElement(
                    element_type="table",
                    text=md_table,
                    metadata={"row_count": len(df), "column_count": len(df.columns), "columns": list(df.columns)},
                    position=0,
                )
            ]

            parse_duration_ms = int((time.perf_counter() - start) * 1000)

            warnings: list[str] = []
            if len(df) > 500:
                warnings.append(f"truncated_to_500_rows (full={len(df)})")

            return ParsedDocument(
                job_id=ctx.job_id,
                detected_format="csv",
                text_content=text_content,
                structured_elements=elements,
                page_count=None,
                language=None,
                parse_duration_ms=parse_duration_ms,
                parser_version=f"pandas-{pd.__version__}",
                warnings=warnings,
            )
        except Exception as exc:
            raise ParseError(f"Failed to parse CSV s3://{bucket}/{key}: {exc}") from exc
