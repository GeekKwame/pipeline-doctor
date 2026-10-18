# Getting Started

This guide walks you through installing Pipeline Doctor, running the tests, and executing your first diagnosis.

## Prerequisites

- **Python 3.11 or later** (tested with Python 3.11 and 3.12)
- `pip` (Python package installer)
- `git` (for cloning the repository)

Check your Python version:

```bash
python3 --version
# Expected: Python 3.11.x or Python 3.12.x
```

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/GeekKwame/pipeline-doctor.git
cd pipeline-doctor
```

### 2. Create a Virtual Environment

Using a virtual environment isolates dependencies from your system Python.

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install the Package

Install Pipeline Doctor with development dependencies:

```bash
pip install -e ".[dev]"
```

This installs:
- **Pipeline Doctor** in editable mode (changes to source code are immediately reflected)
- **pytest** for running tests
- **jsonschema** for schema validation

**Expected output**: You should see successful installation of `pipeline-doctor`, `pydantic`, `requests`, `pytest`, and `jsonschema`.

## Run the Tests

Verify your installation by running the test suite:

```bash
pytest
```

**Expected result**: All tests should pass. As of the last run, there are 155 tests covering:
- GitHub API client (real and fake)
- Grok AI client (mocked)
- Evidence collection
- Secret redaction
- Validation
- Orchestration

**Note**: One test (`test_redirect_same_host_keeps_auth_header`) may show a resource warning about unclosed sockets. This is a test cleanup issue and does not affect functionality.

### Run Tests with Verbose Output

```bash
pytest -v
```

### Run Tests Treating Warnings as Errors

```bash
pytest -W error
```

**Note**: With `-W error`, the socket cleanup warning will cause the test run to fail, but 154/155 tests pass.

## Run the CLI Example

The `examples/diagnose_run.py` script demonstrates a complete diagnosis workflow.

### Using Fake Grok (No API Key Required)

Test the entire pipeline without making real API calls:

```bash
python3 examples/diagnose_run.py --fake owner/repo 12345
```

Replace `owner/repo` with any GitHub repository and `12345` with any workflow run ID. Without a `GITHUB_TOKEN`, you'll see a warning about logs being unavailable, but the script will still attempt to fetch public data.

**Example output**:
```
Warning: GITHUB_TOKEN not set. Using unauthenticated GitHub access.
         Job logs may be unavailable.

Using fake Grok client (--fake flag)

Diagnosing workflow run: owner/repo run_id=12345
Grok client: fake

Collecting evidence...

✅ Diagnosis successful!
Root cause: Test failure
Confidence: medium
Evidence items: 2
API requests made: 3

--- Full Report (JSON) ---
{
  "schema_version": "1.0.0",
  "incident": { ... },
  ...
}
```

### Using Real Grok (Requires API Key)

Set your xAI API key and GitHub token:

```bash
export GROK_API_KEY="xai-..."
export GITHUB_TOKEN="ghp_..."
```

Then run against a real failed workflow:

```bash
python3 examples/diagnose_run.py owner/repo 12345
```

**Note**: The real Grok integration has NOT been verified against the live xAI API due to lack of credits. The script will work, but the xAI API response format is unverified.

## Validate the Example Report

The repository includes a valid example incident report. Validate it:

```bash
python3 -c "
import json
from pipeline_doctor.validator import IncidentReportValidator

with open('examples/example-incident-report.json') as f:
    report = json.load(f)

result = IncidentReportValidator().validate(report)

if result.success:
    print('✅ Example report is valid!')
    print(f'   Root cause: {result.report.diagnosis.root_cause}')
    print(f'   Confidence: {result.report.diagnosis.confidence_level}')
    print(f'   Evidence items: {len(result.report.evidence)}')
else:
    print('❌ Validation failed:')
    for error in result.errors:
        print(f'  - {error}')
"
```

**Expected output**:
```
✅ Example report is valid!
   Root cause: Missing AUTH_SECRET_KEY environment variable in workflow configuration
   Confidence: high
   Evidence items: 5
```

## Test Against a Real GitHub Actions Run

To test against a real workflow run, you need:

1. A **GitHub personal access token** (see [GitHub Token Setup](github-token.md))
2. A **failed GitHub Actions run** in a repository you have access to

### Find a Run ID

Navigate to a failed workflow run on GitHub. The run ID is in the URL:

```
https://github.com/owner/repo/actions/runs/12345678
                                             ^^^^^^^^
                                             Run ID
```

### Run Diagnosis

```bash
export GITHUB_TOKEN="ghp_..."

# Using fake Grok (safe for testing)
python3 examples/diagnose_run.py --fake owner/repo 12345678

# Using real Grok (requires xAI credits)
export GROK_API_KEY="xai-..."
python3 examples/diagnose_run.py owner/repo 12345678
```

## Next Steps

- **[Configuration](configuration.md)** — Learn about all configuration options
- **[GitHub Token Setup](github-token.md)** — Create a fine-grained read-only token
- **[xAI API Key Setup](xai-api-key.md)** — Get an xAI API key and credits
- **[Usage Guide](usage.md)** — Detailed usage examples and workflows
- **[Troubleshooting](troubleshooting.md)** — Common errors and solutions

## Troubleshooting

### ImportError: No module named 'pipeline_doctor'

Make sure you installed the package:

```bash
pip install -e ".[dev]"
```

### pytest: command not found

Activate the virtual environment:

```bash
source venv/bin/activate
```

### Permission denied: GITHUB_TOKEN

Double-check your token has the required permissions. See [GitHub Token Setup](github-token.md).

### HTTP 404: Not Found

The run ID does not exist or you don't have access to the repository. Use a public repository or set a valid `GITHUB_TOKEN`.

### Rate limit exceeded

GitHub's unauthenticated rate limit is 60 requests/hour. Authenticated requests get 5,000/hour. Set `GITHUB_TOKEN` to avoid rate limits.

For more detailed troubleshooting, see [Troubleshooting](troubleshooting.md).
