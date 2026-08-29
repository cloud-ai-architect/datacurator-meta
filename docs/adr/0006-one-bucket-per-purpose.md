# ADR-0006: One S3 bucket per purpose, not one bucket per environment

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: storage, naming, isolation

## Context and problem statement

We have several S3 buckets in the design: raw ingests, vector storage, KB UI, Terraform state. We need to decide on the naming and grouping pattern.

Two schools of thought:

1. **One bucket per environment** — `datacurator-dev`, `datacurator-staging`, `datacurator-prod` with prefixes inside (`raw/`, `vectors/`, `ui/`)
2. **One bucket per purpose per environment** — `datacurator-raw-dev`, `datacurator-vectors-dev`, `datacurator-ui-dev`

## Decision drivers

- **IAM scoping** — easier to grant least-privilege when a bucket has a single purpose
- **Lifecycle policies** — different buckets have different retention (raw 30 days, vectors forever, logs 7 days)
- **Public access** — the UI bucket is public; raw and vectors must not be public
- **Cost attribution** — separate cost-per-bucket visibility
- **Bucket policy simplicity** — single-purpose buckets have single-purpose policies

## Considered options

### Option 1: One bucket per environment, prefixes inside

- ✅ Fewer buckets to manage
- ✅ Easy to delete an entire environment
- ❌ Lifecycle policies get complex (different prefixes → different policies)
- ❌ Public access block on the bucket would block the UI prefix
- ❌ Blast radius — an over-permissive bucket policy affects everything inside
- ❌ Hard to give Lambda function X access to only `vectors/` prefix

### Option 2: One bucket per purpose per environment (chosen)

- ✅ Single-purpose IAM policies
- ✅ Tailored lifecycle rules per bucket
- ✅ Public access block is unambiguous (raw/vectors blocked, UI allowed)
- ✅ Cost attribution per purpose
- ✅ Easier to add Resource Groups per bucket
- ⚠️ More buckets to manage (but Terraform modules abstract this)
- ⚠️ S3 global namespace — need to ensure unique names per account

## Decision outcome

**Chosen option 2: One bucket per purpose per environment.**

Naming convention:

```json
{project}-{purpose}-{environment}
  - datacurator-raw-dev
  - datacurator-vectors-dev
  - datacurator-ui-dev
  - datacurator-raw-staging
  - datacurator-vectors-staging
  - datacurator-ui-staging
  - datacurator-raw-prod
  - datacurator-vectors-prod
  - datacurator-ui-prod
  - datacurator-tfstate-dev      (Terraform state)
  - datacurator-tfstate-lock-dev (DynamoDB lock table, not a bucket)
```

The `raw` and `vectors` buckets have **public access fully blocked** at the account level (via `aws s3control put-public-access-block`).
The `ui` bucket is the only one with public ACLs allowed, and only for the `static/` prefix.

### Consequences

**Positive**

- IAM policies are single-purpose and short (e.g., "Lambda can read `datacurator-vectors-dev` only")
- Lifecycle rules per bucket reflect actual data lifecycle
- Cost reports clearly show "raw storage: $X, vector storage: $Y, UI bandwidth: $Z"
- Public access block is set-and-forget for non-UI buckets

**Negative**

- 3× the number of buckets compared to option 1
- S3 namespace collisions possible (mitigated by `random_id` suffix in Phase 5)

### Confirmation

- Public access blocked on all non-UI buckets (verified via `aws s3api get-public-access-block`)
- Each bucket has a single resource tag (`Project=datacurator`, `Purpose=raw|vectors|ui`, `Environment=dev|staging|prod`)
- IAM policies are < 30 lines each (per audit)

## Pros and cons of the options

| Option | IAM clarity | Lifecycle | Public access | Cost visibility | Bucket count |
| --- | --- | --- | --- | --- | --- |
| 1. Per env | ⚠️ Complex | ⚠️ Mixed | ❌ Conflicts | ⚠️ Mixed | Low |
| **2. Per purpose** | **✅ Clear** | **✅ Tailored** | **✅ Unambiguous** | **✅ Per purpose** | **Medium** |

## References

- [S3 bucket naming rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html)
- [S3 Public Access Block](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-best-practices.html)
- [AWS Resource Groups](https://docs.aws.amazon.com/ARG/latest/userguide/)
