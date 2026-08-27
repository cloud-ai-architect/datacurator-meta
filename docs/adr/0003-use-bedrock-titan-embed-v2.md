# ADR-0003: Use Bedrock Titan Embed Text v2 as the primary embedding model

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: ml, cost, embeddings

## Context and problem statement

We need an embedding model for semantic search over ingested chunks. Requirements:

- Available in `ap-south-1` (our deployment region)
- Cost: ≤$0.10 per 1M tokens
- Quality: Reasonable for English + code + (later) Indian languages
- Vector dimension: ≤1024 (S3 Vectors sweet spot)
- Native integration with S3 Vectors and Step Functions

## Decision drivers

- Cost efficiency (per-token pricing)
- Multilingual support (future: Hindi, Tamil, Bengali for downstream Indian verticals)
- AWS-native (no external API dependencies, no data egress)
- Predictable latency for Step Function orchestration

## Considered options

### Option 1: Amazon Titan Embed Text v2

- ✅ **$0.02 per 1M input tokens** (cheapest in-region)
- ✅ 1024 / 512 / 256-dim options
- ✅ Multilingual (100+ languages)
- ✅ Native to S3 Vectors
- ⚠️ No domain-specific tuning out of the box

### Option 2: Cohere Embed v3 (English / Multilingual)

- ✅ Excellent quality benchmarks
- ⚠️ **$0.10 per 1M tokens** (5× more expensive than Titan)
- ✅ Strong domain performance
- ⚠️ Limited dimensions (1024 only for v3)

### Option 3: Amazon Titan Embed Image v1

- ✅ For image-only embeddings
- ❌ Wrong modality for text chunks

## Decision outcome

**Chosen option 1: Amazon Titan Embed Text v2 (1024-dim)** as the default embedder.

Cohere Embed v3 remains available as a per-source alternative (e.g., for code-heavy sources where it has slight quality edge), configured via `config/embedders/cohere-multilingual.yaml`.

Future-proofing: the `Embedder` interface in `src/embedder.py` accepts any provider, so swapping is a config change.

### Consequences

**Positive**

- $0.02/1M tokens → $0.02 to embed 1M chunks
- Multilingual without extra configuration
- Same-region, no egress cost

**Negative**

- Quality may lag Cohere on some domain-specific benchmarks
- No batch API (call per chunk, parallelize via Lambda concurrency)

### Confirmation

- Embedding quality validated by retrieval precision@10 > 0.80 on a held-out test set
- Total embedding cost per million chunks < $0.10

## Pros and cons of the options

| Model | Cost/1M tok | Dims | Multilingual | Quality | In-region |
|---|---|---|---|---|---|
| **Titan v2** | **$0.02** | 1024/512/256 | ✅ | Good | ✅ |
| Cohere v3 | $0.10 | 1024 | ✅ (v3-mul) | Excellent | ✅ |
| Titan Image v1 | $0.08 | 1024 | n/a | (images) | ✅ |

## References

- [Amazon Titan Embeddings — AWS Docs](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)
- [Bedrock pricing](https://aws.amazon.com/bedrock/pricing/)
