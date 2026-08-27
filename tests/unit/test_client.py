"""Unit tests for the DataCurator public client."""

from __future__ import annotations

from src.client import DataCuratorClient


class TestCostEstimation:
    def test_estimate_query_cost(self):
        # Initialize without API URL (we won't make calls)
        try:
            client = DataCuratorClient(api_url="https://example.com")
        except Exception:
            # Fall back if SSM lookup fails
            client = DataCuratorClient.__new__(DataCuratorClient)
            client.region = "ap-south-1"
            client.api_url = "https://example.com"

        # ~4 chars per token, $0.02/1M tokens
        cost_short = client._estimate_query_cost("hello")
        cost_long = client._estimate_query_cost("a" * 4000)

        # Short query: ~1 token = $0.00000002
        assert cost_short < 0.000001
        # Long query: ~1000 tokens = $0.00002
        assert 0.00001 < cost_long < 0.0001
        # Long should be more expensive than short
        assert cost_long > cost_short
