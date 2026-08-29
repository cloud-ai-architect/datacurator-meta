# Cost Investigation Runbook

## Purpose

Step-by-step procedure to investigate a cost spike or unexpected charge. Use this when an AWS bill is higher than expected, or when a budget alarm fires.

## First 5 minutes

```bash
# 1. Check Cost Explorer for the current month
# Open: https://console.aws.amazon.com/cost-management/home

# 2. Check if any budget alarms fired
aws budgets describe-budgets --account-id $(aws sts get-caller-identity --query Account --output text)

# 3. Get a quick breakdown by service for the last 7 days
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query "ResultsByTime[*].Groups[?Metrics.UnblendedCost.Amount>\`10\`]"
```

## Common cost spikes and fixes

### S3 Vectors / S3 storage growing

**Symptom**: S3 bill increases steadily.

**Diagnostic**:

```bash
# List bucket sizes
for bucket in datacurator-raw-dev datacurator-vectors-dev datacurator-ui-dev; do
  echo "=== $bucket ==="
  aws s3 ls s3://$bucket --recursive --summarize | tail -2
done
```

**Common causes**:

| Cause | Fix |
| --- | --- |
| Raw bucket not lifecycle-expiring | Verify `lifecycle_rule` in Terraform |
| Vector index growing unbounded | Add filter to chunker to drop low-value chunks |
| Old test data never deleted | Manually purge via `aws s3 rm --recursive` |

### Lambda runaway

**Symptom**: Lambda bill spikes; thousands of invocations.

**Diagnostic**:

```bash
# Get Lambda invocation metrics for last 24h
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=datacurator-embed-dev \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

**Common causes**:

| Cause | Fix |
|---|---|

| Bug in code creates infinite loop | Patch code, redeploy |
| Recursive S3 trigger (Lambda → S3 → Lambda) | Add `event_source_filter` or check `requestId` |
| Test script left running | Kill the script |

**Fix**:

```bash
# Throttle the Lambda concurrency
aws lambda put-function-concurrency \
  --function-name datacurator-embed-dev \
  --reserved-concurrent-executions 5 \
  --region ap-south-1
```

### Bedrock spike

**Symptom**: Bedrock line item dominates the bill.

**Diagnostic**:

```bash
# Check Bedrock usage in Cost Explorer
# Group by UsageType
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=USAGE_TYPE \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon Bedrock"]}}'
```

**Common causes**:

| Cause | Fix |
| --- | --- |
| Large batch re-embedding | Wait for batch to finish; or cancel and reduce |
| Classification model too expensive (Claude Sonnet) | Switch to Haiku for non-critical |
| Token count much higher than expected | Check chunker config |

### DynamoDB throughput

**Symptom**: DynamoDB line item high.

**Diagnostic**:

```bash
# Check consumed WCU/RCU
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedWriteCapacityUnits \
  --dimensions Name=TableName,Value=datacurator-chunk-metadata-dev \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

**Common causes**:

| Cause | Fix |
| --- | --- |
| Hot partition key (sequential UUIDs are fine; timestamp-based is bad) | Switch PK to UUID |
| Scan instead of query | Add GSI; use Query |
| No TTL on items | Enable TTL |

### CloudWatch logs

**Symptom**: CloudWatch Logs line item higher than expected.

**Diagnostic**:

```bash
# Find log groups by size
aws logs describe-log-groups \
  --query "logGroups[?storedBytes>\`100000000\`].[logGroupName,storedBytes]" \
  --output table
```

**Common causes**:

| Cause | Fix |
| --- | --- |
| Lambda logging full payload | Add `print` filter to remove sensitive fields |
| Log retention too long | Reduce to 30 days |
| Verbose logging in production | Set `LOG_LEVEL=WARN` in prod |

## Cost reduction techniques

### Quick wins (no code change)

1. **S3 lifecycle policy** — auto-expire raw files after 30 days
2. **CloudWatch log retention** — set to 30 days (not "Never expire")
3. **Lambda concurrency limits** — prevent runaway cost
4. **Budget alarms** — already set at $5/$20/$50
5. **S3 Intelligent-Tiering** — for raw bucket

### Medium effort (some code change)

1. **Batch Bedrock calls** — up to 25 chunks per call
2. **Cache embeddings** — if same text appears multiple times
3. **Switch to Haiku 4.5** for non-critical classification
4. **DynamoDB TTL** on all tables

### Bigger changes (architectural)

1. **Reserved capacity** for predictable traffic
2. **S3 Vectors tiered storage** (when available)
3. **Provisioned concurrency** for high-traffic Lambdas

## Cost allocation tags

Make sure the `Project=datacurator` tag is applied to all resources. The Terraform modules do this automatically, but verify in the AWS Console:

```bash
# Check that all datacurator resources have the tag
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=datacurator \
  --output table
```

If any resources are missing the tag, the IAM policy will deny access to the deploy role — and that's a feature, not a bug. But it would prevent the deploy from working.

## When to escalate

If you find:

- A single resource costing >$100/day unexpectedly
- Unrecognized services in the bill
- Resources in a region you don't use
- A security incident (resources you didn't create)

**Stop the bleeding first**:

```bash
# Disable the runaway Lambda
aws lambda update-function-configuration \
  --function-name datacurator-embed-dev \
  --no-reserved-concurrent-executions 0 \
  --region ap-south-1

# Or delete it entirely
aws lambda delete-function \
  --function-name datacurator-embed-dev \
  --region ap-south-1
```

Then investigate root cause and add guardrails.

## See also

- [Cost model](../architecture/07-cost-model.md) — Expected costs
- [ADR-0002: Use S3 Vectors](../adr/0002-use-s3-vectors-not-opensearch.md) — Why cheap
- [ADR-0003: Use Bedrock Titan v2](../adr/0003-use-bedrock-titan-embed-v2.md) — Why cheap embeddings
- [Deploy runbook](deploy.md) — Forward deploys
- [Incident response runbook](incident-response.md) — Live incidents
