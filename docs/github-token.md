# GitHub Token Setup

Pipeline Doctor requires a **fine-grained, read-only** GitHub personal access token to access workflow runs, job logs, and source files. This guide walks you through creating one.

## Why a Token is Required

- **Unauthenticated access** has severe limitations:
  - Rate limit: 60 requests/hour (exhausted quickly)
  - Job logs often unavailable (403 Forbidden)
  - Private repository access: not possible

- **With a token**:
  - Rate limit: 5,000 requests/hour
  - Full access to job logs
  - Access to private repositories (if token has permission)

## Token Requirements

### Read-Only Permissions

Pipeline Doctor uses **only GET requests** — no POST, PUT, PATCH, or DELETE. The GitHub client cannot modify repositories, create issues, or perform write operations.

### Required Scopes (Fine-Grained Token)

For **fine-grained personal access tokens** (recommended), grant these repository permissions:

| Permission | Access | Why Required |
|------------|--------|--------------|
| **Actions** | Read | Access workflow runs, jobs, and logs |
| **Contents** | Read | Access workflow YAML files and source code |
| **Metadata** | Read | Automatically included; repository metadata |

### Classic Token Scopes (Not Recommended)

If using a **classic personal access token** (legacy), use:
- `repo` (full repository access) — or —
- `public_repo` (public repositories only)

**⚠️ Classic tokens have broader permissions than needed.** Use fine-grained tokens instead.

---

## Step-by-Step: Creating a Fine-Grained Token

### 1. Navigate to Token Settings

Go to GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**

Or visit directly: https://github.com/settings/personal-access-tokens/new

### 2. Configure Token Basics

- **Token name**: `pipeline-doctor-read-only`
- **Description**: `Read-only token for Pipeline Doctor diagnosis`
- **Expiration**: Choose based on your security policy
  - **90 days** (recommended for production)
  - **Custom** (shorter for testing, e.g., 7 days)
  - **No expiration** (not recommended; no auto-rotation)

### 3. Choose Repository Access

Select which repositories this token can access:

#### Option A: Specific Repositories (Recommended)

- **Repository access**: "Only select repositories"
- Click **Select repositories** and choose the repositories you want to diagnose
- Example: `owner/my-project`, `owner/another-project`

**Best for**: Production use, testing on specific repos

#### Option B: All Repositories

- **Repository access**: "All repositories"
- Grants access to all current and future repos

**⚠️ Warning**: Broad access. Use only if needed for organization-wide monitoring.

### 4. Set Repository Permissions

Scroll to **Repository permissions** and set:

| Permission | Access Level |
|------------|--------------|
| **Actions** | **Read** |
| **Contents** | **Read** |
| **Metadata** | Read (auto-selected) |

**Do NOT grant**:
- Write access to any permission
- Admin access
- Permissions beyond Actions, Contents, Metadata

### 5. Generate Token

- Click **Generate token**
- **Copy the token immediately** — you won't see it again
- Store securely (password manager, environment variable, secret manager)

### 6. Save Token as Environment Variable

```bash
export GITHUB_TOKEN="ghp_1234567890abcdefghijklmnopqrstuvwxyz12"
```

Add to your shell profile (`~/.bashrc`, `~/.zshrc`) or use a `.env` file (never commit to version control).

**Verify it works**:

```bash
echo $GITHUB_TOKEN | wc -c
# Expected: ~40-50 characters
```

---

## Token Expiry

Fine-grained tokens expire after the configured duration. When a token expires:

- **Symptom**: `HTTP 401` errors: `"Bad credentials"` or `"token expired"`
- **Fix**: Generate a new token and update `GITHUB_TOKEN`

Set calendar reminders to rotate tokens before expiry.

---

## Security Best Practices

### ✅ DO

- Use **fine-grained tokens** with minimal permissions
- Set **short expiration** (90 days or less)
- Store tokens in **environment variables** or secret managers
- Rotate tokens regularly
- Use separate tokens for different environments (dev, staging, prod)

### ❌ DON'T

- Never commit tokens to version control
- Never share tokens in chat, email, or logs
- Don't use classic tokens unless necessary
- Don't grant write permissions
- Don't use "no expiration"

---

## How Logs Behave Without Permissions

### Log Retention: 90 Days

GitHub Actions logs are retained for **90 days** after a workflow run completes. After 90 days:

