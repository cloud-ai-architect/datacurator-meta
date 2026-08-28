"""Embedder.

Generates vector embeddings for redacted chunks using Amazon Bedrock Titan
Embed Text v2 (1024-dim, $0.02/1M tokens).

Why Titan v2: cheapest multilingual model in-region. See ADR-0003.
"""

from __future__ import annotations

import json
import time

from src.common import (
    DataCuratorModel,
    EmbeddedChunk,
    EmbeddingError,
    JobContext,
    BaseLambda,
    RedactedChunk,
    stage,
)

EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIM = 1024
BATCH_SIZE = 25  # Titan v2 max batch size


@stage(name="embed", input_model=RedactedChunk, output_model=EmbeddedChunk)
class BedrockEmbedder(BaseLambda):
    """Generate embeddings via Bedrock Titan v2."""

    def setup(self) -> None:
        pass

    def handle(self, ctx: JobContext, inp: RedactedChunk) -> EmbeddedChunk:  # type: ignore[override]
        start = time.perf_counter()

        try:
            vector = self._embed_text(inp.text)
        except Exception as exc:
            raise EmbeddingError(f"Failed to embed chunk {inp.chunk_id}: {exc}") from exc

        duration_ms = int((time.perf_counter() - start) * 1000)

        self.log.info(
            "embedder.complete",
            job_id=ctx.job_id,
            chunk_id=inp.chunk_id,
            embedding_dim=len(vector),
            duration_ms=duration_ms,
        )

        # Carry every field forward from the input rather than listing them.
        # Hand-listed constructions silently dropped any field added to the
        # upstream model -- that is how source_bucket/source_key vanished
        # between Chunk and Route.
        carried = inp.to_dict()
        carried.pop("embedding_model", None)

        return EmbeddedChunk(
            **carried,
            embedding=vector,
            embedding_model=EMBEDDING_MODEL_ID,
            embedding_dim=EMBEDDING_DIM,
            embedding_duration_ms=duration_ms,
        )

    def _embed_text(self, text: str) -> list[float]:
        """Call Bedrock Titan v2 to embed a single text."""
        body = json.dumps(
            {
                "inputText": text,
                "dimensions": EMBEDDING_DIM,
                "normalize": True,
            }
        )

        response = self.bedrock.invoke_model(
            modelId=EMBEDDING_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )

        response_body = json.loads(response["body"].read())
        return response_body["embedding"]
