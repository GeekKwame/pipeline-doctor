# GitHub Client Implementation

Documentation for the real GitHub REST API client.

## Overview

The `GitHubClient` class in `src/pipeline_doctor/github_client.py` provides read-only access to GitHub Actions data via the GitHub REST API.

## Features

### Read-Only Operations

The client uses **only GET requests**. No write operations (POST, PUT, PATCH, DELETE) are implemented or allowed. This ensures:
- Safety: cannot modify repository data
- Simplicity: straightforward authentication requirements
- Minimal permissions: works with read-only tokens

### Authentication

Token can be provided in two ways:
1. Constructor argument: `GitHubClient(token="ghp_...")`
2. Environment variable: `GITHUB_TOKEN`

If no token is provided, the client will attempt anonymous access (subject to much lower rate limits).

**Required scopes**:
- `repo` (full repository access), or
- `actions:read` (read-only Actions access)

### Token Security

Tokens are **never logged or exposed in error messages**:
- All error messages pass through `_redact_token_from_message()`
- Token strings are replaced with `[REDACTED-TOKEN]`
- Applies to all exception messages

### Rate Limit Handling

The client detects and handles GitHub rate limits:
- HTTP 403 or 429 status codes trigger `RateLimitError`
- `X-RateLimit-Reset` header is captured and exposed as `reset_at` timestamp
- Clients can catch `RateLimitError` and retry after the reset time

### Request Budget

To prevent runaway API usage:
- Default maximum: 50 requests per client instance
- Configurable via `max_requests` parameter
- Current count tracked in `request_count` attribute
- Exceeding budget raises `GitHubAPIError`

### 404 Handling

Missing resources raise `NotFoundError`:
- Workflow runs that don't exist
- Jobs that are not accessible
- Files not present at the specified commit SHA

This allows callers to distinguish "not found" from other errors and add appropriate limitations to the incident report.

### Log Downloads

GitHub Actions logs are returned as redirects to zip files or direct URLs:
- Client follows redirects automatically
- Extracts content from zip archives when detected
- Falls back to plain text if not a zip
- Handles both formats transparently

### Commit SHA Pinning

All file content fetches use the `ref` parameter:
- `get_file_content(owner, repo, path, ref)`
- `get_workflow_file(owner, repo, workflow_path, ref)`

The `ref` should be set to the workflow run's `head_sha` to ensure consistency. This prevents race conditions where files change between API calls.

The `EvidenceCollector` captures the SHA from the workflow run metadata and uses it for all subsequent file fetches.

## API Endpoints

### Get Workflow Run

```python
run = client.get_workflow_run("owner", "repo", run_id=12345)
```

**GitHub API**: `GET /repos/{owner}/{repo}/actions/runs/{run_id}`

Returns workflow run metadata including:
- `id`: Run ID
- `name`: Workflow name
- `head_sha`: Commit SHA
- `head_branch`: Branch name
- `status`: Run status (completed, in_progress, etc.)
- `conclusion`: Run conclusion (success, failure, etc.)
- `html_url`: Web URL to the run

### List Jobs

```python
jobs = client.list_jobs("owner", "repo", run_id=12345)
```

**GitHub API**: `GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs`

Returns list of job dictionaries, each containing:
- `id`: Job ID
- `name`: Job name
- `status`: Job status
- `conclusion`: Job conclusion
- `steps`: List of step dictionaries

### Get Job Logs

```python
logs = client.get_job_logs("owner", "repo", job_id=1001)
```

**GitHub API**: `GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs`

Returns job logs as a string. Handles:
- Redirect responses (GitHub redirects to artifact storage)
- Zip file extraction (logs are often zipped)
- Plain text fallback

### Get File Content

```python
content = client.get_file_content("owner", "repo", "src/main.py", ref="abc123...")
```

**GitHub API**: `GET /repos/{owner}/{repo}/contents/{path}?ref={ref}`

Returns file content as a string. The `ref` parameter should be a commit SHA.

Handles:
- Base64 decoding (GitHub returns content as base64)
- Newlines in base64 (GitHub adds newlines every ~60 chars)

### Get Workflow File

```python
yaml = client.get_workflow_file("owner", "repo", ".github/workflows/ci.yml", ref="abc123...")
```

Same as `get_file_content()` but semantically clearer when fetching workflow YAML files.

## Error Handling

### Exception Hierarchy

```
Exception
└── GitHubAPIError (base class)
    ├── NotFoundError (404)
    └── RateLimitError (403/429)
```

### Error Patterns

**Not Found**:
```python
try:
    run = client.get_workflow_run("owner", "repo", 99999)
except NotFoundError as e:
    print(f"Run not found: {e}")
```

**Rate Limit**:
```python
try:
    run = client.get_workflow_run("owner", "repo", 12345)
except RateLimitError as e:
    print(f"Rate limited until: {e.reset_at}")
    # Wait and retry
```

**Generic API Error**:
```python
try:
    run = client.get_workflow_run("owner", "repo", 12345)
except GitHubAPIError as e:
    print(f"API error: {e}")
```

