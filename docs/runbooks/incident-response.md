# Incident Response Runbook

## Purpose

When something is broken **right now** and the KB UI is down, the pipeline is failing, or AWS is rejecting requests, this is the runbook. It prioritizes **fast detection, fast mitigation, post-mortem later**.

## Severity levels

| Level | Impact | Response time | Examples |
|---|---|---|---|
| **SEV-1** | Total outage | < 15 min | All pipeline runs failing; KB UI down |
| **SEV-2** | Degraded | < 1 hour | > 50% pipeline runs failing; search broken |
| **SEV-3** | Minor | < 4 hours | < 10% of runs failing; specific format not parsing |
| **SEV-4** | Cosmetic | < 1 week | Doc typo, minor UX issue |

## First 60 seconds

```mermaid
flowchart TD
    A[Page received] --> B{What's broken?}
    B -->|Pipeline| C[Check Step Function executions]
    B -->|Search/UI| D[Check API Gateway + CloudFront]
    B -->|Embeddings| E[Check Bedrock availability]
    B -->|AWS auth| F[Check IAM role + OIDC]

    C --> G[CloudWatch logs]
    D --> G
    E --> G
    F --> G

    G --> H{Failed at known stage?}
    H -->|Yes| I[See "Common errors" below]
    H -->|No| J[Page on-call / file sev-1]
```

## Common errors and fixes

### Pipeline failing in `Detect` stage

**Symptom**: Step Function execution status `FAILED`, error in `Detect` state.

**Diagnostic**:
```bash
# Get the failed execution
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:ap-south-1:ACCOUNT:stateMachine:datacurator-pipeline-dev \
  --status-filter FAILED \
  --max-items 1 \
  --region ap-south-1

# Get the failure event
aws stepfunctions get-execution-history \
  --execution-arn <exec-arn> \
  --region ap-south-1

# Check CloudWatch logs
aws logs tail /aws/lambda/datacurator-detect-dev --follow
```

**Common causes**:

| Error message | Cause | Fix |
|---|---|---|
| `AccessDenied` on `s3:GetObject` | IAM role missing S3 read | Re-apply Terraform |
| `NoSuchKey` | File removed before pipeline ran | Re-upload |
| `ThrottlingException` | Too many concurrent runs | Raise concurrency limit |
| `Lambda timeout` | File too large | Increase Lambda timeout to 5 min |

### Pipeline failing in `Embed` stage

**Symptom**: Job succeeds through Redact but fails at Embed.

**Diagnostic**:
```bash
aws logs tail /aws/lambda/datacurator-embed-dev --follow
```

**Common causes**:

| Error message | Cause | Fix |
|---|---|---|
| `AccessDeniedException` on Bedrock | Model access not enabled in console | Enable in Bedrock console |
| `ThrottlingException` | Bedrock rate limit | Reduce batch size, add backoff |
| `ValidationException: input too long` | Chunk > 25K chars | Reduce chunk size in config |
| `ModelTimeout` | Bedrock unavailable | Retry; check AWS status |

### KB UI shows "search failed"

**Symptom**: UI loads, but search returns 500.

**Diagnostic**:
```bash
# Check API Gateway logs
aws logs tail /aws/vendedlogs/apigateway/datacurator-api-dev --follow

# Check search-lambda logs
aws logs tail /aws/lambda/datacurator-search-dev --follow
```

**Common causes**:

| Error message | Cause | Fix |
|---|---|---|
| `AccessDeniedException` on `s3vectors:QueryVectors` | IAM missing S3 Vectors perm | Re-apply Terraform |
| `IndexNotFoundException` | Vector index deleted | Re-run `terraform apply` |
| `ServiceUnavailable` on Bedrock | Bedrock down | Wait for AWS to recover |
| `CORS error` in browser | API Gateway CORS misconfigured | Check Terraform `cors` config |

### KB UI completely down

**Symptom**: Browser shows 403, 502, or 504.

**Diagnostic**:
```bash
# Check CloudFront
aws cloudfront get-distribution --id <distribution-id>

# Check S3 UI bucket
aws s3 ls s3://datacurator-ui-dev/static/

# Check CloudFront error rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/CloudFront \
  --metric-name 4xxErrorRate \
  --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum
```

**Common causes**:

| Error | Cause | Fix |
|---|---|---|
| 403 Forbidden | CloudFront OAC misconfigured | Re-apply Terraform; wait 5 min for CF propagation |
| 502 Bad Gateway | S3 bucket policy denies CF | Re-apply Terraform |
| 504 Gateway Timeout | Origin (S3) slow | Check S3 health |

### GitHub Actions deploy fails

**Symptom**: Apply workflow fails with AWS error.

**Diagnostic**:
- Check the Actions tab for the failed run
- Look at the `terraform apply` step output
- Most common: `sts:AssumeRoleWithWebIdentity` fails

**Common causes**:

| Error | Cause | Fix |
|---|---|---|
| `Not authorized to perform sts:AssumeRoleWithWebIdentity` | OIDC trust policy mismatch | Re-run bootstrap, check sub-claim |
| `Error: getting data.aws_caller_identity` | Wrong credentials in workflow | Check secrets |
| `Error acquiring the state lock` | Stuck lock | Manually delete lock in DynamoDB console |

## Escalation

If you've spent 15 minutes and the issue is unresolved:

1. **Page on-call** (when applicable — for solo side-project, this is you)
2. **Open a SEV-1 incident** in the issue tracker
3. **Consider rolling back** — see [rollback runbook](rollback.md)
4. **Communicate** — post status updates in chat every 30 min

## Post-incident

Within 48 hours of resolution:

1. **Write a post-mortem** — even for SEV-3
2. **Add regression test** — to prevent recurrence
3. **Add an alarm** — to detect faster next time
4. **Update the runbook** — if the runbook was wrong

## Useful one-liners

```bash
# Find all failed executions in the last hour
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:ap-south-1:ACCOUNT:stateMachine:datacurator-pipeline-dev \
  --status-filter FAILED \
  --region ap-south-1 \
  --query "executions[?startDate>=\`$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)\`]"

# Tail all Lambda logs at once
for fn in detect parse chunk redact embed classify route search feedback; do
  aws logs tail "/aws/lambda/datacurator-${fn}-dev" --follow --region ap-south-1 &
done

# Get current Bedrock service health
aws health describe-events \
  --filter services=BEDROCK \
  --region us-east-1
```

## See also

- [Deploy runbook](deploy.md) — Forward deploys
- [Rollback runbook](rollback.md) — Recovery
- [Cost investigation runbook](cost-investigation.md) — For cost spikes
- [Security model](../architecture/06-security-model.md) — For security incidents
