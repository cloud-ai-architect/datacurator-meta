# Cost Model

## Purpose

This document is the **single source of truth** for DataCurator's cost — what each component costs, what a typical workload costs, and how the architecture decisions keep cost low. Use this to forecast spend, justify architecture choices, and identify optimization opportunities.

## TL;DR

| Scenario | Monthly cost |
| --- | --- |
| **Idle** (no traffic) | **~$0.50 / month** |
| **Light usage** (1K pipeline runs, 10K searches) | **~$5 / month** |
| **Moderate usage** (10K pipeline runs, 100K searches) | **~$25 / month** |
| **Heavy usage** (100K pipeline runs, 1M searches) | **~$150 / month** |

## Cost by component

### Compute (Lambda + Step Functions)

| Component | Pricing | Per-pipeline-run cost |
| --- | --- | --- |
| Lambda invocations | $0.20 / 1M requests | ~$0.000002 (8 invocations) |
| Lambda GB-seconds | $0.0000166667 / GB-s | ~$0.0008 (avg 512MB, 3s) |
| Step Function transitions | $0.025 / 1K transitions | ~$0.0002 (8 transitions) |
| **Per-run compute** | | **~$0.001** |

### AI / ML (Bedrock)

| Component | Pricing | Per-chunk cost |
| --- | --- | --- |
| Titan Embed v2 | $0.02 / 1M input tokens | ~$0.00001 (avg 500 tokens) |
| **Embedding per 1K chunks** | | **~$0.01** |
| Classifier (Claude Haiku 4.5) | $0.25 / 1M input tokens, $1.25 / 1M output | ~$0.0005 per chunk |
| **Classification per 1K chunks** | | **~$0.50** |

### Storage

| Component | Pricing | Per-month cost |
| --- | --- | --- |
| S3 standard (raw, 1 GB) | $0.023 / GB | $0.023 |
| S3 Vectors (1 GB vectors) | $0.04 / GB | $0.04 |
| DynamoDB (1 GB, on-demand) | $1.25 / million WCU/RCU | ~$0.10 (1K ops/day) |
| **Storage for 1 GB corpus** | | **~$0.16** |

### API and CDN

| Component | Pricing | Per-request cost |
| --- | --- | --- |
| API Gateway HTTP | $1.00 / million requests | $0.000001 |
| Lambda (search) | $0.20 / 1M | $0.0000002 |
| Bedrock Titan (query) | $0.02 / 1M tokens | $0.0000002 |
| S3 Vectors query | $0.004 / 1K queries | $0.000004 |
| **Per search request** | | **~$0.000005** |
| CloudFront (10 GB transfer) | $0.085 / GB | $0.85 / month |
| CloudFront (1M requests) | $0.01 / 10K | $1.00 / month |

### Other

| Component | Pricing | Per-month cost |
| --- | --- | --- |
| CloudWatch logs (1 GB) | $0.50 / GB | $0.50 |
| CloudWatch metrics (10 custom) | $0.30 / metric | $3.00 |
| SNS (1K notifications) | $0.50 / million | $0.0005 |
| Budgets (1 budget) | $0.01 / budget / day | $0.30 |
| KMS (1 key) | $1.00 / key / month | $1.00 |

## Per-pipeline-run cost

A typical run processes a 1 MB PDF → ~50 chunks → ~25K tokens.

| Stage | Cost |
| --- | --- |
| Lambda (8 invocations, avg 3s, 512MB) | $0.0008 |
| Step Functions (8 transitions) | $0.0002 |
| Bedrock embedding (25K tokens) | $0.0005 |
| Bedrock classification (50 chunks × 500 tok) | $0.0250 |
| DynamoDB writes (50 items) | $0.0075 |
| S3 Vectors writes (50 vectors) | $0.0002 |
| **Total per pipeline run** | **~$0.034** |

For a CSV → ~10 chunks → ~5K tokens, total is ~$0.005.

## Per-search-request cost

A search returns top-10 results.

| Stage | Cost |
| --- | --- |
| API Gateway | $0.000001 |
| Lambda (search) | $0.0000002 |
| Bedrock embedding (query, ~50 tokens) | $0.000001 |
| S3 Vectors query (top-10) | $0.000004 |
| DynamoDB reads (10 items) | $0.0000125 |
| **Total per search** | **~$0.00002** |

