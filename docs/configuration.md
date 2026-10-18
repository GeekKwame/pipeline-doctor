# Configuration

Pipeline Doctor is configured via environment variables and constructor parameters. This document describes all available configuration options.

## Environment Variables

### GitHub Authentication

#### `GITHUB_TOKEN`

**Type**: String  
**Required**: Optional (recommended for production)  
**Default**: `""` (empty string, unauthenticated access)  
**Read by**: `GitHubClient.__init__()`

GitHub personal access token for API authentication.

- **Without token**: Unauthenticated access, 60 requests/hour, job logs may be unavailable
- **With token**: Authenticated access, 5,000 requests/hour, full access to logs

**Permissions required**: See [GitHub Token Setup](github-token.md)

**Example**:
```bash
export GITHUB_TOKEN="ghp_1234567890abcdefghijklmnopqrstuvwxyz12"
```

**Security**: Never commit tokens to version control. Use environment variables or secret management systems.

---

### xAI / Grok Authentication

#### `GROK_API_KEY`

**Type**: String  
**Required**: Yes (for real Grok client)  
**Default**: `None`  
**Read by**: `GrokAPIClient.__init__()`

xAI API key for Grok AI requests.

**Example**:
```bash
export GROK_API_KEY="xai-1234567890abcdefghijklmnopqrstuvwxyz"
```

#### `XAI_API_KEY`

**Type**: String  
**Required**: Alternative to `GROK_API_KEY`  
**Default**: `None`  
**Read by**: `GrokAPIClient.__init__()`

Alternative environment variable name for xAI API key. If both `GROK_API_KEY` and `XAI_API_KEY` are set, `GROK_API_KEY` takes precedence.

**Example**:
```bash
export XAI_API_KEY="xai-1234567890abcdefghijklmnopqrstuvwxyz"
```

**Precedence order**:
1. `api_key` constructor parameter
2. `GROK_API_KEY` environment variable
3. `XAI_API_KEY` environment variable

---

### Grok Model Selection

#### `GROK_MODEL`

**Type**: String  
**Required**: Optional  
**Default**: `"grok-beta"`  
**Read by**: `GrokAPIClient.__init__()`

Model name to use for Grok API requests.

**Example**:
```bash
export GROK_MODEL="grok-2-latest"
```

**⚠️ Warning**: The default model name `"grok-beta"` has NOT been verified against the live xAI API. Check available models with:

```bash
curl -H "Authorization: Bearer $GROK_API_KEY" https://api.x.ai/v1/models
```

---

## Constructor Parameters

### GitHubClient

**Module**: `pipeline_doctor.github_client`

```python
from pipeline_doctor.github_client import GitHubClient

client = GitHubClient(
    token: Optional[str] = None,
    max_requests: int = 50
)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | `Optional[str]` | `None` | GitHub personal access token. Falls back to `GITHUB_TOKEN` env var. |
| `max_requests` | `int` | `50` | Maximum number of API requests to make before raising `GitHubAPIError`. Prevents runaway API usage. Includes redirects. |

#### Example

```python
# Use token from environment variable
client = GitHubClient()

# Explicit token
client = GitHubClient(token="ghp_...")

# Custom request budget
client = GitHubClient(max_requests=100)
```

---

### GrokAPIClient

**Module**: `pipeline_doctor.grok_client`

```python
from pipeline_doctor.grok_client import GrokAPIClient

client = GrokAPIClient(
    api_key: Optional[str] = None,
    base_url: str = "https://api.x.ai/v1",
    model: Optional[str] = None,
    connect_timeout: float = 30.0,
    read_timeout: float = 120.0,
    max_retries: int = 3
)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `Optional[str]` | `None` | xAI API key. Falls back to `GROK_API_KEY` or `XAI_API_KEY` env vars. |
| `base_url` | `str` | `"https://api.x.ai/v1"` | Base URL for xAI API. |
| `model` | `Optional[str]` | `None` | Default model name. Falls back to `GROK_MODEL` env var or `"grok-beta"`. |
| `connect_timeout` | `float` | `30.0` | Connection timeout in seconds. |
| `read_timeout` | `float` | `120.0` | Read timeout in seconds. |
| `max_retries` | `int` | `3` | Maximum retries for 429 (rate limit) and 5xx errors. Uses exponential backoff: 1s, 2s, 4s, 8s, etc. |

