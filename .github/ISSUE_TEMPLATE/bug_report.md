---
name: Bug report
about: Report something that is broken or behaves unexpectedly
title: "[BUG] "
labels: ["bug"]
assignees: []
---

## Describe the bug

A clear and concise description of what the bug is.

## To reproduce

Steps to reproduce the behavior:

1. Deploy with config '...'
2. Upload file '...'
3. Run '...'
4. See error

## Expected behavior

A clear and concise description of what you expected to happen.

## Actual behavior

What actually happened. Include the full error message and stack trace if applicable.

## Environment

- DataCurator version (commit SHA or release tag):
- AWS account ID: (do NOT share, just note region)
- AWS region: (e.g. ap-south-1)
- Deployment method: (terraform apply, manual, CI/CD)
- Python version: (output of `python --version`)
- Terraform version: (output of `terraform --version`)

## Logs

```text
Paste relevant logs here. Mask any account IDs or secrets.
```

## Severity

<!-- How bad is this? -->

- [ ] Critical — production broken, no workaround
- [ ] High — major feature broken, workaround exists
- [ ] Medium — minor feature broken
- [ ] Low — cosmetic / docs / nice-to-have

## Additional context

Any other relevant information (screenshots, related issues, etc.).
