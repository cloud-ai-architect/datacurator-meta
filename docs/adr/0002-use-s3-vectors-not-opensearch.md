# ADR-0002: Use S3 Vectors for vector storage, not OpenSearch

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: storage, cost, vectors

## Context and problem statement

We need a vector store for ~10K–1M embedded chunks (1024-dim from Bedrock Titan v2). Options evaluated:

- **OpenSearch Serverless** — managed vector DB, mature, expensive at idle
- **Aurora pgvector** — Postgres extension, well-understood, requires DB cluster
- **Pinecone** — third-party SaaS, vendor lock-in, data leaves AWS
- **S3 Vectors** — purpose-built vector storage in S3, GA in `ap-south-1` since 2025

The downstream consumers are RAG agents that need sub-200ms similarity search over the corpus.

## Decision drivers

- **Cost**: Side-project with $50–80/month total budget; idle cost must be near zero
- **Latency**: p95 < 200ms for top-10 similarity search
- **Data residency**: Must stay in AWS (`ap-south-1`)
- **Operational simplicity**: No always-on cluster to manage
- **Vendor preference**: AWS-native where possible

## Considered options

### Option 1: OpenSearch Serverless

- ✅ Mature, well-documented, native Bedrock integration
- ❌ **$0.30/hour per OCU × minimum 2 OCUs = $14.40/day = $432/month idle**
- ❌ Complex IAM, security policies, network policies
- ❌ Significant cold-start overhead

### Option 2: Aurora pgvector

- ✅ Strong SQL semantics, hybrid queries
- ✅ Reuses existing Aurora expertise
- ❌ Aurora Serverless v2 has minimum ACU of 0.5 ($43/month minimum)
- ❌ pgvector performance degrades above ~1M vectors
- ❌ Still requires a DB cluster

### Option 3: Pinecone

- ✅ Excellent performance, easy API
- ❌ Vendor lock-in, data leaves AWS
- ❌ $70/month for the smallest production tier
- ❌ Compliance review required for data residency

### Option 4: S3 Vectors

- ✅ **$0.04/GB-month storage + $0.004 per 1K queries**
- ✅ Zero idle cost (no always-on compute)
- ✅ Native AWS, IAM-scoped
- ✅ Purpose-built for this workload
- ⚠️ Newer service (GA 2025), smaller community
- ⚠️ Limited query expressiveness (top-K only, no filters)
- ⚠️ Available in fewer regions than S3 itself

## Decision outcome

**Chosen option 4: S3 Vectors** for Phase 1.

Index name: `datacurator-chunks-v1`
Vector dimensions: 1024 (Titan v2 default)
Distance metric: cosine

If S3 Vectors proves insufficient (e.g., we need hybrid search or pre-filtering), we migrate to Aurora pgvector in Phase 3 without changing the calling code (the `VectorStore` interface in `src/router.py` abstracts the backend).

### Consequences

**Positive**

- ~$0.50/month idle cost vs $432/month for OpenSearch
- Zero cluster management
- IAM-scoped, no separate auth
- Backed by S3 durability (11 9s)

**Negative**

- Less mature; some operations slower than OpenSearch
- No built-in hybrid search; need post-filtering in DynamoDB
- Documentation is sparse; expect to read SDK source

### Confirmation

- p95 query latency < 200ms for top-10 over 10K vectors (measured via `pytest tests/integration/test_vector_latency.py`)
- Total monthly cost stays under $5 for the portfolio's projected usage
- No data leaves AWS

## Pros and cons of the options

| Option | Idle cost/mo | Query cost | Latency | Maturity | Data residency |
| --- | --- | --- | --- | --- | --- |
| OpenSearch Serverless | $432 | Included | Low | High | AWS |
| Aurora pgvector | $43+ | Included | Low | High | AWS |
| Pinecone | $0 (free tier) / $70+ | Included | Very low | High | External |
| **S3 Vectors** | **$0.04/GB** | **$0.004/1K** | Low | Medium | AWS |

## References

- [Amazon S3 Vectors — AWS News Blog](https://aws.amazon.com/blogs/aws/amazon-s3-vectors-vector-storage-native-in-s3/)
- [S3 Vectors pricing](https://aws.amazon.com/s3/pricing/)
- [Bedrock Knowledge Bases — S3 Vectors integration](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
