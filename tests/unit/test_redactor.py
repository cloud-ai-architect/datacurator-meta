"""Unit tests for the PII redactor."""

from __future__ import annotations

import pytest

from src.redactor import FALLBACK_PATTERNS, POLICY_VERSION


class TestPatterns:
    def test_email_detected(self):
        matches = FALLBACK_PATTERNS["email"].findall("Contact me at john@example.com")
        assert "john@example.com" in matches

    def test_phone_in_detected(self):
        matches = FALLBACK_PATTERNS["phone_in"].findall("Call 9876543210")
        assert "9876543210" in matches

    def test_aadhaar_detected(self):
        matches = FALLBACK_PATTERNS["aadhaar"].findall("My Aadhaar is 1234 5678 9012")
        assert "1234 5678 9012" in matches

    def test_no_pii(self):
        text = "This is a normal sentence with no sensitive data."
        for pattern in FALLBACK_PATTERNS.values():
            assert pattern.findall(text) == []

    def test_ssn_detected(self):
        matches = FALLBACK_PATTERNS["ssn"].findall("SSN: 123-45-6789")
        assert "123-45-6789" in matches

    def test_ipv4_detected(self):
        matches = FALLBACK_PATTERNS["ipv4"].findall("Server IP is 10.0.0.1")
        assert "10.0.0.1" in matches


class TestPolicyVersion:
    def test_version_format(self):
        assert POLICY_VERSION.startswith("pii-redaction-")
        assert "." in POLICY_VERSION
