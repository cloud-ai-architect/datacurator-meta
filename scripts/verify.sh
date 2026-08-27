#!/usr/bin/env bash
# scripts/verify.sh
# ------------------------------------------------------------------------------
# DataCurator — Post-deploy health check.
# Runs a series of read-only AWS API calls to verify the stack is healthy.
# Exits non-zero if any check fails.
# ------------------------------------------------------------------------------
set -euo pipefail

ENV="${1:-dev}"
REGION="${2:-ap-south-1}"
PROJECT="${PROJECT:-datacurator}"

PASS=0
FAIL=0

check() {
  local desc="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "  ✓ $desc"
    PASS=$((PASS+1))
  else
    echo "  ✗ $desc"
    FAIL=$((FAIL+1))
  fi
}

echo "==> DataCurator health check (env=$ENV region=$REGION)"
echo

echo "Storage:"
check "Raw bucket exists" \
  aws s3api head-bucket --bucket "${PROJECT}-raw-${ENV}" --region "$REGION"
check "Vectors bucket exists" \
  aws s3api head-bucket --bucket "${PROJECT}-vectors-${ENV}" --region "$REGION"
check "UI bucket exists" \
  aws s3api head-bucket --bucket "${PROJECT}-ui-${ENV}" --region "$REGION"

check "chunk-metadata table" \
  aws dynamodb describe-table --table-name "${PROJECT}-chunk-metadata-${ENV}" --region "$REGION"
check "feedback table" \
  aws dynamodb describe-table --table-name "${PROJECT}-feedback-${ENV}" --region "$REGION"
check "jobs table" \
  aws dynamodb describe-table --table-name "${PROJECT}-jobs-${ENV}" --region "$REGION"

echo
echo "Compute:"
check "Step Function exists" \
  aws stepfunctions list-state-machines --region "$REGION"

echo
echo "API:"
check "API Gateway exists" \
  aws apigatewayv2 get-apis --region "$REGION"

echo
echo "Bedrock:"
check "Titan Embed v2 model accessible" \
  aws bedrock get-foundation-model \
    --model-id "amazon.titan-embed-text-v2:0" \
    --region "$REGION"

echo
echo "IAM:"
check "GitHub OIDC provider exists" \
  aws iam get-open-id-connect-provider \
    --open-id-connect-provider-arn \
    "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):oidc-provider/token.actions.githubusercontent.com"

echo
echo "==> ${PASS} passed, ${FAIL} failed"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
