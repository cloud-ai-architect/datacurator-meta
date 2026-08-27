# ADR-0005: Use Terraform for IaC, not AWS CDK

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: infrastructure, tooling

## Context and problem statement

We need to choose an Infrastructure-as-Code (IaC) tool. Both Terraform and AWS CDK are first-class options. The user already has CDK bootstrapped in this account (CDK asset bucket exists), suggesting prior CDK usage.

The decision affects:
- Who can read/modify infrastructure
- How reusable the codebase is for the other 14 portfolio projects
- Long-term maintainability
- Tooling ecosystem (linting, scanning, docs generation)

## Decision drivers

- **Portability across clouds** — DataCurator's design is cloud-portable (AWS / Azure / GCP per the project tagline)
- **Tooling maturity** — pre-commit hooks, linters, security scanners, docs generators
- **Public repo readability** — recruiters and contributors should be able to read and understand
- **Multi-account deployment** — single tool must work across all target accounts
- **Skill transfer** — Terraform skills are more transferable than CDK (TypeScript/Go/Python)

## Considered options

### Option 1: AWS CDK (TypeScript)

- ✅ First-class AWS support
- ✅ TypeScript types for AWS APIs
- ✅ Reuses user's existing CDK bootstrap
- ❌ AWS-only (not portable)
- ❌ Adds a compile step (tsc)
- ❌ Slower to onboard for non-TypeScript developers
- ❌ Generated CloudFormation is verbose and hard to read

### Option 2: AWS CDK (Python)

- ✅ Same as TS CDK but in Python
- ❌ Still AWS-only
- ❌ Less mature than TS CDK

### Option 3: Terraform (chosen)

- ✅ **Cloud-portable** — same HCL works against AWS, Azure, GCP providers
- ✅ **Mature tooling** — tflint, tfsec, checkov, terraform-docs, drift detection
- ✅ **Declarative HCL** is more readable than CDK code
- ✅ **State portability** — S3 backend works the same everywhere
- ✅ **Module ecosystem** — public registry for common patterns
- ⚠️ Less ergonomic for complex application logic (we use Python for that)
- ⚠️ HCL provider bugs can be frustrating

### Option 4: Pulumi

- ✅ General-purpose languages (Python, Go, TS)
- ❌ Smaller community than Terraform
- ❌ Less tooling

## Decision outcome

**Chosen option 3: Terraform ≥1.9** for all infrastructure.

Application code remains Python (Lambda handlers, Step Function orchestration logic, parsers, embedders). Terraform handles only the **provisioned resources** (buckets, DynamoDB tables, IAM roles, Step Function state machine, API Gateway, etc.).

The existing CDK asset bucket (`cdk-hnb659fds-assets-761554981898-ap-south-1`) is left untouched per the "no other assets modified" rule; new Terraform state is stored in a separate bucket created by `bootstrap.sh`.

### Consequences

**Positive**

- Cloud-portable: same `infra/terraform/` can deploy to AWS, Azure, GCP (with provider swap)
- Rich tooling: tflint, tfsec, checkov, terraform-docs
- State in S3 with DynamoDB locking is the de-facto standard
- Module reusability across the 15-project portfolio

**Negative**

- Less type safety than CDK
- Provider bug workarounds sometimes required
- Initial setup is more verbose than `cdk init`

### Confirmation

- All infrastructure changes go through `terraform plan` in PRs
- `tfsec` reports 0 high/critical findings
- Modules are reusable across at least 3 portfolio projects

## Pros and cons of the options

| Option | Cloud-portable | Tooling | Onboarding | Mature |
|---|---|---|---|---|
| CDK (TS) | ❌ AWS only | Medium | Slow (TS) | ✅ |
| CDK (Python) | ❌ AWS only | Medium | Medium | ✅ |
| **Terraform** | **✅ All** | **Rich** | **Fast** | **✅** |
| Pulumi | ✅ All | Medium | Medium | ⚠️ |

## References

- [Terraform AWS provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [tflint](https://github.com/terraform-linters/tflint)
- [tfsec](https://github.com/aquasecurity/tfsec)
- [terraform-docs](https://github.com/terraform-docs/terraform-docs)
- [AWS CDK](https://aws.amazon.com/cdk/)