#### Example

```python
# Default configuration
client = GrokAPIClient(api_key="xai-...")

# Custom model and timeouts
client = GrokAPIClient(
    api_key="xai-...",
    model="grok-2-latest",
    connect_timeout=10.0,
    read_timeout=60.0
)

# Production configuration with retries
client = GrokAPIClient(
    api_key="xai-...",
    max_retries=5
)
```

#### chat_completion() Parameters

```python
response = client.chat_completion(
    system_prompt: str,
    user_message: str,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
    response_format: Optional[str] = None
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `system_prompt` | `str` | Required | System prompt (role instructions). |
| `user_message` | `str` | Required | User message (evidence to analyze). |
| `model` | `Optional[str]` | `None` | Override default model for this call. |
| `temperature` | `float` | `0.1` | Sampling temperature (0.0 = deterministic, 1.0 = creative). |
| `max_tokens` | `Optional[int]` | `None` | Maximum tokens to generate. If not set, uses API default. |
| `response_format` | `Optional[str]` | `None` | Response format type, e.g., `"json_object"` for JSON mode. |

**⚠️ Warning**: `response_format` and `max_tokens` have NOT been verified against the live xAI API.

---

### SecretRedactor

**Module**: `pipeline_doctor.redaction`

```python
from pipeline_doctor.redaction import SecretRedactor

redactor = SecretRedactor()
```

No configuration parameters. Uses hardcoded patterns for:
- GitHub tokens (ghp_, gho_, ghs_, github_pat_)
- AWS keys (AKIA..., aws_secret_access_key)
- Bearer tokens
- Private keys (PEM blocks)
- Password/token/secret assignments
- JWTs
- High-entropy strings (40+ chars, Shannon entropy > 4.5)

**Known false positives**: Docker image names with long hashes may be redacted.

---

### SizeLimiter

**Module**: `pipeline_doctor.redaction`

```python
from pipeline_doctor.redaction import SizeLimiter

limiter = SizeLimiter(
    max_log_bytes: int = 100_000,
    max_file_bytes: int = 50_000,
    max_files: int = 20,
    max_api_requests: int = 50
)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_log_bytes` | `int` | `100,000` | Maximum bytes per log excerpt. Keeps head + tail + error context. |
| `max_file_bytes` | `int` | `50,000` | Maximum bytes per source file. Keeps head + tail. |
| `max_files` | `int` | `20` | Maximum number of source files to fetch. |
| `max_api_requests` | `int` | `50` | Maximum API requests. **Note**: This setting is NOT used by `GitHubClient`; set `max_requests` on `GitHubClient` instead. |

#### Example

```python
# Conservative limits
limiter = SizeLimiter(
    max_log_bytes=50_000,
    max_file_bytes=25_000,
    max_files=10,
    max_api_requests=25
)
```

---

### EvidenceCollector

**Module**: `pipeline_doctor.evidence`

```python
from pipeline_doctor.evidence import EvidenceCollector

collector = EvidenceCollector(
    github_client: GitHubClient,
    redactor: SecretRedactor,
    limiter: SizeLimiter
)
```

No additional configuration. Composed from `GitHubClient`, `SecretRedactor`, and `SizeLimiter`.

---

### IncidentReportValidator

**Module**: `pipeline_doctor.validator`

```python
from pipeline_doctor.validator import IncidentReportValidator

