# REST API Reference

## Overview

DataCurator exposes a small HTTP API for searching the knowledge base and submitting feedback. The API is **server-side IAM authenticated** (SigV4); client tools must use AWS credentials.

Base URL: `https://<api-id>.execute-api.ap-south-1.amazonaws.com` (printed by Terraform output)

## Authentication

The API uses IAM authentication via AWS Signature Version 4. To call it, you need AWS credentials with permission to invoke the API.

```python
import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

session = boto3.Session()
credentials = session.get_credentials()
api_url = "https://abc123.execute-api.ap-south-1.amazonaws.com"

def signed_get(path, params=None):
    url = f"{api_url}{path}"
    request = AWSRequest(method="GET", url=url, params=params)
    SigV4Auth(credentials, "execute-api", "ap-south-1").add_auth(request)
    return requests.get(url, headers=dict(request.headers), params=params)
```

## Endpoints

### `GET /search`

Semantic search over the knowledge base.

**Query parameters**:

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `q` | string | Yes | — | Search query (1-500 chars) |
| `top_k` | integer | No | 10 | Number of results (1-100) |
| `source` | string | No | — | Filter by data source name |
| `format` | string | No | — | Filter by detected format (pdf, csv, json, etc.) |
| `min_score` | float | No | 0.0 | Minimum similarity score (0.0-1.0) |

**Response**:

```json
{
  "query": "company revenue 2025",
  "total_results": 10,
  "results": [
    {
      "chunk_id": "f4e2...",
      "score": 0.892,
      "text_preview": "Total revenue for FY2025 was $42.1M, up from $38.2M in FY2024...",
      "source": "retailpulse",
      "source_key": "ingests/retailpulse/2026/08/27/q3-report.pdf",
      "format": "pdf",
      "page": 12,
      "category": "financial-report",
      "tags": ["revenue", "q3-2025"],
      "created_at": "2026-08-27T10:23:45Z"
    }
  ],
  "query_duration_ms": 142
}
```

**Example**:

```bash
aws apigatewayv2 invoke \
  --api-id abc123 \
  --route-key "GET /search" \
  --query-string "q=company%20revenue&top_k=5" \
  --region ap-south-1
```

**Errors**:

| Status | Code | Description |
|---|---|---|
| 400 | `INVALID_QUERY` | `q` is missing or empty |
| 400 | `INVALID_TOP_K` | `top_k` is not in [1, 100] |
| 401 | `UNAUTHORIZED` | SigV4 signature missing or invalid |
| 429 | `THROTTLED` | Rate limit exceeded |
| 500 | `INTERNAL_ERROR` | Upstream service error (Bedrock, S3 Vectors) |
| 503 | `SERVICE_UNAVAILABLE` | Bedrock or S3 Vectors temporarily unavailable |

### `POST /feedback`

Submit user feedback on a chunk (for the self-learning classifier in Phase 3).

**Request body**:

```json
{
  "chunk_id": "f4e2...",
  "label": "misclassified" | "misrouted" | "good",
  "suggested_class": "financial-report",
  "notes": "This is actually a Q3 forecast, not actuals."
}
```

**Response**:

```json
{
  "feedback_id": "a1b2...",
  "chunk_id": "f4e2...",
  "status": "recorded",
  "recorded_at": "2026-08-27T12:00:00Z"
}
```

**Example**:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: AWS4-HMAC-SHA256 ..." \
  -d '{"chunk_id":"f4e2...","label":"misclassified","suggested_class":"financial-report"}' \
  https://abc123.execute-api.ap-south-1.amazonaws.com/feedback
```

**Errors**:

| Status | Code | Description |
|---|---|---|
| 400 | `INVALID_BODY` | JSON malformed |
| 400 | `INVALID_LABEL` | `label` not in {misclassified, misrouted, good} |
| 404 | `CHUNK_NOT_FOUND` | `chunk_id` doesn't exist |
| 401 | `UNAUTHORIZED` | SigV4 signature missing or invalid |
| 500 | `INTERNAL_ERROR` | DynamoDB write failed |

### `GET /health`

Health check (no auth).

**Response**:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "region": "ap-south-1",
  "uptime_seconds": 12345,
  "checks": {
    "s3_vectors": "ok",
    "dynamodb": "ok",
    "bedrock": "ok"
  }
}
```

## Rate limits

| Endpoint | RPS limit | Burst |
|---|---|---|
| `GET /search` | 50 | 100 |
| `POST /feedback` | 10 | 20 |
| `GET /health` | 100 | 200 |

Limits are per-API-key-equivalent. Adjustable in Terraform.

## CORS

CORS is configured to allow the KB UI origin. For external clients, add the origin to the Terraform `cors` config.

## Pagination

Search does not paginate in Phase 1; the response is capped at `top_k=100`. For Phase 2, we'll add `page_token` and `page_size`.

## Versioning

The API is versioned via the URL prefix: `/v1/search`, `/v1/feedback`, etc. The current version is implicit (no prefix). Version `v1` will be added when we make a breaking change.

## Client SDKs

### Python (official)

```python
from datacurator import DataCuratorClient

client = DataCuratorClient(region="ap-south-1")
results = client.search("company revenue", top_k=5)
client.feedback(chunk_id="f4e2...", label="misclassified", suggested_class="financial-report")
```

### Other languages

Generated SDKs (planned for Phase 5):

- TypeScript
- Go
- Java

For now, use the AWS SDK to sign requests, or use the open-source `boto3` (Python) / `aws-sdk-js-v3` (TypeScript) directly.

## See also

- [Architecture overview](../architecture/00-overview.md)
- [LLD](../architecture/02-lld.md) — Data shapes
- [Security model](../architecture/06-security-model.md) — Authentication
