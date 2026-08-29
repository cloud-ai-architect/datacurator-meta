###############################################################################
# Tests for the PII redaction policy.
# Run: opa test policies/ -v
###############################################################################

package datacurator.pii

# Enables the v1 keywords (if, in, contains) on OPA 0.59+, and is the
# default in OPA 1.x. Without it these files parse under v0 rules and
# every `test_x if { ... }` fails with "var cannot be used for rule name".
import rego.v1

# --- count_pii ---

test_count_email if {
  count_pii("Contact me at john@example.com") == 1
}

test_count_phone if {
  count_pii("Call +1 555 123 4567") >= 1
}

test_count_aadhaar if {
  count_pii("My Aadhaar is 1234 5678 9012") == 1
}

test_count_multiple if {
  count_pii("Email a@b.com or call 1234567890") >= 2
}

test_count_none if {
  count_pii("Hello world") == 0
}

# --- types_found ---

test_types_email if {
  "email" in types_found("Contact me at john@example.com")
}

test_types_aadhaar if {
  "aadhaar" in types_found("My Aadhaar is 1234 5678 9012")
}

test_types_multiple if {
  types := types_found("a@b.com and 1234 5678 9012")
  "email" in types
  "aadhaar" in types
}

test_types_none if {
  count(types_found("Hello world")) == 0
}

# --- should_redact ---

test_should_redact_true if {
  should_redact("My email is a@b.com")
}

test_should_redact_false if {
  not should_redact("Nothing sensitive here")
}

# --- severity ---

test_severity_high_credit_card if {
  severity("credit_card") == "high"
}

test_severity_high_aadhaar if {
  severity("aadhaar") == "high"
}

test_severity_medium_email if {
  severity("email") == "medium"
}

test_severity_low_ipv4 if {
  severity("ipv4") == "low"
}

# --- max_severity_in_text ---

test_max_severity_aadhaar if {
  max_severity_in_text("My Aadhaar is 1234 5678 9012") == "high"
}

test_max_severity_email if {
  max_severity_in_text("Email me at a@b.com") == "medium"
}

test_max_severity_ip if {
  max_severity_in_text("Server IP is 10.0.0.1") == "low"
}

test_max_severity_mixed if {
  max_severity_in_text("Email a@b.com, IP 10.0.0.1, Aadhaar 1234 5678 9012") == "high"
}

# --- detect ---

test_detect_finds_email if {
  matches := detect("Contact john@example.com today")
  some match in matches
  match.type == "email"
  "john@example.com" in match.value
}

test_detect_no_match if {
  count(detect("Nothing here")) == 0
}
