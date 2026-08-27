# Rollback Runbook

## Purpose

Step-by-step procedure to roll back a deploy that introduced a problem. Covers code rollbacks, infrastructure rollbacks, and data rollbacks.

## When to roll back

Roll back when:

- A deploy caused a regression (e.g., pipeline failure rate > 5%)
- A new feature has a critical bug
- A Terraform apply introduced an unintended resource
- An IAM change is too permissive (security issue)

**Don't** roll back for:

- Cosmetic issues (file a bug instead)
- Performance regressions < 20% (file a perf issue)
- A test failure in a single test (fix the test, don't roll back the code)

## Roll back types

### Type 1: Code rollback (Lambda, configs, policies)

The most common case. A new Lambda version or config change broke something.

**Time: 2–5 minutes**

```bash
# Option A: Revert the commit
git revert HEAD
git push origin main
# GitHub Actions runs apply with the reverted code

# Option B: Re-deploy previous version
git log --oneline -5  # find the last good SHA
git checkout <last-good-sha>
git push origin <last-good-sha>:main --force-with-lease
```

### Type 2: Infrastructure rollback

A Terraform apply created an unintended resource, or removed something it shouldn't have.

**Time: 5–15 minutes**

```bash
cd infra/terraform

# Restore previous state from S3 versioning
aws s3api list-object-versions \
  --bucket datacurator-tfstate-dev \
  --key dev/terraform.tfstate \
  --region ap-south-1

# Download the previous version
aws s3api get-object \
  --bucket datacurator-tfstate-dev \
  --key dev/terraform.tfstate \
  --version-id <previous-version-id> \
  terraform.tfstate.previous \
  --region ap-south-1

# Backup current state
cp terraform.tfstate terraform.tfstate.broken

# Use the previous state
cp terraform.tfstate.previous terraform.tfstate

# Apply (will show the diff between broken and previous)
terraform plan -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

### Type 3: Data rollback

A pipeline run wrote bad data (e.g., new classifier assigned wrong categories).

**Time: 15–60 minutes**

```bash
# 1. Identify the bad data
# Query DynamoDB for chunks from the bad run:
aws dynamodb query \
  --table-name datacurator-chunk-metadata-dev \
  --index-name job-index \
  --key-condition-expression "job_id = :jid" \
  --expression-attribute-values '{":jid":{"S":"<bad-job-id>"}}' \
  --region ap-south-1

# 2. Delete from S3 Vectors
aws s3vectors delete-vectors \
  --vector-bucket-name datacurator-vectors-dev \
  --index-name datacurator-chunks-v1 \
  --keys "<chunk-id-1>,<chunk-id-2>" \
  --region ap-south-1

# 3. Delete from DynamoDB
aws dynamodb batch-write-item \
  --request-items '{
    "datacurator-chunk-metadata-dev": [
      {"DeleteRequest": {"Key": {"chunk_id": {"S": "<chunk-id-1>"}}}},
      {"DeleteRequest": {"Key": {"chunk_id": {"S": "<chunk-id-2>"}}}}
    ]
  }' \
  --region ap-south-1

# 4. Re-trigger the pipeline with the old (known-good) code
git revert HEAD
git push origin main
# Re-upload the original file to trigger re-processing
```

### Type 4: Emergency: revert IAM

If a deploy gave a Lambda too much access:

```bash
# 1. Immediately delete the over-permissive policy
aws iam delete-role-policy \
  --role-name datacurator-route-lambda-dev \
  --policy-name <over-permissive-policy-name>

# 2. Apply known-good IAM from git
cd infra/terraform
terraform plan -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars

# 3. Post-mortem: add a tfsec rule to catch this in CI
```

## Communication

After rolling back:

1. **Notify stakeholders** — post in the team channel
2. **File an incident** — even if it was a small roll-back
3. **Post-mortem** — within 48 hours for any rollback > 15 minutes
4. **Add a regression test** — to prevent the same issue

## Recovery time objectives

| Rollback type | Target RTO | Notes |
|---|---|---|
| Code | 5 min | Just a git revert |
| Infrastructure | 15 min | Requires S3 state restore |
| Data | 60 min | Requires manual re-processing |
| IAM emergency | 5 min | Quick policy delete |

## Prevention

- **PR review required** — required reviewers in branch protection
- **Plan-only on PRs** — no direct applies from PRs
- **Required CI checks** — tflint, tfsec, gitleaks, tests
- **Cost alarms** — catch runaway Lambda loops
- **CloudWatch alarms** — on error rate, queue depth, etc.

## See also

- [Deploy runbook](deploy.md) — Forward deploys
- [Incident response runbook](incident-response.md) — Live incident handling
- [Security model](../architecture/06-security-model.md) — IAM best practices
