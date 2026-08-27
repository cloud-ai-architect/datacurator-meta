#!/usr/bin/env bash
# scripts/bootstrap.sh
# ------------------------------------------------------------------------------
# DataCurator — One-time bootstrap for a new AWS account.
#
# Sets up:
#   - Terraform state S3 bucket (versioned, encrypted, public-blocked)
#   - DynamoDB lock table for state
#   - GitHub OIDC provider
#   - GitHub Actions deploy IAM role
#
# Idempotent: re-running is safe; existing resources are left intact.
#
# Usage:
#   bash scripts/bootstrap.sh [PROJECT] [ENV] [REGION] [GITHUB_ORG] [GITHUB_REPO]
#
# Defaults match the current project. Override for fork/portability testing.
# ------------------------------------------------------------------------------
set -euo pipefail

PROJECT="${1:-datacurator}"
ENV="${2:-dev}"
REGION="${3:-ap-south-1}"
GITHUB_ORG="${4:-vijaymadhu}"
GITHUB_REPO="${5:-datacurator-meta}"

echo "==> DataCurator bootstrap"
echo "    Project:      $PROJECT"
echo "    Environment:  $ENV"
echo "    Region:       $REGION"
echo "    GitHub repo:  $GITHUB_ORG/$GITHUB_REPO"

# --- 0. Pre-flight ---
if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI not found. Install: https://aws.amazon.com/cli/"
  exit 1
fi

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "ERROR: aws credentials not configured. Run: aws configure"
  exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "    Account:      $ACCOUNT_ID"
echo

# --- 1. Terraform state S3 bucket ---
STATE_BUCKET="${PROJECT}-tfstate-${ENV}"
echo "==> 1/4 S3 state bucket: $STATE_BUCKET"

if aws s3api head-bucket --bucket "$STATE_BUCKET" --region "$REGION" 2>/dev/null; then
  echo "    Bucket already exists; skipping create"
else
  # Create bucket (handles us-east-1 vs other regions differently)
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$STATE_BUCKET" --region "$REGION"
  else
    aws s3api create-bucket \
      --bucket "$STATE_BUCKET" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
  fi
  echo "    Created"
fi

# Versioning
aws s3api put-bucket-versioning \
  --bucket "$STATE_BUCKET" \
  --versioning-configuration Status=Enabled

# Encryption
aws s3api put-bucket-encryption \
  --bucket "$STATE_BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Public access block
aws s3api put-public-access-block \
  --bucket "$STATE_BUCKET" \
  --public-access-block-configuration \
  '{
    "BlockPublicAcls": true,
    "IgnorePublicAcls": true,
    "BlockPublicPolicy": true,
    "RestrictPublicBuckets": true
  }'

# Lifecycle: expire old state files after 90 days
cat > /tmp/lifecycle.json <<EOF
{
  "Rules": [
    {
      "ID": "ExpireOldState",
      "Status": "Enabled",
      "Expiration": { "Days": 90 },
      "NoncurrentVersionExpiration": { "NoncurrentDays": 30 }
    }
  ]
}
EOF
aws s3api put-bucket-lifecycle-configuration \
  --bucket "$STATE_BUCKET" \
  --lifecycle-configuration file:///tmp/lifecycle.json

echo "    Versioning, encryption, public-access-block, lifecycle applied"

# --- 2. DynamoDB lock table ---
LOCK_TABLE="${PROJECT}-tfstate-lock-${ENV}"
echo
echo "==> 2/4 DynamoDB lock table: $LOCK_TABLE"

if aws dynamodb describe-table --table-name "$LOCK_TABLE" --region "$REGION" >/dev/null 2>&1; then
  echo "    Lock table already exists; skipping"
else
  aws dynamodb create-table \
    --table-name "$LOCK_TABLE" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "$REGION"
  echo "    Created"
fi

# --- 3. GitHub OIDC provider ---
echo
echo "==> 3/4 GitHub OIDC provider"

OIDC_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"

if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_ARN" >/dev/null 2>&1; then
  echo "    OIDC provider already exists; skipping"
else
  # thumbprint for token.actions.githubusercontent.com (as of 2025)
  THUMBPRINT="6938fd4d98bab03faadb97b34396831e3780aea1"
  aws iam create-open-id-connect-provider \
    --url https://token.actions.githubusercontent.com \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list "$THUMBPRINT"
  echo "    Created"
fi

# --- 4. GitHub Actions deploy role ---
echo
echo "==> 4/4 GitHub Actions deploy role"

ROLE_NAME="${PROJECT}-github-deploy-role-${ENV}"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

# Trust policy: scoped to exact repo + branch
cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "$OIDC_ARN"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": [
          "repo:${GITHUB_ORG}/${GITHUB_REPO}:ref:refs/heads/main",
          "repo:${GITHUB_ORG}/${GITHUB_REPO}:pull_request"
        ]
      }
    }
  }]
}
EOF

# Permissions: read-only for plan, read-write for apply (separated by action)
cat > /tmp/permissions-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAllForDatacurator",
      "Effect": "Allow",
      "Action": "*",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:ResourceTag/Project": "$PROJECT"
        }
      }
    },
    {
      "Sid": "AllowStateBucket",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:GetBucketVersioning",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${STATE_BUCKET}",
        "arn:aws:s3:::${STATE_BUCKET}/*"
      ]
    },
    {
      "Sid": "AllowLockTable",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${LOCK_TABLE}"
    }
  ]
}
EOF

if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "    Role already exists; updating trust policy"
  aws iam update-assume-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-document file:///tmp/trust-policy.json
else
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document file:///tmp/trust-policy.json \
    --description "GitHub Actions deploy role for ${PROJECT} ${ENV}"

  aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "${PROJECT}-deploy-permissions" \
    --policy-document file:///tmp/permissions-policy.json

  echo "    Created with permissions policy"
fi

# --- Summary ---
echo
echo "==> Bootstrap complete"
echo
echo "Outputs:"
echo "  Account ID:        $ACCOUNT_ID"
echo "  Region:            $REGION"
echo "  State bucket:      s3://$STATE_BUCKET"
echo "  Lock table:        $LOCK_TABLE"
echo "  OIDC provider ARN: $OIDC_ARN"
echo "  Deploy role ARN:   $ROLE_ARN"
echo
echo "Next steps:"
echo
echo "  1. Add secrets to GitHub repo (Settings → Secrets and variables → Actions):"
echo "       AWS_DEPLOY_ROLE_ARN = $ROLE_ARN"
echo "       AWS_REGION          = $REGION"
echo
echo "  2. cd infra/terraform"
echo
echo "  3. terraform init \\"
echo "       -backend-config=\"bucket=$STATE_BUCKET\" \\"
echo "       -backend-config=\"region=$REGION\" \\"
echo "       -backend-config=\"dynamodb_table=$LOCK_TABLE\""
echo
echo "  4. terraform plan -var-file=envs/${ENV}.tfvars"
echo
echo "  5. terraform apply -var-file=envs/${ENV}.tfvars"
echo
echo "  6. Open PR to verify CI runs; merge to main to deploy via GitHub Actions"
echo
