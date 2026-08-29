# Deployment Diagram

## Purpose

This document shows the **AWS topology** of a deployed DataCurator instance — what resources exist in which region/account, how they connect, and the network paths data takes.

## Single-account, single-region deployment

```mermaid
graph TB
    subgraph Internet[Public Internet]
        User[KB UI user]
        Uploader[Data uploader]
    end

    subgraph CF[CloudFront edge]
        CFNode[CloudFront<br/>datacurator-kb-ui-cdn]
    end

    subgraph Region[AWS Region: ap-south-1]
        subgraph PublicSub[Public-facing]
            S3UI[S3: datacurator-ui-dev<br/>static website]
        end

        subgraph API[API layer]
            GW[API Gateway<br/>HTTP API]
            SearchLambda[Lambda: search]
            FeedbackLambda[Lambda: feedback]
        end

        subgraph Ingestion[Ingestion layer]
            S3Raw[S3: datacurator-raw-dev]
            EB[EventBridge rule]
        end

        subgraph Processing[Processing layer]
            SF[Step Function<br/>datacurator-pipeline-dev]
            DetectLambda[Lambda: detect]
            ParseLambda[Lambda: parse]
            ChunkLambda[Lambda: chunk]
            RedactLambda[Lambda: redact]
            EmbedLambda[Lambda: embed]
            ClassifyLambda[Lambda: classify]
            RouteLambda[Lambda: route]
        end

        subgraph Storage[Storage layer]
            S3V[S3 Vectors<br/>datacurator-vectors-dev]
            DDB1[DynamoDB<br/>chunk-metadata]
            DDB2[DynamoDB<br/>feedback]
            DDB3[DynamoDB<br/>jobs]
        end

        subgraph ML[ML services]
            BR[Bedrock<br/>titan-embed-v2]
        end

        subgraph Ops[Operations]
            CW[CloudWatch logs]
            SNS[SNS<br/>datacurator-failures]
            Bgt[Budget alarm<br/>$5 / $20 / $50]
        end
    end

    User -->|HTTPS| CFNode
    CFNode --> S3UI
    S3UI -->|JS calls| GW
    GW --> SearchLambda
    GW --> FeedbackLambda
    SearchLambda --> S3V
    SearchLambda --> DDB1
    FeedbackLambda --> DDB2

    Uploader -->|PUT| S3Raw
    S3Raw --> EB
    EB --> SF
    SF --> DetectLambda
    SF --> ParseLambda
    SF --> ChunkLambda
    SF --> RedactLambda
    SF --> EmbedLambda
    SF --> ClassifyLambda
    SF --> RouteLambda

    ParseLambda --> S3Raw
    EmbedLambda --> BR
    RouteLambda --> S3V
    RouteLambda --> DDB1
    RouteLambda --> DDB3

    SF -.->|failures| SNS
    Lambda -.->|logs| CW
    Bgt -.->|alerts| CW
```

## Resources by AWS service

| Service | Resources | Naming |
| --- | --- | --- |
| S3 | 3 buckets | `datacurator-{raw,vectors,ui}-dev` |
| S3 Vectors | 1 index | `datacurator-chunks-v1` (in `datacurator-vectors-dev`) |
| DynamoDB | 3 tables | `datacurator-{chunk-metadata,feedback,jobs}-dev` |
| Lambda | 9 functions | `datacurator-{stage}-dev` |
| Step Function | 1 state machine | `datacurator-pipeline-dev` |
| EventBridge | 1 rule | `datacurator-s3-trigger-dev` |
| API Gateway | 1 HTTP API | `datacurator-api-dev` |
| CloudFront | 1 distribution | `datacurator-kb-ui-cdn-dev` |
| SNS | 1 topic | `datacurator-failures-dev` |
| CloudWatch | Log groups | `/aws/lambda/datacurator-*-dev` |
| Budgets | 1 budget | `datacurator-monthly-dev` |
| IAM | 1 OIDC provider + 7 roles | `datacurator-*` |
| Resource Group | 1 group | `rg-datacurator-dev` |

## No VPC by design

This deployment has **no VPC** because:

