"""Lambda handler for the API Gateway /search endpoint."""

from __future__ import annotations

import json
import os
import time

import boto3


def handler(event: dict, context: object) -> dict:
    """Handle a search request.

    Event shape (API Gateway HTTP API v2):
        {
            "queryStringParameters": {"q": "...", "top_k": "10"},
            "rawPath": "/search",
            "requestContext": {"http": {"method": "GET"}}
        }
    """
    params = event.get("queryStringParameters") or {}
    query = params.get("q", "").strip()
    top_k = int(params.get("top_k", "10"))
    source_filter = params.get("source")
    format_filter = params.get("format")
    min_score = float(params.get("min_score", "0.0"))

    if not query:
        return _error(400, "INVALID_QUERY", "q is required")

    if not (1 <= top_k <= 100):
        return _error(400, "INVALID_TOP_K", "top_k must be in [1, 100]")

    if len(query) > 500:
        return _error(400, "INVALID_QUERY", "q must be <= 500 chars")

    start = time.perf_counter()

    # Embed the query with Bedrock Titan v2
    bedrock = boto3.client("bedrock-runtime", region_name="ap-south-1")
    embed_response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": query, "dimensions": 1024, "normalize": True}),
    )
    query_vector = json.loads(embed_response["body"].read())["embedding"]

    # Query S3 Vectors
    s3vectors = boto3.client("s3vectors", region_name="ap-south-1")
    query_response = s3vectors.query_vectors(
        vectorBucketName=os.environ.get("VECTOR_BUCKET", "datacurator-vectors-dev"),
        indexName=os.environ.get("VECTOR_INDEX", "datacurator-chunks-v1"),
        queryVector={"float32": query_vector},
        topK=top_k,
        returnMetadata=True,
    )

    matches = query_response.get("vectors", [])

    # Optionally fetch metadata from DynamoDB
    if matches:
        chunk_ids = [m["key"] for m in matches]
        dynamodb = boto3.client("dynamodb", region_name="ap-south-1")
        try:
            batch_response = dynamodb.batch_get_item(
                RequestItems={
                    os.environ.get("METADATA_TABLE", "datacurator-chunk-metadata-dev"): {
                        "Keys": [{"chunk_id": {"S": cid}} for cid in chunk_ids]
                    }
                }
            )
            metadata_map = {
                item["chunk_id"]["S"]: item
                for item in batch_response["Responses"][
                    os.environ.get("METADATA_TABLE", "datacurator-chunk-metadata-dev")
                ]
            }
        except Exception:
            metadata_map = {}
    else:
        metadata_map = {}

    # Format response
    results = []
    for match in matches:
        if min_score > 0 and match.get("distance", 1.0) > 1.0 - min_score:
            continue
        chunk_id = match["key"]
        meta = metadata_map.get(chunk_id, {})
        results.append(
            {
                "chunk_id": chunk_id,
                "score": round(1.0 - match.get("distance", 0.0), 4),
                "text_preview": meta.get("text_preview", {}).get("S", ""),
                "source": match.get("metadata", {}).get("source", "unknown"),
                "source_key": meta.get("source_key", {}).get("S", ""),
                "format": match.get("metadata", {}).get("format", "unknown"),
                "page": None,
                "category": match.get("metadata", {}).get("category"),
                "tags": [],
                "created_at": meta.get("created_at", {}).get("S", ""),
            }
        )

    duration_ms = int((time.perf_counter() - start) * 1000)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "query": query,
                "total_results": len(results),
                "results": results,
                "query_duration_ms": duration_ms,
            }
        ),
    }


def _error(status: int, code: str, message: str) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": code, "message": message}),
    }
