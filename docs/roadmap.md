# Roadmap

This document lists remaining work, known issues, and future enhancements for Pipeline Doctor.

## Status Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Core library | ✅ Complete | Orchestrator, evidence collector, validator |
| GitHub client | ✅ Complete | Read-only, tested live against public repos |
| Grok client | ⚠️ Mock-tested | NOT verified against live xAI API |
| Secret redaction | ✅ Complete | Known false positives (Docker hashes) |
| Validation | ✅ Complete | Pydantic v2 + JSON Schema Draft 2020-12 |
| CLI example | ✅ Complete | Works with `--fake` flag |
| Documentation | ✅ Complete | Comprehensive guides |
| Tests | ✅ Complete | 155 tests, 154 pass (1 resource warning) |

---

## Remaining Work

### 1. Live Grok Verification

**Status**: ❌ Not verified

**Issue**: The Grok integration has NOT been tested against the live xAI API because the xAI account had no credits during development. All Grok tests use mocked HTTP responses.

**Unverified assumptions**:
- Model name `"grok-beta"` is valid
- xAI API accepts `response_format: {type: "json_object"}`
- xAI API accepts `max_tokens` parameter
- xAI API uses `finish_reason: "length"` for truncation
- Error response formats match mocked examples

**Required before production**:
1. ✅ Get xAI credits
2. ✅ Verify model names with `GET /v1/models`
3. ✅ Test chat completion with small `max_tokens`
4. ✅ Test JSON mode if using `response_format`
5. ✅ Test error responses (403, 429, 5xx)
6. ✅ Verify API key redaction in real error messages
7. ✅ Measure actual token usage for cost estimation

---

### 2. Automatic Triggering on New Failures

**Status**: ❌ Not implemented

**Goal**: Automatically run diagnosis when a workflow fails.

**Options**:

#### Option A: GitHub Action

Create a reusable workflow that triggers on `workflow_run` events:

```yaml
name: Pipeline Doctor
on:
  workflow_run:
    workflows: ["*"]
    types: [completed]

jobs:
  diagnose:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Pipeline Doctor
        run: pip install pipeline-doctor
      - name: Run Diagnosis
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GROK_API_KEY: ${{ secrets.GROK_API_KEY }}
        run: |
          pipeline-doctor diagnose ${{ github.repository }} ${{ github.event.workflow_run.id }}
```

**Challenges**:
- Package not published to PyPI yet
- Needs CLI interface (`pipeline-doctor diagnose`)
- Credential management

#### Option B: Polling Service

External service polls GitHub API for new failures:

```python
# Pseudocode
while True:
    failed_runs = github.list_failed_runs_since(last_check)
    for run in failed_runs:
        result = diagnose(run.owner, run.repo, run.id)
        if result.success:
            create_issue_or_comment(run, result.report)
    sleep(300)  # Poll every 5 minutes
```

**Challenges**:
- Requires hosting (server, lambda, etc.)
- Rate limit management
- Cost (xAI credits per diagnosis)

**Status**: Design phase; not implemented

---

### 3. GitHub Action Packaging

**Status**: ❌ Not packaged

**Goal**: Publish as a reusable GitHub Action.

**Tasks**:
1. Create `action.yml`
2. Package as Docker container or Node.js action
3. Publish to GitHub Marketplace
4. Add README with usage examples

**Example usage** (target):

```yaml
- uses: pipeline-doctor/action@v1
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    grok_api_key: ${{ secrets.GROK_API_KEY }}
    run_id: ${{ github.event.workflow_run.id }}
```

---

### 4. Automatic PR Creation with Fixes

**Status**: ❌ Not implemented

**Goal**: Create pull requests with proposed patches (after human approval).

**Flow**:
1. Diagnosis completes
2. User reviews and approves patch
3. CLI command creates PR: `pipeline-doctor apply report.json --create-pr`
4. PR contains:
   - Patch applied
   - Incident report summary in description
   - Link to full report

**Challenges**:
- Requires write permissions (breaks read-only guarantee)
- User must explicitly approve and trigger
- GitHub token needs `pull_requests: write` scope

**Status**: Design phase; not implemented

---

## Known Issues

