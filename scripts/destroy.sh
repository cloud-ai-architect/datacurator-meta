#!/usr/bin/env bash
# scripts/destroy.sh
# ------------------------------------------------------------------------------
# DataCurator — Tear down all resources for a given environment.
#
# WARNING: This is destructive. All data, vectors, metadata, and feedback
# in the target environment will be lost.
#
# Usage:
#   bash scripts/destroy.sh [ENV] [REGION]
#
# Requires:
#   - AWS credentials with admin access
#   - terraform already initialized
# ------------------------------------------------------------------------------
set -euo pipefail

ENV="${1:-dev}"
REGION="${2:-ap-south-1}"
PROJECT="${PROJECT:-datacurator}"

echo "==> DataCurator destroy"
echo "    Project:      $PROJECT"
echo "    Environment:  $ENV"
echo "    Region:       $REGION"
echo
echo "WARNING: This will delete:"
echo "  - All S3 buckets and vectors in this env"
echo "  - All DynamoDB tables in this env"
echo "  - All Lambda functions in this env"
echo "  - Step Function state machine"
echo "  - API Gateway, CloudFront, EventBridge"
echo "  - IAM roles (GitHub deploy role is PRESERVED)"
echo "  - Terraform state bucket contents (preserved, but emptied by TF)"
echo
echo "The following are PRESERVED:"
echo "  - GitHub OIDC provider"
echo "  - GitHub Actions deploy IAM role"
echo "  - Terraform state S3 bucket (empty after run)"
echo "  - DynamoDB lock table"
echo
read -p "Type 'destroy-${ENV}' to confirm: " CONFIRM

if [ "$CONFIRM" != "destroy-${ENV}" ]; then
  echo "Aborted."
  exit 1
fi

cd "$(dirname "$0")/../infra/terraform"

echo
echo "==> terraform destroy"
terraform destroy \
  -var-file="envs/${ENV}.tfvars" \
  -auto-approve

echo
echo "==> Done. State bucket and OIDC provider left in place for reuse."
