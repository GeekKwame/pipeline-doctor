# xAI API Key Setup

Pipeline Doctor uses xAI's Grok models for AI-powered failure diagnosis. This guide explains how to get an API key, set up credits, and choose a model.

## ⚠️ Important: Unverified Integration

**The Grok integration has NOT been verified against the live xAI API.** During development, the xAI account had no credits, so all testing used mocked HTTP responses. The API request format follows OpenAI conventions, but the actual xAI API behavior is unverified.

**Before production use**:
1. Verify model names with `GET /v1/models`
2. Test with small `max_tokens` to check truncation behavior
3. Test JSON mode (`response_format: "json_object"`) if using it
4. Verify error response formats (403, 429, 5xx)

---

## Getting an xAI API Key

### 1. Sign Up for xAI

Visit the xAI developer console:

https://console.x.ai/

Create an account or sign in with your existing credentials.

### 2. Generate an API Key

Navigate to **API Keys** section and click **Create API Key**.

- **Name**: `pipeline-doctor`
- **Description**: `AI-powered GitHub Actions failure diagnosis`

Copy the API key immediately — you won't see it again.

### 3. Save as Environment Variable

```bash
export GROK_API_KEY="xai-1234567890abcdefghijklmnopqrstuvwxyz"
```

Or use the alternative name:

```bash
export XAI_API_KEY="xai-1234567890abcdefghijklmnopqrstuvwxyz"
```

Add to your shell profile (`~/.bashrc`, `~/.zshrc`) or use a `.env` file (never commit to version control).

---

## Setting Up Credits

xAI uses a **pay-per-use** model with credits. You must have credits to make API requests.

### 1. Add Credits

In the xAI console:

1. Navigate to **Billing** → **Credits**
2. Click **Add Credits**
3. Choose an amount (start with $10-$20 for testing)
4. Complete payment

### 2. Check Current Pricing

Pricing varies by model and changes over time. Check the latest rates in the xAI console:

https://console.x.ai/pricing

**Do NOT rely on outdated pricing estimates.** Always check the console for current rates.

### 3. Monitor Usage

Track credit usage in the xAI console under **Usage** or **Billing**.

---

## Choosing a Model

Pipeline Doctor defaults to `"grok-beta"`, but this name is **unverified**.

### List Available Models

Use the xAI API to list available models:

```bash
curl -H "Authorization: Bearer $GROK_API_KEY" \
     https://api.x.ai/v1/models
```

**Expected response** (format may vary):

```json
{
  "object": "list",
  "data": [
    {
      "id": "grok-beta",
      "object": "model",
      "created": 1234567890,
      "owned_by": "xai"
    },
    {
      "id": "grok-2-latest",
      "object": "model",
      "created": 1234567890,
      "owned_by": "xai"
    }
  ]
}
```

### Set Model via Environment Variable

```bash
export GROK_MODEL="grok-2-latest"
```

### Set Model via Constructor

```python
from pipeline_doctor.grok_client import GrokAPIClient

client = GrokAPIClient(
    api_key="xai-...",
    model="grok-2-latest"
)
```

### Override Per Request

```python
response = client.chat_completion(
    system_prompt="...",
    user_message="...",
    model="grok-custom"
)
```

---

## Token Usage Estimates

These are **rough estimates** based on testing with fake data. Actual usage depends on log size and number of source files.

### Input Tokens (User + System Prompts)

| Component | Typical Size | Token Estimate |
|-----------|--------------|----------------|
| System prompt | ~2 KB | ~500 tokens |
| Run metadata | ~1 KB | ~250 tokens |
| Failed job metadata | ~500 bytes | ~125 tokens |
| Job logs (truncated) | ~100 KB | ~25,000 tokens |
| Workflow YAML | ~1-5 KB | ~250-1,250 tokens |
| Source files (0-5) | ~50 KB each | ~12,500 tokens each |
| Evidence index | ~500 bytes | ~125 tokens |

**Total input range**: **6,000 - 22,000 tokens** (varies widely)

**Factors that increase input**:
- Large log files (even after truncation)
- Multiple source files
- Long workflow YAML

**Reducing input**:
- Decrease `max_log_bytes` (default: 100,000)
- Decrease `max_file_bytes` (default: 50,000)
- Fetch fewer source files

### Output Tokens (Incident Report)

| Component | Typical Size | Token Estimate |
|-----------|--------------|----------------|
| Schema version | ~50 bytes | ~15 tokens |
| Incident metadata | ~500 bytes | ~125 tokens |
| Failure details | ~500 bytes | ~125 tokens |
| Diagnosis | ~1,000 bytes | ~250 tokens |
| Evidence (5 items) | ~2,000 bytes | ~500 tokens |
| Proposed patch | ~1,000 bytes | ~250 tokens |
| Verification | ~300 bytes | ~75 tokens |
| Limitations | ~200 bytes | ~50 tokens |