### 1. Redaction False Positives: Docker Image Hashes

**Symptom**: Docker image hashes redacted as high-entropy strings.

**Example**:
```
# Original
node:14-alpine@sha256:abcdef1234567890...

# Redacted
node:14-alpine@[REDACTED-HIGH-ENTROPY]
```

**Impact**: Some context lost, but diagnosis usually unaffected.

**Cause**: SHA-256 hashes match high-entropy pattern (40+ chars, entropy >4.5).

**Potential fixes**:
- Whitelist Docker image format: `image:tag@sha256:<hash>`
- Reduce high-entropy threshold (may miss real secrets)
- Add context-aware redaction (check for `@sha256:` prefix)

**Status**: Known issue; fix not prioritized

---

### 2. BOM Stripping Not Implemented

**Symptom**: Files with UTF-8 BOM (Byte Order Mark) may cause validation errors.

**Impact**: Rare; most files don't have BOM.

**Example**:
```
# File with BOM
\xef\xbb\xbf{"key": "value"}

# Causes
json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Potential fix**: Strip BOM in `GitHubClient.get_file_content()`:

```python
content_bytes = base64.b64decode(content_b64)
content = content_bytes.decode("utf-8-sig")  # Strip BOM
```

**Status**: Known issue; fix not prioritized (rare)

---

### 3. Log Pagination Not Implemented

**Symptom**: If a workflow run has more than 30 jobs, only the first 30 are fetched.

**Cause**: GitHub API paginates job lists (`per_page=30` default).

**Impact**: Rare; most workflows have fewer than 30 jobs.

**Potential fix**: Implement pagination in `GitHubClient.list_jobs()`:

```python
def list_jobs(self, owner: str, repo: str, run_id: int) -> List[Dict]:
    jobs = []
    page = 1
    while len(jobs) < 100:  # Safety limit
        response = self._get_json(f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs?page={page}")
        batch = response.get("jobs", [])
        if not batch:
            break
        jobs.extend(batch)
        page += 1
    return jobs
```

**Status**: Known issue; fix not prioritized (rare)

---

### 4. HTTP 410 Logs Expired: No Special Handling

**Symptom**: When logs are expired (>90 days), error message is generic.

**Current behavior**:
```
Limitation: Failed to fetch job logs: HTTP 410: Logs are no longer available
```

**Desired behavior**:
```
Limitation: Job logs expired (>90 days old). GitHub Actions logs are retained for 90 days only.
```

**Potential fix**: Check for `410` status code and provide user-friendly message.

**Status**: Minor usability issue; fix not prioritized

---

### 5. Confidence Scoring: Uncalibrated

**Symptom**: Confidence scores (0.0-1.0) are heuristic, not calibrated probabilities.

**Impact**: Cannot interpret confidence as "80% probability this is correct."

**Example**: A diagnosis with `confidence: 0.8` may not actually be correct 80% of the time.

**Potential fix**: Calibrate against historical diagnoses:
1. Collect large dataset of diagnoses
2. Label correctness (human review)
3. Train calibration model (e.g., isotonic regression)
4. Adjust confidence scores

**Status**: Research required; not prioritized

---

### 6. Test Socket Cleanup Warning

**Symptom**: `test_redirect_same_host_keeps_auth_header` shows resource warning about unclosed sockets.

**Impact**: Test cleanup issue; does not affect production code.

**Potential fix**: Properly close sockets in test teardown.

**Status**: Minor test issue; does not affect functionality

---

## Future Enhancements

### 1. Support for Other CI Systems

**Goal**: Support GitLab CI, CircleCI, Jenkins, etc.

**Approach**:
- Abstract `CIClient` protocol (like `GitHubClient`)
- Implement `GitLabClient`, `CircleCIClient`, etc.
- Generalize evidence collection

**Status**: Not planned (out of scope for GitHub Actions focus)

---

### 2. Historical Failure Correlation

**Goal**: Detect patterns across multiple failures.

**Example**: "This test has failed 5 times in the last week with the same error."

**Approach**:
- Store incident reports in database
- Query for similar failures (fuzzy match on root cause, locations, error patterns)
- Add `historical_context` field to report

**Status**: Future enhancement; not planned

---

### 3. Repository Health Score

**Goal**: Identify chronic issues and suggest improvements.

**Example**:
- "Flaky test: `test_user_auth` fails 20% of the time"
- "Missing test coverage: `src/auth/oauth.py` has no tests"

**Approach**:
- Aggregate multiple incident reports
- Analyze failure frequency, flakiness
- Suggest repository improvements

**Status**: Future enhancement; not planned

---

### 4. Cost Estimation and Budgeting

**Goal**: Estimate xAI credit usage before running diagnosis.

**Features**:
- Estimate tokens based on log size, file count
- Warn if estimate exceeds budget
- Track cumulative cost

**Status**: Nice-to-have; not planned

---

### 5. Streaming Responses

**Goal**: Stream incident report as Grok generates it.

**Benefits**:
- Faster perceived latency
- Can display partial results

**Challenges**:
- Parsing incomplete JSON
- Validation on partial data

**Status**: Future enhancement; not planned

---

### 6. Response Caching

**Goal**: Cache Grok responses for identical inputs.

**Benefits**:
- Reduce xAI costs
- Faster repeated diagnoses

**Approach**:
- Hash (system_prompt, user_message)
- Store response in cache (Redis, SQLite)
- Expiration: 24-48 hours

**Challenges**:
- Cache invalidation (model updates, prompt changes)
- Storage management

**Status**: Future enhancement; not planned

---

## Completed Work

### ✅ GitHub Client

- Read-only API client
- Token authentication
- Rate limit handling
- Redirect handling (cross-host auth stripping)
- Request budget enforcement
- Token redaction in errors
- 404, 403, 401, 410, 429 handling

**Tests**: 36 tests covering all scenarios

**Status**: Complete, verified live

---

### ✅ Grok Client

- Chat completion API
- Error handling (403, 429, 5xx)
- Retry logic with exponential backoff
- API key redaction
- Configurable timeouts, model, max_tokens
- Response format support (JSON mode)
- Truncation detection

**Tests**: 28 tests covering all scenarios

**Status**: Complete, NOT verified live

---

### ✅ Evidence Collection

- Run metadata
- Job logs (with truncation)
- Workflow YAML
- Source files (with pinning)
- Evidence item tracking (unique IDs)
- Limitation recording

**Tests**: 12 tests

**Status**: Complete, verified live

---

### ✅ Secret Redaction

- Comprehensive patterns (GitHub, AWS, JWTs, etc.)
- High-entropy detection
- Applied to all untrusted data

**Tests**: 12 tests

**Status**: Complete (known false positives)

---

### ✅ Validation

- Pydantic v2 models
- JSON Schema Draft 2020-12 compliance
- Evidence ID validation
- Confidence scoring consistency
- Patch consistency checks
- Hardened JSON extraction (prose-wrapped, truncated)

**Tests**: 35 tests

**Status**: Complete

---

### ✅ Orchestration

- End-to-end diagnosis pipeline
- SHA drift detection
- Graceful error handling
- Limitation tracking

**Tests**: 5 tests

**Status**: Complete

---

### ✅ Documentation

- README (landing page)
- Getting Started
- Configuration
- GitHub Token Setup
- xAI API Key Setup
- Usage Guide
- Troubleshooting
- Security
- Incident Report Schema
- Roadmap (this document)

**Status**: Complete

---

## Priority Order

1. **Live Grok Verification** — Critical before production use
2. **GitHub Action Packaging** — Enables auto-triggering
3. **Automatic Triggering** — Completes the user experience
4. **Redaction False Positives** — Improves diagnosis quality
5. **PR Creation** — Streamlines fix application

---

## Contributing

To contribute to any of the remaining work:

1. Read [CONTRIBUTING.md](../CONTRIBUTING.md)
2. Pick an item from this roadmap
3. Open an issue to discuss approach
4. Submit a pull request

---

## Next Steps

- **[Getting Started](getting-started.md)** — Install and run Pipeline Doctor
- **[Usage Guide](usage.md)** — Run diagnoses and read reports
- **[Troubleshooting](troubleshooting.md)** — Common errors and fixes
- **[Security](security.md)** — Read-only guarantee, redaction, prompt injection
