# ADR-0004: Use GitHub OIDC for AWS authentication; no long-lived AWS keys

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: security, ci-cd

## Context and problem statement

GitHub Actions needs to deploy infrastructure to AWS. The traditional approach is to store long-lived AWS access keys in GitHub repository secrets and use them in workflows.

This has serious security issues:

- **Secret leak risk** — secrets in GitHub can be exfiltrated by malicious PRs, log scrapers, or compromised dependencies
- **Blast radius** — a leaked key is valid for up to 90 days (or until manually rotated)
- **Rotation overhead** — requires manual rotation, easy to forget
- **Auditability** — CloudTrail shows access key ID but not the GitHub context

## Decision drivers

- **Zero static secrets** in GitHub or anywhere
- **Scoped trust** — only this exact repo, on `main` branch, can assume the deploy role
- **Short-lived tokens** (15 min max)
- **Audit trail** — every assume-role call is attributable to a specific commit/PR
- **Public repo safety** — even a public viewer of the repo cannot gain AWS access

## Considered options

### Option 1: Long-lived AWS access keys in GitHub Secrets

- ✅ Simple, well-understood
- ❌ **Critical security risk** if leaked
- ❌ Manual rotation required
- ❌ Repo compromise = AWS compromise

### Option 2: AWS Vault / Chamber / external secret manager

- ✅ Short-lived credentials
- ❌ Adds an external dependency
- ❌ Still requires bootstrapping with long-lived keys
- ❌ Out-of-band setup

### Option 3: GitHub OIDC federation (chosen)

- ✅ **No long-lived secrets anywhere**
- ✅ Short-lived tokens (15 min)
- ✅ Trust policy scoped to exact repo + branch
- ✅ CloudTrail shows `token.actions.githubusercontent.com` as the principal
- ✅ No secret rotation needed
- ⚠️ Requires one-time OIDC provider setup (in `bootstrap.sh`)
- ⚠️ Trust policy must be carefully scoped

## Decision outcome

**Chosen option 3: GitHub OIDC with `sub` claim scoped to `repo:vijaymadhu/datacurator-meta:ref:refs/heads/main` and `repo:vijaymadhu/datacurator-meta:pull_request`.**

The bootstrap script (`scripts/bootstrap.sh`) creates:

1. The OIDC provider (`arn:aws:iam::*:oidc-provider/token.actions.githubusercontent.com`)
2. An IAM role with a trust policy that **only** allows token subjects matching this exact repo + branch

The GitHub Actions workflow (`.github/workflows/apply.yml`) requests a short-lived token via `aws-actions/configure-aws-credentials@v4` with `role-to-assume` and `oidc-token-file-path` (the latter for pull_request builds).

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::ACCOUNT:oidc-provider/token.actions.githubusercontent.com" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": [
          "repo:vijaymadhu/datacurator-meta:ref:refs/heads/main",
          "repo:vijaymadhu/datacurator-meta:pull_request"
        ]
      }
    }
  }]
}
```

### Consequences

**Positive**

- No secrets in GitHub, ever
- Public repo viewers cannot gain AWS access
- Compromised GitHub PAT → still cannot assume the role (different principal)
- Compromised PR from a fork → can only run `plan` (read-only), not `apply`
- CloudTrail audit shows the exact commit SHA that triggered each deployment
- Eliminates the "did I rotate the keys this quarter?" risk

**Negative**

- One-time setup complexity (bootstrap script handles this)
- Trust policy mistakes can over-scope access — mitigated by `tflint`/`tfsec` and PR review
- Requires GitHub to remain operational (acceptable; we already depend on it)

### Confirmation

- `git log` of secrets: zero matches
- `aws sts assume-role-with-web-identity` from a non-trusted principal returns `AccessDenied`
- CloudTrail shows all deploy activity attributed to `token.actions.githubusercontent.com` with full `sub` claim

## Pros and cons of the options

| Option | Secrets in repo | Rotation | Audit | Trust scope | Setup complexity |
| --- | --- | --- | --- | --- | --- |
| Long-lived keys | ❌ Yes | Manual | Key ID only | All | Low |
| AWS Vault | ✅ None | Auto | Session only | All | Medium |
| **GitHub OIDC** | **✅ None** | **Auto** | **Full context** | **Repo + branch** | **Medium** |

## References

- [GitHub Actions — Configuring OpenID Connect in Amazon Web Services](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [aws-actions/configure-aws-credentials](https://github.com/aws-actions/configure-aws-credentials)
- [AWS IAM — Web identity federation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_oidc.html)
