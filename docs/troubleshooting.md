# Troubleshooting

This guide covers common errors and their solutions, organized by component.

## GitHub API Errors

### HTTP 401: Bad credentials

**Full error message**:
```
PermissionError: Authentication failed (401): Bad credentials
```

**Causes**:
1. `GITHUB_TOKEN` is invalid, expired, or malformed
2. Token is not set

**Fixes**:

1. **Check token is set**:
   ```bash
   echo $GITHUB_TOKEN
   ```
   Should output a token starting with `ghp_`, `gho_`, or `github_pat_`.

2. **Regenerate token**:
   - Go to GitHub → Settings → Developer settings → Personal access tokens
   - Create a new fine-grained token with **Actions: Read** and **Contents: Read**
   - See [GitHub Token Setup](github-token.md)

3. **Update environment variable**:
   ```bash
   export GITHUB_TOKEN="ghp_..."
   ```

---

### HTTP 403: Insufficient permissions

**Full error message**:
```
GitHubPermissionError: Insufficient permissions (403): Token lacks required scope. 
Required: actions=read;contents=read. Response: Resource not accessible by personal access token
```

**Causes**:
1. Token lacks **Actions: Read** permission
2. Token lacks **Contents: Read** permission
3. Token is scoped to specific repositories and doesn't include this one

**Fixes**:

1. **Check token permissions**:
   - Go to GitHub → Settings → Developer settings → Personal access tokens
   - Click on your token
   - Verify **Actions: Read** and **Contents: Read** are enabled

2. **Regenerate token with correct permissions**:
   - See [GitHub Token Setup](github-token.md)

3. **Check repository access**:
   - If token is repository-scoped, add the target repository to access list

---

### HTTP 403: No credits (Grok, not GitHub)