**Budget Exceeded**:
```python
try:
    # Make many requests...
except GitHubAPIError as e:
    if "budget exceeded" in str(e).lower():
        print("Hit request limit")
```

## Implementation Details

### Dependencies

Uses only Python standard library:
- `urllib.request` for HTTP
- `urllib.error` for exception handling
- `base64` for content decoding
- `zipfile` for log extraction
- `json` for response parsing

No external HTTP libraries required (though `requests` could be used as an alternative).

### No Write Methods

The implementation intentionally excludes:
- `create_*` methods
- `update_*` methods
- `delete_*` methods
- Any POST, PUT, PATCH, DELETE requests

This is enforced by design and verified in tests.

## Testing

### Mocked HTTP Tests

All tests use mocked `urlopen` (via `unittest.mock.patch`):
- No network calls
- No credentials required
- Deterministic results
- Fast execution

Test coverage includes:
- ✅ Success paths for all endpoints
- ✅ 404 handling
- ✅ Rate limit handling (403 and 429)
- ✅ Token redaction in errors
- ✅ Request budget enforcement
- ✅ Log download (zip and plain text)
- ✅ Base64 decoding with newlines
- ✅ Network errors
- ✅ Authorization header format
- ✅ No write methods exist
- ✅ SHA pinning via ref parameter

Run tests with:
```bash
pytest tests/test_github_client.py -v
```

### Live Testing (Optional)

To test against real GitHub API:

```python
from pipeline_doctor.github_client import GitHubClient

client = GitHubClient(token="ghp_your_token")

# Use a public workflow run from a public repository
run = client.get_workflow_run("actions", "toolkit", run_id=123456789)
print(run["name"])
```

**Note**: The implementation is tested only against mocked HTTP. Live API testing is optional and not required for correctness.

## Example Usage

### Standalone

```python
import os
from pipeline_doctor.github_client import GitHubClient

client = GitHubClient(token=os.environ["GITHUB_TOKEN"])

# Get run info
run = client.get_workflow_run("octocat", "hello-world", 12345)
print(f"Workflow: {run['name']}")
print(f"Status: {run['conclusion']}")

# Get jobs
jobs = client.list_jobs("octocat", "hello-world", 12345)
for job in jobs:
    print(f"Job: {job['name']} - {job['conclusion']}")

# Get logs for failed job
failed_jobs = [j for j in jobs if j["conclusion"] == "failure"]
if failed_jobs:
    logs = client.get_job_logs("octocat", "hello-world", failed_jobs[0]["id"])
    print(logs)

# Get workflow file
sha = run["head_sha"]
workflow_yaml = client.get_workflow_file("octocat", "hello-world", run["path"], sha)
print(workflow_yaml)
```

### With Evidence Collector

```python
import os
from pipeline_doctor.evidence import EvidenceCollector
from pipeline_doctor.github_client import GitHubClient
from pipeline_doctor.redaction import SecretRedactor, SizeLimiter

github = GitHubClient(token=os.environ["GITHUB_TOKEN"])
redactor = SecretRedactor()
limiter = SizeLimiter()

collector = EvidenceCollector(github, redactor, limiter)
evidence = collector.collect_run_evidence("owner", "repo", run_id=12345)

print(f"Collected {len(evidence['evidence_items'])} evidence items")
print(f"Pinned SHA: {evidence['pinned_sha']}")
```

### CLI Tool

See `examples/diagnose_run.py` for a complete CLI example:

```bash
export GITHUB_TOKEN="ghp_your_token"
python examples/diagnose_run.py owner/repo 12345
```

## Future Enhancements

Potential improvements (not currently implemented):

- **httpx support**: Optional `httpx` dependency for async operations
- **Retry logic**: Automatic retry with exponential backoff
- **Pagination**: Handle paginated responses for large job lists
- **Conditional requests**: Use ETags for caching
- **GraphQL**: Alternative to REST for fewer API calls

These are **not required** for current functionality and would add complexity.

## Security Considerations

### Token Handling

- ✅ Never logged or printed
- ✅ Never included in exception messages
- ✅ Redacted from all error output
- ✅ Not stored in logs or reports
- ✅ Environment variable or constructor only

### Read-Only Access

- ✅ No write operations possible
- ✅ Cannot modify repository data
- ✅ Cannot trigger workflows
- ✅ Cannot create issues or PRs
- ✅ Safe for CI/CD environments

### Content Validation

- ✅ Base64 decoding errors caught
- ✅ JSON parsing errors caught
- ✅ Malformed responses handled gracefully
- ✅ No code execution from API responses
- ✅ All content treated as untrusted data

## Comparison: Real vs Fake Client

| Feature | `GitHubClient` | `FakeGitHubClient` |
|---------|----------------|---------------------|
| Purpose | Production use | Testing |
| Network | Yes | No |
| Token required | Yes | No |
| Rate limits | Yes | No |
| 404 errors | Yes | Configurable |
| Deterministic | No | Yes |
| Fast | Network-dependent | Instant |

Both implement the same `GitHubClient` protocol from `protocols.py`, allowing transparent substitution via dependency injection.
