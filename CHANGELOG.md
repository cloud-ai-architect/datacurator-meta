# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial project scaffold
- README, LICENSE (Apache 2.0), SECURITY.md, CONTRIBUTING.md
- Pre-commit hooks (gitleaks, ruff, mypy, terraform fmt/lint/sec, markdownlint)
- GitHub Actions workflows (CI, plan, apply)
- OPA Rego policies for PII redaction
- Terraform modules for raw bucket, vectors bucket, UI bucket, DynamoDB, Lambdas, Step Function, EventBridge, API Gateway, CloudFront, IAM, Resource Group
- Python source: detect, parsers (PDF/CSV/JSON), chunker, redactor, embedder, classifier
- Step Function orchestration
- KB UI (rich version: search, filters, bulk feedback, viz, analytics)
- Bootstrap script for new-account deployment
- Synthetic data generator
- Architecture Decision Records (9 ADRs)
- Architecture docs (HLD, LLD, component, dataflow, deployment, security, cost)
- Runbooks (deploy, rollback, incident response, cost investigation)

### Security

- GitHub OIDC for AWS authentication (no long-lived credentials)
- Gitleaks pre-commit and CI secret-scanning
- Branch protection on `main` (required reviews, no force-push)
- Dependabot weekly updates
- All resources tagged `Project=datacurator` for IAM scoping

[Unreleased]: https://github.com/vijaymadhu/datacurator-meta/compare/main...HEAD