**Note**: This is a Grok error, not GitHub. See [Grok Errors](#grok-api-errors) below.

---

### HTTP 404: Not Found

**Full error message**:
```
NotFoundError: HTTP 404: {"message":"Not Found","documentation_url":"..."}
```

**Causes**:
1. Run ID doesn't exist
2. Repository is private and token doesn't have access
3. Repository doesn't exist or is misspelled

**Fixes**:

1. **Verify run ID**:
   - Check URL: `https://github.com/owner/repo/actions/runs/12345`
   - Run ID is the number after `/runs/`

2. **Verify repository name**:
   - Format: `owner/repo` (case-sensitive)
   - Example: `facebook/react`, not `Facebook/React`

3. **Check private repository access**:
   - If private, ensure `GITHUB_TOKEN` has access
   - Token must be scoped to the repository

4. **Test manually**:
   ```bash
   curl -H "Authorization: Bearer $GITHUB_TOKEN" \
        https://api.github.com/repos/owner/repo/actions/runs/12345
   ```

---

### HTTP 410: Logs are no longer available

**Full error message**:
```
GitHubAPIError: HTTP 410: {"message":"Logs are no longer available for this job"}
```

**Cause**: GitHub Actions logs are retained for **90 days** only. After 90 days, logs are permanently deleted.

**Impact**: Pipeline Doctor can still fetch run metadata and workflow YAML, but diagnosis will be limited without logs.

**Limitation added to report**:
```
"limitations": [
  "Failed to fetch job logs: HTTP 410: Logs are no longer available"
]
```

**Fixes**:
- **No fix**: Logs are permanently gone
- **Diagnosis**: Will proceed with available evidence (metadata, YAML)
- **Confidence**: Likely to be `low` or `insufficient` without logs

**Prevention**: Run diagnosis within 90 days of workflow failure.

---

### HTTP 429: Rate limit exceeded

**Full error message**:
```
RateLimitError: HTTP 429: Rate limit exceeded. Reset at: 2024-10-18T15:30:00Z
```

**Causes**:
1. Too many requests in a short time
2. Unauthenticated requests (60/hour limit)
3. Authenticated requests exceeded (5,000/hour limit)

**Fixes**:

1. **Wait for reset**:
   - Check `X-RateLimit-Reset` header or error message
   - Wait until reset time

2. **Use authenticated requests**:
   ```bash
   export GITHUB_TOKEN="ghp_..."
   ```
   - Unauthenticated: 60 requests/hour
   - Authenticated: 5,000 requests/hour

3. **Reduce request budget**:
   ```python
   github = GitHubClient(token="ghp_...", max_requests=25)
   ```

4. **Check current limits**:
   ```bash
   curl -H "Authorization: Bearer $GITHUB_TOKEN" \
        https://api.github.com/rate_limit
   ```

---

### Request budget exceeded

**Full error message**:
```
GitHubAPIError: Request budget exceeded (max: 50)
```

**Cause**: `max_requests` limit reached before diagnosis completed.

**Fixes**:

1. **Increase budget**:
   ```python
   github = GitHubClient(max_requests=100)
   ```

2. **Reduce file fetches**:
   ```python
   limiter = SizeLimiter(max_files=10)
   ```

3. **Avoid large repositories**:
   - Fetching many source files increases request count

---

### Redirect loop detected

**Full error message**:
```
GitHubAPIError: Redirect loop detected: https://storage.googleapis.com/...
```

**Cause**: GitHub API redirected to the same URL multiple times.

**Fix**: This is a GitHub API issue. Report to GitHub Support or retry later.

---

### Invalid redirect scheme

**Full error message**:
```
GitHubAPIError: Invalid redirect scheme: ftp
```

**Cause**: GitHub API redirected to a non-HTTP(S) URL.

**Fix**: This is a GitHub API issue. Report to GitHub Support.

---

## Grok API Errors

### No API key provided

**Full error message**:
```
ValueError: Grok API key required: set GROK_API_KEY or XAI_API_KEY environment variable
```

**Cause**: `GROK_API_KEY` and `XAI_API_KEY` are both unset.

**Fixes**:

1. **Set environment variable**:
   ```bash
   export GROK_API_KEY="xai-..."
   ```

2. **Or use fake client for testing**:
   ```bash
   python3 examples/diagnose_run.py --fake owner/repo 12345
   ```

---

### HTTP 401: Bad credentials (Grok)

**Full error message**:
```
GrokAPIError: API request failed with status 401: {"error": "Invalid API key"}
```

**Causes**:
1. `GROK_API_KEY` is invalid or expired
2. API key is malformed

**Fixes**:

1. **Check API key**:
   ```bash
   echo $GROK_API_KEY
   ```
   Should start with `xai-`.

2. **Regenerate API key**:
   - Go to https://console.x.ai/ → API Keys
   - Create new key
   - Update environment variable

---

### HTTP 403: No credits

**Full error message**:
```
GrokAPIError: API request failed with status 403: {"error": "Insufficient credits"}
```

**Cause**: xAI account has no credits.

**Fixes**:

1. **Add credits**:
   - Go to https://console.x.ai/ → Billing → Add Credits
   - Purchase credits ($10-$20 for testing)

2. **Check current balance**:
   - xAI console → Usage → Current Balance

3. **Use fake client for testing**:
   ```bash
   python3 examples/diagnose_run.py --fake owner/repo 12345
   ```

---

### HTTP 404: Model not found

**Full error message**:
```
GrokAPIError: API request failed with status 404: {"error": "Model 'grok-beta' not found"}
```

**Cause**: Model name is invalid or no longer available.

**Fixes**:

1. **List available models**:
   ```bash
   curl -H "Authorization: Bearer $GROK_API_KEY" \
        https://api.x.ai/v1/models
   ```

2. **Update model**:
   ```bash
   export GROK_MODEL="grok-2-latest"
   ```

3. **Or specify in code**:
   ```python
   grok = GrokAPIClient(api_key="xai-...", model="grok-2-latest")
   ```

---

### HTTP 429: Rate limited (Grok)

**Full error message**:
```
GrokAPIError: API request failed with status 429: {"error": "Rate limit exceeded"}
```

**Cause**: Too many requests to xAI API.

**Automatic fix**: `GrokAPIClient` retries with exponential backoff (1s, 2s, 4s, 8s).

**Manual fix**: Wait and retry after a few seconds.

**Increase retries**:
```python
grok = GrokAPIClient(api_key="xai-...", max_retries=5)
```

---

### Response truncated (finish_reason: length)

**Full error message**:
```
GrokAPIError: Response was truncated (finish_reason: length). Increase max_tokens.
```

**Cause**: Grok's response exceeded `max_tokens` limit.

**Fixes**:

1. **Increase max_tokens**:
   ```python
   response = grok.chat_completion(
       system_prompt="...",
       user_message="...",
       max_tokens=8192
   )
   ```

2. **Or reduce input size**:
   ```python
   limiter = SizeLimiter(max_log_bytes=50_000, max_file_bytes=25_000)
   ```

---

### Request timeout

**Full error message**:
```
GrokAPIError: Request timeout: HTTPSConnectionPool(host='api.x.ai', port=443): Read timed out.
```

**Cause**: Grok API took too long to respond.

**Fixes**:

1. **Increase timeout**:
   ```python
   grok = GrokAPIClient(
       api_key="xai-...",
       connect_timeout=60.0,
       read_timeout=180.0
   )
   ```

2. **Retry**: Automatic retries for timeout errors (up to `max_retries`).

---

## Validation Errors

### Response is empty

**Full error message**:
```
ValidationResult(success=False, errors=['Response is empty'])
```

**Cause**: Grok returned an empty response.

**Fixes**:
1. Check Grok API status
2. Retry diagnosis
3. Increase `max_tokens`

---

### Response is a JSON array, not an object

**Full error message**:
```
ValidationResult(success=False, errors=['Response is a JSON array, not an object. Expected a JSON object with incident report fields.'])
```

**Cause**: Grok returned a JSON array (`[...]`) instead of an object (`{...}`).

**Fixes**:
1. Check Grok prompt template (`prompts/diagnosis_system_prompt.md`)
2. Retry diagnosis (may be a transient AI error)
3. Report as bug if persistent

---

### Failed to parse JSON from response

**Full error message**:
```
ValidationResult(success=False, errors=['Failed to parse JSON from response. JSON may be truncated or malformed.'])
```

**Causes**:
1. Grok response was truncated (finish_reason: length)
2. Grok returned invalid JSON
3. Response wrapped in prose

**Fixes**:

1. **Increase max_tokens**:
   ```python
   response = grok.chat_completion(..., max_tokens=8192)
   ```

2. **Check for truncation**: Look for `finish_reason: "length"` in Grok error

3. **Retry**: May be transient AI error

---

### Patch targets unknown file

**Full error message**:
```
ValidationResult(success=False, errors=['Patch targets unknown file: src/nonexistent.py'])
```

**Cause**: Proposed patch references a file that wasn't fetched or doesn't exist.

**Impact**: Validation fails, but report may still contain useful diagnosis.

**Fixes**:
1. Fetch additional files:
   ```python
   result = orchestrator.diagnose(
       "owner", "repo", run_id=12345,
       additional_files=["src/nonexistent.py"]
   )
   ```

2. **Or disable file validation**:
   ```python
   validator = IncidentReportValidator(known_files=None)
   ```

---

### Evidence ID references unknown evidence

**Full error message**:
```
ValidationResult(success=False, errors=["Report contains evidence IDs that were not in the collected set: {'E99'}"])
```

**Cause**: Diagnosis references evidence ID (e.g., `E99`) that wasn't collected.

**Impact**: Grok invented evidence IDs that don't exist in the evidence index.

**Fixes**:
1. Retry diagnosis (transient AI error)
2. Check prompt template includes evidence index
3. Report as bug if persistent

---

## Orchestration Errors

### Could not determine commit SHA

**Full error message**:
```
Errors:
  - Could not determine commit SHA for the workflow run
```

**Cause**: Run metadata is missing `head_sha` field.

**Fixes**:
1. Verify run exists and is accessible
2. Check GitHub API status
3. Retry diagnosis

---

### Commit SHA drift detected

**Full error message**:
```
Errors:
  - Commit SHA drift detected: started with abc123..., now at def456...
```

**Cause**: The workflow run's commit SHA changed between evidence collection start and end. This should never happen (indicates a race condition or GitHub API issue).

**Fixes**:
1. Retry diagnosis (should be rare)
2. Report as bug if persistent

---

### Grok API error surfaced

**Full error message**:
```
Errors:
  - Grok API error (status 403): {"error": "Insufficient credits"}
```

**Cause**: Grok API call failed. Status code and response body are included.

**Fixes**: See [Grok API Errors](#grok-api-errors) above.

---

## CLI Errors

### No module named 'pipeline_doctor'

**Full error message**:
```
ModuleNotFoundError: No module named 'pipeline_doctor'
```

**Cause**: Package not installed.

**Fixes**:

1. **Install package**:
   ```bash
   pip install -e ".[dev]"
   ```

2. **Activate virtual environment**:
   ```bash
   source venv/bin/activate
   ```

---

### pytest: command not found

**Cause**: `pytest` not installed or virtual environment not activated.

**Fixes**:

1. **Activate virtual environment**:
   ```bash
   source venv/bin/activate
   ```

2. **Install dev dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

---

## Known Issues

### False Positive: Docker Image Names Redacted

**Symptom**: Docker image hashes redacted as secrets.

**Example**: `node:14-alpine@sha256:abcd1234...` → `node:14-alpine@[REDACTED-HIGH-ENTROPY]`

**Impact**: Some context lost, but diagnosis usually unaffected.

**Workaround**: None yet.

**Status**: Known issue. See [Roadmap](roadmap.md).

---

### BOM Stripping Not Implemented

**Symptom**: Files with UTF-8 BOM (Byte Order Mark) may cause validation errors.

**Impact**: Rare; most files don't have BOM.

**Workaround**: Strip BOM manually from files.

**Status**: Known issue. See [Roadmap](roadmap.md).

---

### Log Pagination Not Implemented

**Symptom**: If a run has more than 30 jobs, only the first 30 are fetched.

**Impact**: Rare; most workflows have fewer than 30 jobs.

**Workaround**: None.

**Status**: Known issue. See [Roadmap](roadmap.md).

---

### Socket Cleanup Warning in Tests

**Symptom**: `test_redirect_same_host_keeps_auth_header` shows resource warning about unclosed sockets.

**Impact**: Test cleanup issue; does not affect functionality.

**Status**: Known issue; does not impact production code.

---

## Diagnostic Commands

### Check GitHub Token

```bash
# Token is set
echo $GITHUB_TOKEN

# Token works
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     https://api.github.com/user
```

### Check Grok API Key

```bash
# API key is set
echo $GROK_API_KEY

# API key works
curl -H "Authorization: Bearer $GROK_API_KEY" \
     https://api.x.ai/v1/models
```

### Check GitHub Rate Limits

```bash
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     https://api.github.com/rate_limit
```

### Test GitHub API Access

```bash
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     https://api.github.com/repos/owner/repo/actions/runs/12345
```

### Test Grok Chat Completion

```bash
curl -X POST https://api.x.ai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GROK_API_KEY" \
  -d '{
    "model": "grok-beta",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Say hello."}
    ],
    "temperature": 0.1,
    "max_tokens": 100
  }'
```

---

## Getting Help

If you encounter an error not covered here:

1. **Check error message carefully**: Most errors include actionable information.
2. **Review documentation**: [Configuration](configuration.md), [Usage](usage.md), [Security](security.md)
3. **Test with fake client**: Isolate whether issue is GitHub, Grok, or validation
4. **Check API status**: GitHub and xAI may have outages
5. **Report bugs**: Open an issue on GitHub with:
   - Full error message (redact tokens/keys)
   - Steps to reproduce
   - Environment (Python version, OS)

---

## Next Steps

- **[Configuration](configuration.md)** — All configuration options
- **[GitHub Token Setup](github-token.md)** — Token permissions and creation
- **[xAI API Key Setup](xai-api-key.md)** — Credits and model selection
- **[Security](security.md)** — Read-only guarantee, redaction, prompt injection
