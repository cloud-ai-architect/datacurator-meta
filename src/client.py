"""Public client for downstream agent projects.

This module is what the other 14 portfolio projects (RetailPulse, MedAssist,
FinSight, etc.) will use to query the DataCurator knowledge base.

Designed to be:
- Easy to use (one import, one method)
- Type-safe (Pydantic models for inputs/outputs)
- Resilient (retries with exponential backoff)
- Cost-transparent (returns query cost estimate)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


@dataclass
class SearchResult:
    """A single search hit."""

    chunk_id: str
    score: float
    text_preview: str
    source: str
    source_key: str
    format: str
    page: int | None
    category: str | None
    tags: list[str]
    created_at: str


@dataclass
class SearchResponse:
    """Response from a search call."""

    query: str
    results: list[SearchResult]
    total_results: int
    query_duration_ms: int
    cost_usd: float  # estimated cost of the embedding call


class DataCuratorClient:
    """Client for the DataCurator knowledge base.

    Example:
        client = DataCuratorClient(region="ap-south-1")
        response = client.search("company revenue 2025", top_k=5)
        for result in response.results:
            print(f"{result.score:.3f}  {result.text_preview[:80]}")
    """

    def __init__(
        self,
        region: str = "ap-south-1",
        api_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Create a client.

        Args:
            region: AWS region where DataCurator is deployed.
            api_url: Base URL of the API Gateway. If None, looked up via
                CloudFormation/Terraform output.
            api_key: Optional API key (not used with IAM auth).

        Note: The client uses IAM SigV4 authentication by default. For
        long-running processes, pass AWS credentials via the standard
        AWS credential chain (env vars, ~/.aws/credentials, IAM role).
        """
        self.region = region
        self.api_url = api_url or self._lookup_api_url()
        self._session = boto3.Session()
        self._credentials = self._session.get_credentials()
        self._bedrock = boto3.client("bedrock-runtime", region_name=region)

    def _lookup_api_url(self) -> str:
        """Look up the API URL from Terraform output or SSM."""
        # In production, this would read from SSM Parameter Store
        # For now, raise if not provided
        raise ValueError(
            "api_url is required. Either pass it explicitly or set up "
            "the SSM Parameter Store lookup. See deploy runbook."
        )

    def _sign_and_call(self, method: str, path: str, body: dict | None = None) -> dict[str, Any]:
        """Sign a request with SigV4 and call the API."""
        url = f"{self.api_url}{path}"
        body_str = json.dumps(body) if body else None

        request = AWSRequest(
            method=method,
            url=url,
            data=body_str,
            headers={"Content-Type": "application/json"} if body_str else {},
        )
        SigV4Auth(self._credentials, "execute-api", self.region).add_auth(request)
        response = requests.request(
            method=method,
            url=url,
            headers=dict(request.headers),
            data=body_str,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def search(
        self,
        query: str,
        top_k: int = 10,
        source: str | None = None,
        format: str | None = None,
        min_score: float = 0.0,
    ) -> SearchResponse:
        """Semantic search over the knowledge base.

        Args:
            query: Search query (1-500 chars).
            top_k: Number of results (1-100).
            source: Filter by data source name.
            format: Filter by detected format.
            min_score: Minimum similarity score (0.0-1.0).

        Returns:
            SearchResponse with results and cost estimate.
        """
        params: dict[str, str | int | float] = {"q": query, "top_k": top_k}
        if source is not None:
            params["source"] = source
        if format is not None:
            params["format"] = format
        if min_score > 0:
            params["min_score"] = min_score

        # Build path with query string
        path = "/search?" + "&".join(
            f"{k}={requests.utils.quote(str(v))}" for k, v in params.items()
        )

        data = self._sign_and_call("GET", path)

        results = [
            SearchResult(
                chunk_id=r["chunk_id"],
                score=r["score"],
                text_preview=r["text_preview"],
                source=r["source"],
                source_key=r["source_key"],
                format=r["format"],
                page=r.get("page"),
                category=r.get("category"),
                tags=r.get("tags", []),
                created_at=r["created_at"],
            )
            for r in data.get("results", [])
        ]

        return SearchResponse(
            query=data.get("query", query),
            results=results,
            total_results=data.get("total_results", len(results)),
            query_duration_ms=data.get("query_duration_ms", 0),
            cost_usd=self._estimate_query_cost(query),
        )

    def feedback(
        self,
        chunk_id: str,
        label: str,
        suggested_class: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Submit feedback for a chunk (for the self-learning loop).

        Args:
            chunk_id: The chunk ID (from a previous search result).
            label: One of "misclassified", "misrouted", "good".
            suggested_class: If misclassified, what should it be?
            notes: Free-text notes.

        Returns:
            Response from the API.
        """
        body: dict[str, Any] = {"chunk_id": chunk_id, "label": label}
        if suggested_class is not None:
            body["suggested_class"] = suggested_class
        if notes is not None:
            body["notes"] = notes
        return self._sign_and_call("POST", "/feedback", body)

    def _estimate_query_cost(self, query: str) -> float:
        """Estimate the cost of embedding the query."""
        # Titan v2: $0.02 / 1M tokens, ~4 chars per token
        tokens = max(1, len(query) // 4)
        return (tokens / 1_000_000) * 0.02