1. All services are AWS-managed and accessed via service endpoints
2. Lambda functions run in AWS-managed compute (not in a customer VPC)
3. No RDS, ElastiCache, or EC2 that would require a VPC
4. Eliminates NAT gateway cost (~$32/month per AZ)
5. Eliminates VPC endpoint complexity for S3, DynamoDB, etc.

If Phase 5 introduces a need for private networking (e.g., a customer-managed Redis), a VPC would be added at that point.

## Account-wide controls (assumed pre-existing)

These should be set in the AWS Organization or root account, NOT in this Terraform:

- **Service Control Policies (SCPs)** — region restrictions, service denylist
- **AWS Config rules** — required tags, public bucket detection
- **CloudTrail** — organization-wide audit log
- **IAM Access Analyzer** — unused permission detection
- **GuardDuty** — threat detection

## Tagging strategy

Every resource carries:

```hcl
tags = {
  Project     = "datacurator"
  Environment = "dev"  # dev | staging | prod
  Owner       = "vijay"
  CostCenter  = "portfolio"
  ManagedBy   = "terraform"
  Purpose     = "raw|vectors|ui|api|compute|storage|..."
}
```

Resource Group `rg-datacurator-dev` is filter-based:

```text
ResourceTypeFilters: [all]
TagFilters:
  - Key: Project, Values: [datacurator]
  - Key: Environment, Values: [dev]
```

This shows all datacurator-dev resources in one view, regardless of AWS service.

## Cross-account deployment (multi-account)

To deploy the same codebase to another AWS account:

```mermaid
graph LR
    subgraph Code[GitHub repo]
        Codebase[datacurator-meta<br/>codebase]
    end

    subgraph A1[Account A: 761554981898]
        Stack1[dev stack]
    end

    subgraph A2[Account B: friend's account]
        Stack2[dev stack]
    end

    subgraph A3[Account C: prospect demo]
        Stack3[prod stack]
    end

    Codebase --> Stack1
    Codebase --> Stack2
    Codebase --> Stack3
```

Each account has its own:

- `bootstrap.sh` run once to set up state backend + OIDC
- `envs/<env>.tfvars` with account ID, region, project name
- GitHub Actions Environment secrets (`AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`)

The codebase is identical; only the tfvars differ.

## Bootstrap process (new AWS account)

```mermaid
sequenceDiagram
    participant Dev as Developer (you)
    participant CLI as Local CLI
    participant AWS as New AWS account
    participant GH as GitHub

    Dev->>CLI: bash scripts/bootstrap.sh datacurator dev ap-south-1
    CLI->>AWS: aws sts get-caller-identity
    CLI->>AWS: s3api create-bucket (state)
    CLI->>AWS: s3api put-bucket-versioning
    CLI->>AWS: s3api put-bucket-encryption
    CLI->>AWS: dynamodb create-table (lock)
    CLI->>AWS: iam create-open-id-connect-provider
    CLI-->>Dev: print role ARNs and bucket names

    Dev->>GH: Settings → Secrets → add AWS_DEPLOY_ROLE_ARN
    Dev->>CLI: cd infra/terraform && terraform init
    Dev->>CLI: terraform plan -var-file=envs/dev.tfvars
    Dev->>CLI: terraform apply -var-file=envs/dev.tfvars
    CLI->>AWS: create all datacurator resources
```

## Disaster recovery

| Disaster | Recovery |
| --- | --- |
| Region down | Re-deploy to a new region (multi-region is Phase 5) |
| Accidental bucket delete | Versioning + soft delete; restore from previous version |
| Terraform state corruption | Restore from S3 versioning (S3 has 99.999999999% durability) |
| Bad deploy | `terraform apply` previous commit; OIDC allows rapid rollback |
| Compromised GitHub PAT | Rotate GitHub secrets; OIDC scope is by repo so blast radius is small |

## See also

- [HLD](01-hld.md) — Service boundaries
- [LLD](02-lld.md) — Data shapes
- [Data flow](04-data-flow.md) — Sequence diagrams
- [Security model](06-security-model.md) — Trust boundaries
- [Cost model](07-cost-model.md) — Per-resource cost
- [Bootstrap script](../../scripts/bootstrap.sh) — New-account setup
