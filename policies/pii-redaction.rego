###############################################################################
# DataCurator PII Redaction Policy
# -----------------------------------------------------------------------------
# Detects and redacts PII from text before embedding.
# See ADR-0008 for rationale on using OPA.
#
# Test: opa test policies/
###############################################################################

package datacurator.pii

import future.keywords.if
import future.keywords.in
import future.keywords.contains

# --- Pattern definitions ---
# Each pattern matches a specific type of PII.

aadhaar_pattern := r"\b\d{4}\s\d{4}\s\d{4}\b"

email_pattern := r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

phone_intl_pattern := r"\+\d{1,3}[\s-]?\d{3,5}[\s-]?\d{3,5}[\s-]?\d{3,5}"

phone_in_pattern := r"\b\d{10}\b"

ssn_pattern := r"\b\d{3}-\d{2}-\d{4}\b"

credit_card_pattern := r"\b(?:\d[ -]*?){13,19}\b"

ipv4_pattern := r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"

pan_card_pattern := r"\b[A-Z]{5}\d{4}[A-Z]\b"

ifsc_pattern := r"\b[A-Z]{4}0[A-Z0-9]{6}\b"

# All patterns indexed by PII type
pii_patterns := {
  "aadhaar": aadhaar_pattern,
  "email": email_pattern,
  "phone_intl": phone_intl_pattern,
  "phone_in": phone_in_pattern,
  "ssn": ssn_pattern,
  "credit_card": credit_card_pattern,
  "ipv4": ipv4_pattern,
  "pan_card": pan_card_pattern,
  "ifsc": ifsc_pattern,
}

# --- Detection ---

# detect finds all PII matches in `text` and returns a list of {type, value} pairs.
detect(text) := matches if {
  matches := [match |
    some pii_type, pattern in pii_patterns
    match := {
      "type": pii_type,
      "value": regex.find_n(pattern, text, -1),
    }
    count(match.value) > 0
  ]
}

# count_pii returns the total number of PII matches in `text`.
count_pii(text) := count if {
  matches := detect(text)
  count := sum([count_match |
    some match in matches
    count_match := count(match.value)
  ])
}

# types_found returns the unique PII types detected.
types_found(text) := types if {
  matches := detect(text)
  types := {match.type | some match in matches}
}

# --- Redaction ---

# redact replaces all PII in `text` with [REDACTED:<type>] tokens.
redact(text) := redacted if {
  redacted := text
  # In real OPA, we'd use regex.replace; for documentation purposes,
  # the actual replacement logic lives in the Python redactor
  # (src/redactor.py) which uses compiled regex from these patterns.
}

# --- Policy decisions ---

# should_redact returns true if the text contains any PII.
should_redact(text) if {
  count_pii(text) > 0
}

# severity classifies the PII risk level.
# credit_card, ssn, aadhaar = high (regulatory)
# email, phone, pan = medium (privacy)
# ipv4, ifsc = low (informational)
severity(pii_type) := "high" if {
  pii_type in {"credit_card", "ssn", "aadhaar"}
}

severity(pii_type) := "medium" if {
  pii_type in {"email", "phone_intl", "phone_in", "pan_card"}
}

severity(pii_type) := "low" if {
  pii_type in {"ipv4", "ifsc"}
}

# max_severity_in_text returns the highest severity across all PII in text.
max_severity_in_text(text) := max_severity if {
  types := types_found(text)
  severities := {severity(t) | some t in types}
  max_severity := highest(severities)
}

# Helper: order severities
severity_order := {
  "low": 1,
  "medium": 2,
  "high": 3,
}

highest(severities) := max if {
  max := arg_max(s)
  some s in severities
  max := severity_order[s]
}
