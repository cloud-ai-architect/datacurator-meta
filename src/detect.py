"""Format detection stage.

Detects the file format from:
1. Content-Type metadata (S3 object metadata)
2. File extension
3. Magic bytes (first 8 bytes of the file)

Returns a DetectResult that downstream stages use to pick the right parser.
"""

from __future__ import annotations

import time
from typing import ClassVar

from src.common import (
    DataCuratorModel,
    DetectResult,
    FormatDetectionError,
    JobContext,
    BaseLambda,
    stage,
)

# Magic byte signatures for common formats.
# Reference: https://en.wikipedia.org/wiki/List_of_file_signatures
MAGIC_SIGNATURES: dict[bytes, str] = {
    b"%PDF": "pdf",
    b"PK\x03\x04": "zip",  # also docx, xlsx, etc.
    b"\x89PNG\r\n\x1a\n": "image",
    b"\xff\xd8\xff": "image",  # JPEG
    b"GIF87a": "image",
    b"GIF89a": "image",
    b"RIFF": "video",  # also WebP
    b"\x1a\x45\xdf\xa3": "video",  # Matroska / WebM
    b"ID3": "audio",  # MP3 with ID3 tag
    b"\xff\xfb": "audio",  # MP3
    b"OggS": "audio",  # OGG
    b"fLaC": "audio",  # FLAC
    b"\x7fELF": "unknown",  # ELF binary
}

EXTENSION_MAP: dict[str, str] = {
    ".pdf": "pdf",
    ".csv": "csv",
    ".tsv": "csv",
    ".json": "json",
    ".jsonl": "json",
    ".ndjson": "json",
    ".html": "html",
    ".htm": "html",
    ".xhtml": "html",
    ".mp3": "audio",
    ".wav": "audio",
    ".flac": "audio",
    ".ogg": "audio",
    ".m4a": "audio",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".svg": "image",
    ".mp4": "video",
    ".mov": "video",
    ".avi": "video",
    ".mkv": "video",
    ".webm": "video",
    ".txt": "text",
    ".md": "text",
    ".markdown": "text",
    ".docx": "pdf",  # we'll convert via docling
    ".xlsx": "csv",  # we'll convert to CSV
}


@stage(name="detect", output_model=DetectResult)
class FormatDetector(BaseLambda):
    """Detect the format of a file using content-type, extension, and magic bytes."""

    # Override INPUT_MODEL: this stage takes raw S3 info
    INPUT_MODEL: ClassVar[type[DataCuratorModel] | None] = None

    def setup(self) -> None:
        # No special setup needed
        pass

    def handle(self, ctx: JobContext, inp: dict) -> DetectResult:  # type: ignore[override]
        """Detect format from S3 object metadata.

        `inp` is expected to be a dict with: bucket, key, content_type, size
        """
        bucket = inp.get("bucket") or ctx.source_bucket
        key = inp.get("key") or ctx.source_key
        content_type = inp.get("content_type", "")
        size = inp.get("size", 0)

        # Strategy 1: extension
        ext_format = self._detect_from_extension(key)

        # Strategy 2: content-type
        ct_format = self._detect_from_content_type(content_type)

        # Strategy 3: magic bytes
        magic_format, verified = self._detect_from_magic_bytes(bucket, key)

        # Pick the most specific match
        detected = self._reconcile(ext_format, ct_format, magic_format, bucket, key)

        return DetectResult(
            job_id=ctx.job_id,
            source_bucket=bucket,
            source_key=key,
            detected_format=detected,
            detected_encoding="utf-8",
            magic_bytes_verified=verified,
            detected_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            size_bytes=size,
        )

    def _detect_from_extension(self, key: str) -> str:
        """Return format based on file extension, or 'unknown'."""
        lower = key.lower()
        for ext, fmt in EXTENSION_MAP.items():
            if lower.endswith(ext):
                return fmt
        return "unknown"

    def _detect_from_content_type(self, content_type: str) -> str:
        """Return format based on S3 Content-Type metadata."""
        if not content_type:
            return "unknown"
        ct = content_type.lower().split(";")[0].strip()
        mapping = {
            "application/pdf": "pdf",
            "text/csv": "csv",
            "application/json": "json",
            "text/html": "html",
            "application/xhtml+xml": "html",
            "audio/mpeg": "audio",
            "audio/wav": "audio",
            "image/png": "image",
            "image/jpeg": "image",
            "image/gif": "image",
            "image/webp": "image",
            "video/mp4": "video",
            "text/plain": "text",
            "text/markdown": "text",
        }
        return mapping.get(ct, "unknown")

    def _detect_from_magic_bytes(self, bucket: str, key: str) -> tuple[str, bool]:
        """Read first 16 bytes and check against known signatures."""
        try:
            response = self.s3.get_object(Bucket=bucket, Key=key, Range="bytes=0-15")
            head = response["Body"].read(16)
        except Exception as exc:
            self.log.warning("magic_bytes.read_failed", error=str(exc))
            return "unknown", False

        for sig, fmt in MAGIC_SIGNATURES.items():
            if head.startswith(sig):
                return fmt, True
        return "unknown", False

    def _reconcile(
        self,
        ext_fmt: str,
        ct_fmt: str,
        magic_fmt: str,
        bucket: str,
        key: str,
    ) -> str:
        """Reconcile conflicting format signals.

        Priority: magic bytes > content-type > extension.
        Magic bytes are the ground truth; if they say it's a PDF, it's a PDF.
        """
        if magic_fmt != "unknown":
            return magic_fmt
        if ct_fmt != "unknown":
            return ct_fmt
        if ext_fmt != "unknown":
            return ext_fmt
        raise FormatDetectionError(
            f"Could not detect format for s3://{bucket}/{key} "
            f"(ext={ext_fmt}, content_type={ct_fmt}, magic={magic_fmt})"
        )
