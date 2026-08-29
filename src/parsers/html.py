"""HTML parser using BeautifulSoup.

Extracts the visible text, headers, links, and tables from HTML.
Skips scripts, styles, and other non-content elements.
"""

from __future__ import annotations

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


@stage(name="parse-html", input_model=DataCuratorModel, output_model=ParsedDocument)
class HtmlParser(BaseLambda):
    """Parse HTML into text + structured elements."""

    def setup(self) -> None:
        from bs4 import BeautifulSoup

        self._BeautifulSoup = BeautifulSoup

    def handle(self, ctx: JobContext, inp: DataCuratorModel) -> ParsedDocument:
        start = time.perf_counter()
        bucket = getattr(inp, "source_bucket", None) or ctx.source_bucket
        key = getattr(inp, "source_key", None) or ctx.source_key

        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            body = response["Body"].read()

            # Try to detect encoding from meta charset
            soup = self._BeautifulSoup(body, "lxml")

            # Remove script and style elements
            for tag in soup(["script", "style", "noscript", "iframe"]):
                tag.decompose()

            # Get title
            title = soup.title.string if soup.title else ""

            # Get meta description
            meta_desc = ""
            meta = soup.find("meta", attrs={"name": "description"})
            if meta and meta.get("content"):
                meta_desc = str(meta["content"])

            # Get all text
            text = soup.get_text(separator="\n", strip=True)

            # Identify headers
            elements: list[StructuredElement] = []
            for header in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
                elements.append(
                    StructuredElement(
                        element_type="header",
                        text=header.get_text(strip=True),
                        metadata={"level": int(header.name[1])},
                        position=len(elements),
                    )
                )

            # Build the final text
            parts: list[str] = []
            if title:
                parts.append(f"# {title}\n")
            if meta_desc:
                parts.append(f"*{meta_desc}*\n")
            parts.append(text)

            text_content = "\n\n".join(parts)
            parse_duration_ms = int((time.perf_counter() - start) * 1000)

            return ParsedDocument(
                job_id=ctx.job_id,
                source_bucket=bucket,
                source_key=key,
                detected_format="html",
                text_content=text_content,
                structured_elements=elements,
                page_count=None,
                language=None,
                parse_duration_ms=parse_duration_ms,
                parser_version="beautifulsoup4",
                warnings=[],
            )
        except Exception as exc:
            raise ParseError(f"Failed to parse HTML s3://{bucket}/{key}: {exc}") from exc