## Cost scaling

| Workload | Pipeline runs/mo | Search req/mo | Compute | Bedrock | Storage | API | **Total** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Idle | 0 | 0 | $0.00 | $0.00 | $0.50 | $0.00 | **$0.50** |
| Light | 1,000 | 10,000 | $1.00 | $0.50 | $1.00 | $0.10 | **$2.60** |
| Moderate | 10,000 | 100,000 | $10.00 | $5.00 | $5.00 | $1.00 | **$21.00** |
| Heavy | 100,000 | 1,000,000 | $100.00 | $50.00 | $25.00 | $10.00 | **$185.00** |
| Extreme | 1,000,000 | 10,000,000 | $1,000.00 | $500.00 | $100.00 | $100.00 | **$1,700.00** |

## Cost comparison: S3 Vectors vs alternatives

| Solution | Idle / month | 10K vectors, 100K queries / month |
| --- | --- | --- |
| **S3 Vectors** | **$0.04** | **$0.40** |
| OpenSearch Serverless (2 OCU min) | $432.00 | $432.00 |
| Aurora pgvector (Serverless v2, 0.5 ACU min) | $43.00 | $50.00 |
| Pinecone (Standard, 1 pod) | $70.00 | $70.00 |

**S3 Vectors is 1,000× cheaper than OpenSearch Serverless at idle.**

## Cost comparison: Titan v2 vs Cohere v3

| Model | 1M tokens cost | 1M chunks (avg 500 tok) cost |
| --- | --- | --- |
| **Titan v2** | **$0.02** | **$10** |
| Cohere v3 (English) | $0.10 | $50 |
| OpenAI text-embedding-3-small | $0.02 | $10 (but external API, adds egress) |

**Titan v2 is 5× cheaper than Cohere v3 with comparable quality for general use.**

## Cost optimization techniques

### Already applied (Phase 1)

1. **S3 Vectors over OpenSearch** — 1000× cheaper idle
2. **Bedrock Titan v2 over Cohere v3** — 5× cheaper
3. **Lambda concurrency limits** — prevent runaway cost
4. **DynamoDB on-demand** — only pay for what you use
5. **S3 lifecycle policies** — auto-delete old raw files after 30 days
6. **CloudWatch log retention** — 30 days, not forever
7. **HTTP API over REST API** — 70% cheaper per request

### Future optimizations (Phase 2+)

1. **Provisioned concurrency for high-traffic Lambdas** — saves ~30% on sustained traffic
2. **S3 Intelligent-Tiering** for raw bucket — auto-move to Infrequent Access after 30 days
3. **Reserved capacity for DynamoDB** if traffic is predictable
4. **Caching layer** (DAX or ElastiCache) for frequently-searched queries
5. **Batch API for Bedrock** — single call for multiple chunks (up to 25)

## Budgets and alarms

Three budget thresholds with automatic alerts:

```hcl
resource "aws_budgets_budget" "datacurator_monthly" {
  name         = "datacurator-monthly-${var.environment}"
  budget_type  = "COST"
  limit_amount = "20"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 25   # $5
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = ["vijaymadhu@users.noreply.github.com"]
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100  # $20
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = ["vijaymadhu@users.noreply.github.com"]
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 250  # $50
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = ["vijaymadhu@users.noreply.github.com"]
  }
}
```

Alerts fire at **$5, $20, $50** monthly spend.

## What we're NOT optimizing for

- **Multi-AZ redundancy** — single AZ is acceptable for portfolio scope
- **Multi-region** — Phase 5 enhancement
- **Sub-100ms p99 latency** — p95 < 300ms is sufficient
- **99.99% availability** — 99.9% (AWS-managed) is sufficient

If any of these become important, cost will increase 2–10×.

## See also

- [ADR-0002: Use S3 Vectors](../adr/0002-use-s3-vectors-not-opensearch.md) — Why S3 Vectors
- [ADR-0003: Use Bedrock Titan v2](../adr/0003-use-bedrock-titan-embed-v2.md) — Why Titan
- [Deployment diagram](05-deployment-diagram.md) — Resources
- [Cost investigation runbook](../runbooks/cost-investigation.md) — How to investigate spikes
