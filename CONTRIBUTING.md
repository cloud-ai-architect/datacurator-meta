# Contributing to DataCurator

Thanks for your interest in contributing! This document covers how to propose changes, report issues, and submit pull requests.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you agree to uphold it.

## How to contribute

### 1. File an issue first

For non-trivial changes (new feature, refactor, breaking change), file an issue describing:
- The problem you're solving
- Your proposed approach
- Alternatives considered
- Acceptance criteria

This avoids duplicate work and surfaces architectural concerns early.

### 2. Fork and branch

```bash
git clone https://github.com/vijaymadhu/datacurator-meta.git
cd datacurator-meta
git checkout -b feat/your-feature-name
```

Branch naming convention:
- `feat/short-description` — new feature
- `fix/short-description` — bug fix
- `docs/short-description` — documentation only
- `chore/short-description` — tooling, dependencies
- `refactor/short-description` — code refactor without behavior change
- `infra/short-description` — Terraform / CI changes

### 3. Make your changes

- Follow the style guides (see below)
- Write tests for new functionality
- Update relevant ADRs and architecture docs
- Sign off your commits (DCO):

```bash
git commit -s -m "feat: add support for Parquet parser"
```

### 4. Pre-commit checks

```bash
# Install hooks (one time)
pip install pre-commit
pre-commit install

# Run all hooks on all files
pre-commit run --all-files
```

Hooks enforce:
- Gitleaks secret scan
- Ruff lint + format
- Mypy type check
- Terraform fmt + validate + tflint + tfsec
- Markdown lint
- YAML lint
- Conventional commit message

### 5. Open a pull request

- Use the [PR template](.github/pull_request_template.md)
- Link related issues
- Include `terraform plan` output (collapsed) for infra changes
- Wait for CI to pass
- Address review feedback

## Style guides

### Python

- **Format**: `ruff format`
- **Lint**: `ruff check` (config in `pyproject.toml`)
- **Types**: `mypy --strict`
- **Tests**: `pytest`, ≥85% coverage required
- **Docstrings**: Google style

### Terraform

- **Format**: `terraform fmt -recursive`
- **Validate**: `terraform validate`
- **Lint**: `tflint`
- **Security**: `tfsec` (config in `.tfsec/`)
- **Docs**: `terraform-docs` auto-generates module READMEs

### Markdown

- **Lint**: `markdownlint` (config in `.markdownlint.json`)
- **Diagrams**: Mermaid (rendered automatically by GitHub)
- **ADRs**: MADR format (template in `docs/adr/template.md`)

### Rego

- **Test**: `opa test policies/`
- **Format**: `opa fmt policies/`

## Architecture decisions

Significant changes (new service, new dependency, breaking API change) **require an ADR** in `docs/adr/`:

1. Copy `docs/adr/template.md` to `docs/adr/NNNN-short-title.md`
2. Fill in all sections: Context, Decision, Consequences, Alternatives
3. Submit the ADR in the same PR as the code change
4. Discuss in the PR review

## Reporting bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md). Include reproduction steps, environment, and logs.

## License

By contributing, you agree that your contributions will be licensed under the [Apache 2.0 License](LICENSE).