- **Symptom**: `HTTP 410 Gone` when fetching logs
- **Error message**: `"Logs are no longer available for this job"`
- **Impact**: Pipeline Doctor can still fetch run metadata and workflow YAML, but diagnosis will be limited

**In diagnosis report**: Limitation added: `"Failed to fetch job logs: HTTP 410: Logs are no longer available"`

### Private Repository Access

Without a token or with insufficient permissions:

- **Symptom**: `HTTP 403 Forbidden` or `HTTP 404 Not Found`
- **Error message**: `"Not Found"` or `"Resource not accessible by personal access token"`
- **Impact**: Cannot access private repositories at all

### Missing Actions: Read Permission

If token lacks **Actions: Read**:

- **Symptom**: `HTTP 403 Forbidden` when fetching logs
- **Error message**: `"Resource not accessible by personal access token"`
- **Header**: `X-Accepted-GitHub-Permissions: actions=read`
- **Impact**: Can fetch run metadata but not logs

**Fix**: Regenerate token with **Actions: Read** permission.

---

## Rate Limits

GitHub API rate limits apply per token:

| Access Type | Rate Limit | Window |
|-------------|------------|--------|
| **Unauthenticated** | 60 requests | 1 hour |
| **Authenticated (token)** | 5,000 requests | 1 hour |
| **Redirect hops** | Counted toward limit | — |

**Pipeline Doctor usage**:
- Typical diagnosis: 3-10 API requests
- With redirects (log downloads): +1-2 requests

**Rate limit exceeded**:
- **Symptom**: `HTTP 429` or `HTTP 403` with `X-RateLimit-Remaining: 0`
- **Error**: `RateLimitError` raised
- **Reset**: Check `X-RateLimit-Reset` header for reset timestamp

**Fix**: Wait until rate limit resets or use a different token.

---

## Verify Token Permissions

Test your token:

```bash
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     https://api.github.com/repos/owner/repo/actions/runs/12345
```

**Expected**: JSON response with run metadata

**If 404**: Run doesn't exist or token lacks access to repository

**If 403**: Token lacks required permissions (Actions: Read)

**If 401**: Token is invalid or expired

---

## Troubleshooting

### HTTP 401: Bad credentials

**Cause**: Token is invalid, expired, or malformed

**Fix**:
1. Check `GITHUB_TOKEN` is set correctly: `echo $GITHUB_TOKEN`
2. Regenerate token on GitHub
3. Update environment variable

### HTTP 403: Resource not accessible by personal access token

**Cause**: Token lacks required permissions

**Fix**:
1. Check token permissions on GitHub (Settings → Developer settings → Personal access tokens)
2. Verify **Actions: Read** and **Contents: Read** are enabled
3. Regenerate token if needed

### HTTP 404: Not Found

**Causes**:
1. Run ID doesn't exist
2. Repository is private and token doesn't have access
3. Token is scoped to specific repositories and this repo isn't included

**Fix**:
1. Verify run ID is correct (check URL: `https://github.com/owner/repo/actions/runs/12345`)
2. If private repo, ensure token has access
3. If using repository-scoped token, add the repository to token access

### HTTP 410: Logs are no longer available

**Cause**: Logs older than 90 days

**Fix**: No fix — logs are permanently deleted. Pipeline Doctor will continue with available metadata.

### X-RateLimit-Remaining: 0

**Cause**: Rate limit exceeded

**Fix**:
1. Wait until rate limit resets (check `X-RateLimit-Reset` header)
2. Use authenticated token (5,000/hour vs 60/hour)
3. Increase `max_requests` limit on `GitHubClient` to catch earlier

---

## Example: Testing Token Manually

```bash
# Set token
export GITHUB_TOKEN="ghp_..."

# Test run metadata
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github+json" \
     https://api.github.com/repos/owner/repo/actions/runs/12345

# Test job list
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github+json" \
     https://api.github.com/repos/owner/repo/actions/runs/12345/jobs

# Test workflow file
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github+json" \
     "https://api.github.com/repos/owner/repo/contents/.github/workflows/ci.yml?ref=abc123"
```

---

## Next Steps

- **[xAI API Key Setup](xai-api-key.md)** — Get an xAI API key for Grok
- **[Configuration](configuration.md)** — Learn about all configuration options
- **[Usage Guide](usage.md)** — Run your first diagnosis
- **[Troubleshooting](troubleshooting.md)** — Common errors and fixes