**Total output range**: **1,000 - 2,000 tokens**

**Factors that increase output**:
- Large unified diffs in proposed patches
- Many evidence items
- Detailed technical explanations

### Total Tokens per Diagnosis

**Estimated range**: **7,000 - 24,000 tokens**

**Cost estimate** (example, **not current pricing**):
- If 1M tokens = $10: ~$0.07 - $0.24 per diagnosis
- Check xAI console for actual pricing

---

## Error Handling

### HTTP 403: No Credits

When credits are exhausted:

**Symptom**:
```
GrokAPIError: API request failed with status 403: {"error": "Insufficient credits"}
```

**Fix**:
1. Add credits in xAI console (Billing → Add Credits)
2. Verify credits are available (Usage → Current Balance)
3. Retry diagnosis

### HTTP 401: Bad Credentials

**Cause**: API key is invalid or expired

**Fix**:
1. Check `GROK_API_KEY` is set correctly: `echo $GROK_API_KEY`
2. Regenerate API key in xAI console
3. Update environment variable

### HTTP 429: Rate Limited

**Cause**: Too many requests in a short time

**Fix**:
- **Wait**: xAI will return `Retry-After` header (in seconds)
- **Automatic**: `GrokAPIClient` retries with exponential backoff (1s, 2s, 4s, 8s)
- **Manual**: Wait and retry

**Note**: `max_retries` defaults to 3. Increase if needed:

```python
client = GrokAPIClient(api_key="xai-...", max_retries=5)
```

### HTTP 5xx: Server Error

**Cause**: xAI server error

**Fix**:
- **Automatic**: `GrokAPIClient` retries with exponential backoff
- **Manual**: Wait and retry

### Response Truncated (finish_reason: "length")

**Cause**: Response exceeds `max_tokens`

**Symptom**:
```
GrokAPIError: Response was truncated (finish_reason: length). Increase max_tokens.
```

**Fix**:
```python
response = client.chat_completion(
    system_prompt="...",
    user_message="...",
    max_tokens=8192  # Increase from default
)
```

### Model Not Found

**Cause**: Model name is invalid

**Symptom**:
```
GrokAPIError: API request failed with status 404: {"error": "Model not found"}
```

**Fix**:
1. List available models: `curl -H "Authorization: Bearer $GROK_API_KEY" https://api.x.ai/v1/models`
2. Update `GROK_MODEL` or use valid model name

---

## Testing Without Credits

Use the **fake Grok client** for testing without making real API calls:

```bash
python3 examples/diagnose_run.py --fake owner/repo 12345
```

Or programmatically:

```python
from pipeline_doctor.grok_client import FakeGrokClient

client = FakeGrokClient()
```

The fake client returns a minimal valid incident report without calling the xAI API.

---

## Security Best Practices

### ✅ DO

- Store API keys in **environment variables** or secret managers
- Rotate API keys regularly
- Monitor usage and set budget alerts in xAI console
- Use separate keys for dev/staging/prod

### ❌ DON'T

- Never commit API keys to version control
- Never share API keys in chat, email, or logs
- Don't hardcode API keys in source code

---

## Verifying Your Setup

### 1. Test API Key

```bash
curl -H "Authorization: Bearer $GROK_API_KEY" \
     https://api.x.ai/v1/models
```

**Expected**: List of available models

**If 401**: API key is invalid

**If 403**: No credits or access denied

### 2. Test Chat Completion (Manual)

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
    "temperature": 0.1
  }'
```

**Expected**: JSON response with `choices[0].message.content`

### 3. Test with Pipeline Doctor

```bash
export GROK_API_KEY="xai-..."
python3 examples/diagnose_run.py owner/repo 12345
```

**Note**: This will consume credits. Use `--fake` for testing without credits.

---

## Troubleshooting

### No credits warning on real Grok call

**Symptom**: `HTTP 403` with message about credits

**Fix**: Add credits in xAI console

### Model name rejected

**Symptom**: `HTTP 404` or `Model not found`

**Fix**: List models with `GET /v1/models` and use a valid name

### Timeout errors

**Symptom**: `GrokAPIError: Request timeout`

**Fix**: Increase timeouts:

```python
client = GrokAPIClient(
    api_key="xai-...",
    connect_timeout=60.0,
    read_timeout=180.0
)
```

### API key in error messages

**Protection**: `GrokAPIClient` automatically redacts API keys from error messages

**Verify**: Check that errors show `[REDACTED-API-KEY]` instead of the real key

---

## Next Steps

- **[Configuration](configuration.md)** — Learn about all Grok client options
- **[Usage Guide](usage.md)** — Run your first diagnosis
- **[Troubleshooting](troubleshooting.md)** — Common Grok errors and fixes
- **[Roadmap](roadmap.md)** — Status of live Grok verification
