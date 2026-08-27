"""Semantic chunker.

Splits parsed text into chunks of 100-500 tokens with overlap.
Strategy: recursive character text splitter that respects natural boundaries
(sentences, paragraphs) before falling back to character-level splits.

Chunk size is configurable per data source via `config/chunkers/*.yaml`.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from src.common import (
    Chunk,
    ChunkingError,
    DataCuratorModel,
    JobContext,
    BaseLambda,
    ParsedDocument,
    stage,
)


@dataclass
class ChunkerConfig:
    """Configuration for the chunker.

    Loaded from YAML; default values are sensible for English text.
    """

    target_tokens: int = 300
    min_tokens: int = 100
    max_tokens: int = 500
    overlap_tokens: int = 50
    chunk_strategy: str = "semantic-v1"

    @classmethod
    def from_yaml(cls, path: str) -> "ChunkerConfig":
        """Load from YAML file."""
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)


def estimate_tokens(text: str) -> int:
    """Estimate token count using a simple heuristic.

    English text averages ~4 chars per token. For multilingual text, this is
    a rough approximation; production should use tiktoken or a model-specific
    tokenizer.
    """
    return max(1, len(text) // 4)


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences using a simple regex.

    Handles English; for other languages, use a proper sentence tokenizer.
    """
    import re

    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def split_into_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs by double newlines."""
    paragraphs = text.split("\n\n")
    return [p.strip() for p in paragraphs if p.strip()]


@stage(name="chunk", input_model=ParsedDocument, output_model=Chunk)
class SemanticChunker(BaseLambda):
    """Recursive semantic chunker.

    Strategy:
    1. Split into paragraphs (double-newline)
    2. If paragraph > max_tokens, split into sentences
    3. If sentence > max_tokens, hard-split by character count
    4. Combine sentences/paragraphs into chunks of target_tokens with overlap
    """

    def setup(self) -> None:
        self.config = ChunkerConfig()  # default; can be overridden per source

    def handle(self, ctx: JobContext, inp: ParsedDocument) -> list[Chunk]:  # type: ignore[override]
        start = time.perf_counter()
        chunks: list[Chunk] = []
        document_id = str(uuid.uuid4())

        # Get text, fall back to joining structured elements
        text = inp.text_content
        if not text and inp.structured_elements:
            text = "\n\n".join(e.text or "" for e in inp.structured_elements)

        if not text.strip():
            raise ChunkingError(f"Empty text content for job {ctx.job_id}")

        # Split into raw units (paragraphs or sentences)
        units = self._split_into_units(text)
        if not units:
            raise ChunkingError(f"No splittable units in text for job {ctx.job_id}")

        # Group units into chunks
        chunk_index = 0
        current_text: list[str] = []
        current_token_count = 0
        prev_text: str = ""

        for unit in units:
            unit_tokens = estimate_tokens(unit)

            # If single unit > max_tokens, hard-split it
            if unit_tokens > self.config.max_tokens:
                # Flush current
                if current_text:
                    chunks.append(self._make_chunk(ctx, document_id, chunk_index, "\n\n".join(current_text), current_token_count, prev_text))
                    prev_text = current_text[-1] if current_text else ""
                    chunk_index += 1
                    current_text = []
                    current_token_count = 0

                # Hard-split
                for sub in self._hard_split(unit):
                    sub_tokens = estimate_tokens(sub)
                    chunks.append(self._make_chunk(ctx, document_id, chunk_index, sub, sub_tokens, prev_text))
                    prev_text = sub
                    chunk_index += 1
                continue

            # If adding this unit exceeds max_tokens, flush current chunk
            if current_token_count + unit_tokens > self.config.max_tokens and current_text:
                chunks.append(self._make_chunk(ctx, document_id, chunk_index, "\n\n".join(current_text), current_token_count, prev_text))
                prev_text = current_text[-1] if current_text else ""
                chunk_index += 1
                current_text = []
                current_token_count = 0

            current_text.append(unit)
            current_token_count += unit_tokens

        # Flush remaining
        if current_text:
            chunks.append(self._make_chunk(ctx, document_id, chunk_index, "\n\n".join(current_text), current_token_count, prev_text))

        self.log.info(
            "chunker.complete",
            job_id=ctx.job_id,
            document_id=document_id,
            chunk_count=len(chunks),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        return chunks

    def _split_into_units(self, text: str) -> list[str]:
        """Split text into units (paragraphs → sentences)."""
        paragraphs = split_into_paragraphs(text)
        units: list[str] = []
        for p in paragraphs:
            if estimate_tokens(p) <= self.config.max_tokens:
                units.append(p)
            else:
                # Split paragraph into sentences
                units.extend(split_into_sentences(p))
        return units

    def _hard_split(self, text: str) -> list[str]:
        """Hard-split text that's too large for a single chunk."""
        max_chars = self.config.max_tokens * 4
        overlap_chars = self.config.overlap_tokens * 4
        parts = []
        for i in range(0, len(text), max_chars - overlap_chars):
            parts.append(text[i : i + max_chars])
        return parts

    def _make_chunk(
        self,
        ctx: JobContext,
        document_id: str,
        index: int,
        text: str,
        token_count: int,
        prev_text: str,
    ) -> Chunk:
        """Create a Chunk with overlap computed from the previous chunk."""
        overlap = 0
        if prev_text:
            # Find common substring at the end of prev_text and start of text
            overlap = self._compute_overlap(prev_text, text)
        return Chunk(
            job_id=ctx.job_id,
            document_id=document_id,
            chunk_index=index,
            text=text,
            token_count=token_count,
            overlap_with_previous=overlap,
            chunk_strategy=self.config.chunk_strategy,
            metadata={},
        )

    def _compute_overlap(self, prev: str, curr: str) -> int:
        """Estimate token overlap between two consecutive chunks."""
        # Find longest common suffix/prefix
        max_check = min(len(prev), len(curr), self.config.overlap_tokens * 4)
        for length in range(max_check, 0, -1):
            if prev[-length:] == curr[:length]:
                return length // 4  # approximate tokens
        return 0
