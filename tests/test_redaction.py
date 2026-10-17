"""Tests for redaction module."""

import pytest

from pipeline_doctor.redaction import SecretRedactor, SizeLimiter


def test_redact_github_tokens():
    """Test redaction of GitHub tokens."""
    redactor = SecretRedactor()

    text = "token: ghp_1234567890abcdefghijklmnopqrstuv123456"
    result = redactor.redact(text)
    assert "ghp_" not in result
    assert "[REDACTED-GITHUB-TOKEN]" in result


def test_redact_aws_keys():
    """Test redaction of AWS keys."""
    redactor = SecretRedactor()

    text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
    result = redactor.redact(text)
    assert "AKIA" not in result
    assert "[REDACTED-AWS-ACCESS-KEY]" in result


def test_redact_bearer_tokens():
    """Test redaction of bearer tokens."""
    redactor = SecretRedactor()

    text = "Authorization: Bearer abc123token456"
    result = redactor.redact(text)
    assert "abc123token456" not in result
    assert "Bearer [REDACTED-TOKEN]" in result


def test_redact_private_keys():
    """Test redaction of private keys."""
    redactor = SecretRedactor()

    text = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890
-----END RSA PRIVATE KEY-----"""
    result = redactor.redact(text)
    assert "MIIEpAIBAAKCAQEA1234567890" not in result
    assert "[REDACTED-PRIVATE-KEY]" in result


def test_redact_password_assignments():
    """Test redaction of password assignments."""
    redactor = SecretRedactor()

    text = 'password="super_secret_123"'
    result = redactor.redact(text)
    assert "[REDACTED]" in result


def test_redact_jwt_tokens():
    """Test redaction of JWT tokens."""
    redactor = SecretRedactor()

    text = "token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    result = redactor.redact(text)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
    assert "[REDACTED-JWT]" in result


def test_redact_add_mask():
    """Test redaction of ::add-mask:: values."""
    redactor = SecretRedactor()

    text = "::add-mask::my_secret_value"
    result = redactor.redact(text)
    assert "my_secret_value" not in result
    assert "::add-mask::[REDACTED]" in result


def test_truncate_log_with_error():
    """Test log truncation keeping context around error."""
    limiter = SizeLimiter(max_log_bytes=500)

    lines = []
    for i in range(100):
        if i == 50:
            lines.append(f"Line {i}: ERROR: Something went wrong")
        else:
            lines.append(f"Line {i}: Normal log line")

    log = "\n".join(lines)
    result = limiter.truncate_log(log, context_lines=5)

    assert "ERROR: Something went wrong" in result
    assert "Line 45" in result
    assert "Line 55" in result


def test_truncate_file():
    """Test file content truncation."""
    limiter = SizeLimiter(max_file_bytes=100)

    content = "x" * 1000
    result = limiter.truncate_file(content)

    assert len(result) < len(content)
    assert "omitted" in result.lower()


def test_no_truncation_when_under_limit():
    """Test no truncation when content is under limit."""
    limiter = SizeLimiter(max_log_bytes=1000)

    log = "Short log"
    result = limiter.truncate_log(log)
    assert result == log


def test_redact_high_entropy_strings():
    """Test redaction of high-entropy strings."""
    redactor = SecretRedactor()

    text = "Key: aB3dE5fG7hI9jK1lM3nO5pQ7rS9tU1vW3xY5zA7bC9dE1fG3hI5jK7lM9"
    result = redactor.redact(text)

    assert result != text


def test_redact_empty_string():
    """Test redaction of empty string."""
    redactor = SecretRedactor()
    result = redactor.redact("")
    assert result == ""
