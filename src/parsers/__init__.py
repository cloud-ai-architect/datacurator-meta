"""Parsers for each supported file format.

Each parser is a `BaseLambda` subclass that converts raw bytes into a
`ParsedDocument` (text + structured elements).

Available parsers:
- pdf: PDF documents via PyPDF2 (Phase 1) and Docling (Phase 2)
- csv: CSV/TSV files via pandas
- json: JSON / JSONL / NDJSON files
- html: HTML via BeautifulSoup
- text: Plain text and Markdown (stdlib only)
- audio: Audio files via Whisper (Phase 2)
- image: Image files via ColPali (Phase 2)
- video: Video files (Phase 2)
"""
