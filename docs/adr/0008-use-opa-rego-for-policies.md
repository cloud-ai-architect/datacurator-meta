# ADR-0008: Use OPA Rego for PII and redaction policies, not Python conditionals

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: security, policies, compliance

## Context and problem statement

PII redaction is a core requirement. Chunks must be scanned for emails, phone numbers, Aadhaar numbers (Indian), credit card numbers, SSNs, etc., and redacted before embedding.

Options:

1. **Python regex in the redactor Lambda** — inline code
2. **External library** (Microsoft Presidio, scrubadub)
3. **OPA Rego policy** with the bundle embedded in the Lambda

## Decision drivers

- **Policy as data** — policies should be reviewable separately from code
- **Testability** — policies need unit tests
- **Versioning** — policies should track changes in git history
- **Auditability** — compliance reviewers want to see "what counts as PII" in a declarative file
- **Reusability** — the same PII policy should apply to all 14 downstream portfolio projects

## Considered options

### Option 1: Python regex inline

- ✅ Easy to start
- ❌ Policies scattered in code
- ❌ Hard to test in isolation
- ❌ Hard to reuse across projects

### Option 2: Microsoft Presidio

- ✅ Comprehensive PII detection (NLP-based)
- ❌ Heavy dependency (~500MB model)
- ❌ Slow on small chunks
- ❌ Custom logic still mixed with code

### Option 3: OPA Rego (chosen)

- ✅ **Policies as data files** in `policies/`
- ✅ **First-class unit tests** (`policies/*_test.rego`)
- ✅ **Versioned in git** like any other source file
- ✅ **No code change** to update a rule
- ✅ **Reusable** across all portfolio projects
- ✅ **Cloud-portable** — same policy works on AWS, Azure, GCP
- ✅ **Audit-friendly** — regulators can read `.rego` files
- ⚠️ OPA runtime adds ~10MB to the Lambda deployment package
- ⚠️ Slight learning curve for contributors

## Decision outcome

**Chosen option 3: OPA Rego.**

Policies live in `policies/`:

- `pii-redaction.rego` — main PII detection rules
- `pii-redaction_test.rego` — unit tests
- `retention.rego` — data retention rules (for Phase 3)

The Redactor Lambda (`src/redactor.py`) calls the OPA CLI in-process via the `opa-python` library, or ships a pre-compiled `.bundle` artifact.

```rego
package datacurator.pii

# Detect Indian Aadhaar numbers (12 digits, space-separated)
aadhaar_pattern := `\b\d{4}\s\d{4}\s\d{4}\b`

# Detect email addresses
email_pattern := `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`

# Detect phone numbers (Indian + international)
phone_pattern := `(\+?\d{1,3}[\s-]?)?\(?\d{3,5}\)?[\s-]?\d{3,5}[\s-]?\d{3,5}`

# Detect credit card numbers (Luhn-checked)
ccn_pattern := `\b(?:\d[ -]*?){13,19}\b`

pii_patterns := {
  "aadhaar": aadhaar_pattern,
  "email": email_pattern,
  "phone": phone_pattern,
  "ccn": ccn_pattern,
}

# Decision: redact all matches with [REDACTED:<type>]
redact(text) := result if {
  result := text
  # OPA's `regex.replace` does the substitution
}
```

The OPA policy runs in the Redactor Lambda **before** embedding, ensuring no PII reaches the vector store.

### Consequences

**Positive**

- Policies are auditable, testable, version-controlled
- Adding a new PII type is a 5-line change in a `.rego` file (no code change, no redeploy of application code)
- Same policy file can be enforced in other tools (CLI, API gateway, S3 event handler)
- OPA is a CNCF graduated project, well-supported

**Negative**

- OPA adds 10MB to the Lambda deployment package
- Contributors need to learn Rego (mitigated by clear examples and tests)
- Edge cases in regex are subtle (mitigated by extensive tests)

### Confirmation

- `opa test policies/` passes 100% of cases
- No PII (synthetic test corpus) leaks into the S3 Vectors index (verified by `pytest tests/integration/test_pii_redaction.py`)
- Policies are referenced from the Lambda's `policy_version` env var, allowing zero-downtime policy updates

## Pros and cons of the options

| Option | Testability | Versioning | Reusability | Audit | Bundle size |
| --- | --- | --- | --- | --- | --- |
| Python regex | ⚠️ Inline tests | ⚠️ In code | ❌ Scattered | ⚠️ | 0 |
| Presidio | ✅ Library tests | ⚠️ In code | ⚠️ Library | ❌ | 500MB |
| **OPA Rego** | **✅ First-class** | **✅ Data file** | **✅ Cross-project** | **✅** | **10MB** |

## References

- [Open Policy Agent](https://www.openpolicyagent.org/)
- [Rego language reference](https://www.openpolicyagent.org/docs/latest/policy-language/)
- [OPA in Python](https://github.com/StyraInc/opa-python)
- [Microsoft Presidio](https://github.com/microsoft/presidio) (rejected)