validator = IncidentReportValidator(
    known_files: Optional[Set[str]] = None,
    file_line_counts: Optional[Dict[str, int]] = None,
    collected_evidence_ids: Optional[Set[str]] = None
)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `known_files` | `Optional[Set[str]]` | `None` | Set of known file paths in repository. Validates that patch targets and locations reference real files. |
| `file_line_counts` | `Optional[Dict[str, int]]` | `None` | Mapping of file paths to their line counts. Validates that line ranges are within bounds. |
| `collected_evidence_ids` | `Optional[Set[str]]` | `None` | Set of evidence IDs that were collected. Validates that report only references collected evidence. |

#### Example

```python
# Basic validation
validator = IncidentReportValidator()

# With file validation
validator = IncidentReportValidator(
    known_files={"src/main.py", "tests/test_main.py"},
    file_line_counts={"src/main.py": 150, "tests/test_main.py": 75}
)

# Full validation (used by orchestrator)
validator = IncidentReportValidator(
    known_files=set(source_files.keys()),
    collected_evidence_ids={item.id for item in evidence_items}
)
```

---

## Token Usage Estimates

Based on testing with fake data, a typical diagnosis uses:

- **GitHub API requests**: 3-10 requests
  - 1 for run metadata
  - 1 for job list
  - 1 for logs
  - 1 for workflow YAML
  - 0-5 for additional source files

- **Grok API tokens** (estimates, unverified):
  - **Input tokens**: 6,000 - 22,000 (depends on log size, files fetched)
  - **Output tokens**: 1,000 - 2,000 (JSON incident report)
  - **Total**: ~7,000 - 24,000 tokens per diagnosis

**Note**: Token usage depends heavily on log size and number of source files. Use `max_log_bytes` and `max_file_bytes` to control input size.

---

## Example: Full Configuration

```python
import os
from pathlib import Path
from pipeline_doctor.github_client import GitHubClient
from pipeline_doctor.grok_client import GrokAPIClient
from pipeline_doctor.redaction import SecretRedactor, SizeLimiter
from pipeline_doctor.evidence import EvidenceCollector
from pipeline_doctor.prompts import PromptLoader
from pipeline_doctor.validator import IncidentReportValidator
from pipeline_doctor.orchestrator import DiagnosisOrchestrator

# GitHub client with custom request budget
github = GitHubClient(
    token=os.environ.get("GITHUB_TOKEN"),
    max_requests=100
)

# Grok client with custom model and timeouts
grok = GrokAPIClient(
    api_key=os.environ.get("GROK_API_KEY"),
    model="grok-2-latest",
    connect_timeout=15.0,
    read_timeout=90.0,
    max_retries=5
)

# Redactor and limiter with conservative limits
redactor = SecretRedactor()
limiter = SizeLimiter(
    max_log_bytes=50_000,
    max_file_bytes=25_000,
    max_files=10
)

# Evidence collector
evidence_collector = EvidenceCollector(github, redactor, limiter)

# Prompt loader
prompt_loader = PromptLoader(Path("prompts"))

# Validator
validator = IncidentReportValidator()

# Orchestrator
orchestrator = DiagnosisOrchestrator(
    evidence_collector,
    grok,
    prompt_loader,
    validator,
    redactor
)

# Run diagnosis
result = orchestrator.diagnose("owner", "repo", run_id=12345)

if result.success:
    print(f"Root cause: {result.report.diagnosis.root_cause}")
    print(f"Confidence: {result.report.diagnosis.confidence_level}")
    print(f"GitHub requests: {github.request_count}")
else:
    print(f"Errors: {result.errors}")
```

---

## Next Steps

- **[GitHub Token Setup](github-token.md)** — Create a fine-grained read-only token
- **[xAI API Key Setup](xai-api-key.md)** — Get an xAI API key and credits
- **[Usage Guide](usage.md)** — Run diagnoses and read reports
- **[Troubleshooting](troubleshooting.md)** — Common configuration errors
