"""Secret redaction and size limiting for logs and text."""

import re
from typing import List, Optional


class SecretRedactor:
    """Redacts secrets from logs and text."""

    PATTERNS = [
        (r"ghp_[a-zA-Z0-9]{36}", "[REDACTED-GITHUB-TOKEN]"),
        (r"gho_[a-zA-Z0-9]{36}", "[REDACTED-GITHUB-OAUTH-TOKEN]"),
        (r"ghs_[a-zA-Z0-9]{36}", "[REDACTED-GITHUB-SERVER-TOKEN]"),
        (r"github_pat_[a-zA-Z0-9_]{82}", "[REDACTED-GITHUB-PAT]"),
        (r"AKIA[0-9A-Z]{16}", "[REDACTED-AWS-ACCESS-KEY]"),
        (r"(?i)aws_secret_access_key['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9/+=]{40})", "[REDACTED-AWS-SECRET-KEY]"),
        (r"Bearer\s+[a-zA-Z0-9\-._~+/]+=*", "Bearer [REDACTED-TOKEN]"),
        (r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(?:RSA\s+)?PRIVATE\s+KEY-----", "[REDACTED-PRIVATE-KEY]"),
        (r"(?i)(?:password|token|secret|api_key|apikey)['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};:,.<>?]{8,})['\"]?", r"\g<0>[REDACTED]"),
        (r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*", "[REDACTED-JWT]"),
        (r"::add-mask::(.*?)(?:\n|$)", r"::add-mask::[REDACTED]\n"),
    ]

    HIGH_ENTROPY_PATTERN = re.compile(r"(?:[A-Za-z0-9+/]{40,}|[A-Za-z0-9_-]{40,})")

    def __init__(self):
        self.compiled_patterns = [(re.compile(pattern), replacement) for pattern, replacement in self.PATTERNS]

    def redact(self, text: str) -> str:
        """
        Redact secrets from text.

        Args:
            text: Input text potentially containing secrets

        Returns:
            Text with secrets redacted
        """
        if not text:
            return text

        result = text
        for pattern, replacement in self.compiled_patterns:
            result = pattern.sub(replacement, result)

        result = self._redact_high_entropy(result)

        return result

    def _redact_high_entropy(self, text: str) -> str:
        """
        Redact high-entropy strings that might be credentials.

        Args:
            text: Input text

        Returns:
            Text with high-entropy strings redacted
        """

        def entropy(s: str) -> float:
            """Calculate Shannon entropy of a string."""
            if not s:
                return 0.0
            from collections import Counter
            from math import log2

            length = len(s)
            counts = Counter(s)
            return -sum(count / length * log2(count / length) for count in counts.values())

        def should_redact(match: re.Match) -> str:
            candidate = match.group(0)
            if len(candidate) >= 40 and entropy(candidate) > 4.5:
                return "[REDACTED-HIGH-ENTROPY]"
            return candidate

        return self.HIGH_ENTROPY_PATTERN.sub(should_redact, text)


class SizeLimiter:
    """Limits size of logs and files."""

    def __init__(
        self,
        max_log_bytes: int = 100_000,
        max_file_bytes: int = 50_000,
        max_files: int = 20,
        max_api_requests: int = 50,
    ):
        """
        Initialize size limiter.

        Args:
            max_log_bytes: Maximum bytes per log excerpt
            max_file_bytes: Maximum bytes per source file
            max_files: Maximum number of files to fetch
            max_api_requests: Maximum API requests to make
        """
        self.max_log_bytes = max_log_bytes
        self.max_file_bytes = max_file_bytes
        self.max_files = max_files
        self.max_api_requests = max_api_requests

    def truncate_log(self, log_text: str, context_lines: int = 20) -> str:
        """
        Truncate log keeping head and tail around first error.

        Args:
            log_text: Full log text
            context_lines: Number of lines to keep before/after error

        Returns:
            Truncated log
        """
        if len(log_text) <= self.max_log_bytes:
            return log_text

        lines = log_text.split("\n")

        error_patterns = [
            re.compile(r"(?i)error[:|\s]", re.IGNORECASE),
            re.compile(r"(?i)failed", re.IGNORECASE),
            re.compile(r"(?i)exception", re.IGNORECASE),
            re.compile(r"(?i)traceback", re.IGNORECASE),
        ]

        error_line_idx = None
        for idx, line in enumerate(lines):
            if any(pattern.search(line) for pattern in error_patterns):
                error_line_idx = idx
                break

        if error_line_idx is not None:
            start_idx = max(0, error_line_idx - context_lines)
            end_idx = min(len(lines), error_line_idx + context_lines + 1)

            head = lines[:10] if start_idx > 10 else []
            middle = lines[start_idx:end_idx]
            tail = lines[-10:] if end_idx < len(lines) - 10 else []

            truncated_lines = []
            if head:
                truncated_lines.extend(head)
                truncated_lines.append(f"... [{start_idx - 10} lines omitted] ...")
            truncated_lines.extend(middle)
            if tail and end_idx < len(lines) - 10:
                truncated_lines.append(f"... [{len(lines) - 10 - end_idx} lines omitted] ...")
                truncated_lines.extend(tail)

            return "\n".join(truncated_lines)

        head_bytes = self.max_log_bytes // 2
        tail_bytes = self.max_log_bytes // 2

        head = log_text[:head_bytes]
        tail = log_text[-tail_bytes:]

        omitted = len(log_text) - head_bytes - tail_bytes
        return f"{head}\n... [{omitted} bytes omitted] ...\n{tail}"

    def truncate_file(self, file_content: str) -> str:
        """
        Truncate file content if too large.

        Args:
            file_content: Full file content

        Returns:
            Truncated content
        """
        if len(file_content) <= self.max_file_bytes:
            return file_content

        head_bytes = self.max_file_bytes // 2
        tail_bytes = self.max_file_bytes // 2

        head = file_content[:head_bytes]
        tail = file_content[-tail_bytes:]

        omitted = len(file_content) - head_bytes - tail_bytes
        return f"{head}\n... [{omitted} bytes omitted] ...\n{tail}"


def create_redactor() -> SecretRedactor:
    """Factory function to create a secret redactor."""
    return SecretRedactor()


def create_limiter(
    max_log_bytes: int = 100_000,
    max_file_bytes: int = 50_000,
    max_files: int = 20,
    max_api_requests: int = 50,
) -> SizeLimiter:
    """
    Factory function to create a size limiter.

    Args:
        max_log_bytes: Maximum bytes per log excerpt
        max_file_bytes: Maximum bytes per source file
        max_files: Maximum number of files to fetch
        max_api_requests: Maximum API requests to make

    Returns:
        Configured size limiter
    """
    return SizeLimiter(
        max_log_bytes=max_log_bytes,
        max_file_bytes=max_file_bytes,
        max_files=max_files,
        max_api_requests=max_api_requests,
    )
