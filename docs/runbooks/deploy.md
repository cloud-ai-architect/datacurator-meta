# Deploy Runbook

## Purpose

Step-by-step procedure to deploy DataCurator to a new AWS account, or to redeploy after a change. This is the operational reference for the bootstrap + apply flow.

## Pre-requisites

- [ ] AWS CLI ≥ 2.x installed and configured (`aws configure`)
- [ ] Terraform ≥ 1.9 installed
- [ ] Python ≥ 3.12 (for local testing, optional)
- [ ] GitHub CLI (for OIDC setup, optional)
- [ ] AWS account with admin access for the bootstrap step
- [ ] GitHub repo with admin access (for secrets)

## Deploy to a new AWS account

### Step 1: Clone the repo

```bash
git clone https://github.com/vijaymadhu/datacurator-meta.git
cd datacurator-meta
```

### Step 2: Run bootstrap (one time per account)

```bash
bash scripts/bootstrap.sh datacurator dev ap-south-1
```

This creates:

- S3 bucket for Terraform state (versioned, encrypted, public-blocked)
- DynamoDB table for state locking
- GitHub OIDC provider
- GitHub Actions deploy IAM role

The script prints the role ARN and bucket names. **Copy these.**

### Step 3: Add GitHub secrets

Go to your GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

| Name | Value | Source |
|---|---|---|
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::ACCOUNT:role/datacurator-github-deploy-role-dev` | From bootstrap output |
| `AWS_REGION` | `ap-south-1` | From bootstrap input |

### Step 4: Initialize Terraform

```bash
cd infra/terraform
terraform init \
  -backend-config="bucket=datacurator-tfstate-dev" \
  -backend-config="region=ap-south-1" \
  -backend-config="dynamodb_table=datacurator-tfstate-lock-dev"
```

### Step 5: Review the plan

```bash
terraform plan -var-file=envs/dev.tfvars -out=tfplan
```

Expected output: 30–50 resources to add, 0 to change, 0 to destroy.

**Important**: If the plan shows any resources being **destroyed**, do NOT apply. Investigate first — it usually means the state has drifted from reality. Common causes:

- Manual changes in the AWS console
- A previous partial destroy
- A module refactor that needs `terraform state mv`

### Step 6: Apply

```bash
terraform apply tfplan
```

Time: ~5–10 minutes.

### Step 7: Verify

```bash
cd ../..
bash scripts/verify.sh dev ap-south-1
```

All checks should pass.

### Step 8: Upload a test file

```bash
aws s3 cp tests/fixtures/example.pdf \
  s3://datacurator-raw-dev/ingests/test/$(date +%Y/%m/%d)/example.pdf \
  --region ap-south-1
```

### Step 9: Watch the pipeline

```bash
# Get the execution ARN from CloudWatch logs
aws logs tail /aws/vendedlogs/states/datacurator-pipeline-dev \
  --follow --region ap-south-1

# Or use the Step Functions console:
# https://ap-south-1.console.aws.amazon.com/states/home
```

### Step 10: Test the KB UI

Open the CloudFront URL printed by Terraform output. Search for a term. Verify results appear.

## Redeploy after a code change

For changes that affect infrastructure:

```bash
# Make your changes
# Commit and push
git add -A
git commit -s -m "feat: add new resource"
git push origin main

# GitHub Actions runs plan + apply automatically
# Review the PR or check Actions tab
```

For changes that affect only Lambda code:

```bash
# GitHub Actions rebuilds and updates the Lambda code
# No infra change required
```

## Roll back a deploy

If a deploy breaks something:

```bash
# Option 1: Revert the commit and push
git revert HEAD
git push origin main

# Option 2: Apply previous state
cd infra/terraform
terraform plan -var-file=envs/dev.tfvars
# If destructive, use:
terraform state pull > current.tfstate
# Restore previous state from S3 versioning
# Then apply
```

## Multi-account deploy

To deploy the same codebase to a second AWS account:

```bash
# In the second account:
bash scripts/bootstrap.sh datacurator dev ap-south-1 <your-github-org> <your-fork-name>

# In your fork's GitHub:
# - Add the same secrets (different role ARN)
# - Push to your fork's main

# In your local clone of the fork:
cd infra/terraform
terraform init ...  # (with new backend)
terraform plan -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

## Environment promotion (dev → staging → prod)

The codebase uses the same Terraform for all environments; only `envs/<env>.tfvars` differs.

```bash
# In the same AWS account, with separate state:
terraform init -backend-config="bucket=datacurator-tfstate-staging" ...
terraform plan -var-file=envs/staging.tfvars
terraform apply -var-file=envs/staging.tfvars

# In production, ALWAYS run plan first, review with team
# Manual approval via GitHub Environment "production"
```

## Troubleshooting

### "AccessDenied" during terraform plan

- Check the `AWS_DEPLOY_ROLE_ARN` GitHub secret matches the role from bootstrap
- Verify OIDC trust policy includes your repo
- Check `aws sts get-caller-identity` works locally

### "Bucket already exists and is owned by you" or "by another account"

- The bucket name is globally unique. If another AWS account created `datacurator-vectors-dev`, pick a different name (use `random_id` suffix in `envs/<env>.tfvars`)

### Bedrock "AccessDeniedException"

- You need to enable model access in the Bedrock console first
- Go to https://ap-south-1.console.aws.amazon.com/bedrock/home → Model access → Enable "Titan Text Embeddings v2"

### Step Function execution fails immediately

- Check CloudWatch logs for the failing Lambda
- Verify the IAM role has permissions for S3 GetObject on the raw bucket
- Verify the S3 event notification is set on the raw bucket

### CloudFront returns 403

- Check the S3 bucket policy allows CloudFront OAC
- Check the CloudFront origin is configured correctly
- Wait ~5 minutes for CloudFront propagation

## See also

- [Bootstrap script](../../scripts/bootstrap.sh) — New-account setup
- [Destroy script](../../scripts/destroy.sh) — Tear down
- [Verify script](../../scripts/verify.sh) — Health check
- [Architecture overview](../architecture/00-overview.md) — What gets deployed
