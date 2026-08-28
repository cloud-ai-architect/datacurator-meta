"""Router.

The final stage of the pipeline. Fans out the classified chunk to its
storage destinations:
- S3 Vectors (the embedding)
- DynamoDB chunk-metadata (the full record)
- DynamoDB jobs (updates the job state)
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from src.common import (
    ClassifiedChunk,
    DataCuratorModel,
    JobContext,
    BaseLambda,
    RoutingError,
    stage,
)


@stage(name="route", input_model=ClassifiedChunk, output_model=DataCuratorModel)
class ChunkRouter(BaseLambda):
    """Route a classified chunk to S3 Vectors + DynamoDB."""

    def setup(self) -> None:
        # Vector bucket + index names are environment variables
        import os

        self.vector_bucket = os.environ.get("VECTOR_BUCKET", "datacurator-vectors-dev")
        self.vector_index = os.environ.get("VECTOR_INDEX", "datacurator-chunks-v1")
        self.metadata_table = os.environ.get("METADATA_TABLE", "datacurator-chunk-metadata-dev")
        self.jobs_table = os.environ.get("JOBS_TABLE", "datacurator-jobs-dev")
        self.environment = os.environ.get("ENVIRONMENT", "dev")

    def handle(self, ctx: JobContext, inp: ClassifiedChunk) -> ClassifiedChunk:  # type: ignore[override]
        start = time.perf_counter()

        try:
            self._put_vector(inp)
            self._put_metadata(inp)
            self._update_job(ctx, inp)
        except Exception as exc:
            raise RoutingError(f"Failed to route chunk {inp.chunk_id}: {exc}") from exc

        self.log.info(
            "router.complete",
            job_id=ctx.job_id,
            chunk_id=inp.chunk_id,
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        return inp

    def _put_vector(self, chunk: ClassifiedChunk) -> None:
        """Store the embedding in S3 Vectors."""
        self.s3vectors.put_vectors(
            vectorBucketName=self.vector_bucket,
            indexName=self.vector_index,
            vectors=[
                {
                    "key": chunk.chunk_id,
                    "data": {"float32": chunk.embedding},
                    "metadata": {
                        "source": chunk.metadata.get("source", "unknown"),
                        "format": chunk.metadata.get("format", "unknown"),
                        "category": chunk.classification.category if chunk.classification else "general",
                    },
                }
            ],
        )

    def _put_metadata(self, chunk: ClassifiedChunk) -> None:
        """Store full metadata in DynamoDB."""
        item: dict[str, Any] = {
            "chunk_id": {"S": chunk.chunk_id},
            "job_id": {"S": chunk.job_id},
            "document_id": {"S": chunk.document_id},
            "chunk_index": {"N": str(chunk.chunk_index)},
            # Provenance now travels on the chunk itself; fall back to the
            # metadata bag for records written by older pipeline versions.
            "text_preview": {"S": chunk.text[:500]},  # truncate for table size limits
            "token_count": {"N": str(chunk.token_count)},
            "redaction_count": {"N": str(chunk.redaction_count)},
            "embedding_model": {"S": chunk.embedding_model},
            "embedding_dim": {"N": str(chunk.embedding_dim)},
            "created_at": {"S": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            "ttl": {"N": str(int(time.time()) + 90 * 24 * 60 * 60)},  # 90 days
        }

        # source_key backs a GSI, and DynamoDB rejects an empty string for any
        # index key. Write these only when populated -- a sparse index is the
        # intended behaviour for chunks whose origin is unknown.
        source_bucket = chunk.source_bucket or chunk.metadata.get("source_bucket", "")
        source_key = chunk.source_key or chunk.metadata.get("source_key", "")
        if source_bucket:
            item["source_bucket"] = {"S": source_bucket}
        if source_key:
            item["source_key"] = {"S": source_key}
        if chunk.classification:
            item["classification_category"] = {"S": chunk.classification.category}
            if chunk.classification.tags:
                item["classification_tags"] = {"SS": chunk.classification.tags}
            item["classification_confidence"] = {"N": str(chunk.classification.confidence)}

        self.dynamodb.put_item(TableName=self.metadata_table, Item=item)

    def _update_job(self, ctx: JobContext, chunk: ClassifiedChunk) -> None:
        """Increment the job's chunks_created counter."""
        try:
            self.dynamodb.update_item(
                TableName=self.jobs_table,
                Key={"job_id": {"S": ctx.job_id}},
                UpdateExpression="ADD chunks_created :one, total_tokens :tokens SET #s = :status",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":one": {"N": "1"},
                    ":tokens": {"N": str(chunk.token_count)},
                    ":status": {"S": "running"},
                },
            )
        except Exception as exc:
            # Job update is best-effort; don't fail the chunk
            self.log.warning("router.job_update_failed", job_id=ctx.job_id, error=str(exc))
