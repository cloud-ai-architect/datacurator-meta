<!--
Thanks for contributing to DataCurator!

Please complete the sections below. This template is enforced; PRs without
context may be asked for revisions before review.

If your PR is purely documentation (typos, clarity), you may delete sections
that don't apply.
-->

## Summary

<!-- One or two sentences: what does this PR do and why? -->

## Type of change

<!-- Check all that apply -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that changes existing behavior)
- [ ] Infrastructure / Terraform change
- [ ] Documentation only
- [ ] Refactor (no functional change)
- [ ] Test improvement

## Related issues

<!-- Link related issues: Fixes #123, Relates to #456 -->

## Architectural impact

<!--
If your change affects architecture, security, cost, or operations, explain here.
For Terraform changes: paste the output of `terraform plan` (collapsed) and
explain any resource creations/deletions/modifications.
For security-sensitive changes: explain the threat model impact.
For cost-sensitive changes: estimate monthly impact.
-->

## How has this been tested?

<!-- Describe the tests you ran and the results. -->

- [ ] Unit tests pass locally (`pytest tests/unit`)
- [ ] Integration tests pass locally (if applicable)
- [ ] Manual testing performed
- [ ] Terraform `plan` reviewed (if applicable)

## Security checklist

<!-- Reviewer will verify these, but the author should self-attest. -->

- [ ] No secrets, API keys, or account IDs added to the codebase
- [ ] No new IAM permissions beyond least-privilege
- [ ] No new public S3 buckets, public APIs, or publicly accessible resources
- [ ] Pre-commit hooks pass (`pre-commit run --all-files`)
- [ ] Gitleaks passes
- [ ] Terraform security scan passes (tfsec / checkov)

## Cost impact

<!-- Estimated monthly cost change: +$X / -$X / no change -->

## Checklist

- [ ] My code follows the project's style (`ruff check`, `ruff format`)
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing unit tests pass locally
- [ ] I have updated relevant documentation (ADRs, runbooks, README)
- [ ] My changes generate no new warnings
- [ ] I have signed off my commits (DCO: `git commit -s`)
