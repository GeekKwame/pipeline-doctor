# Usage Guide

This guide explains how to run diagnoses, read incident reports, and work through an end-to-end example.

## Basic Usage

### Running a Diagnosis via CLI

The simplest way to diagnose a GitHub Actions failure:

```bash
export GITHUB_TOKEN="ghp_..."
export GROK_API_KEY="xai-..."

python3 examples/diagnose_run.py owner/repo 12345
```

Replace:
- `owner/repo` with the repository name
- `12345` with the workflow run ID

### Finding a Run ID

The run ID is in the GitHub Actions URL:

```
https://github.com/owner/repo/actions/runs/12345678901
                                             ^^^^^^^^^^^
                                             Run ID
```

**Example**: For `https://github.com/facebook/react/actions/runs/12345678`, the run ID is `12345678`.

### CLI Output

The script writes diagnostic messages to **stderr** and the JSON report to **stdout**.

**Successful diagnosis**:

```
Diagnosing workflow run: owner/repo run_id=12345
GitHub token: ********** (redacted)
Grok client: real

Collecting evidence...

✅ Diagnosis successful!
Root cause: Missing environment variable AUTH_SECRET_KEY
Confidence: high
Evidence items: 5
API requests made: 7

Limitations:
  - Workflow file not available

--- Full Report (JSON) ---

{
  "schema_version": "1.0.0",
  "incident": { ... },
  ...
}
```

**Failed diagnosis**:

```
❌ Diagnosis failed
Errors:
  - Could not determine commit SHA for the workflow run

Limitations:
  - Failed to fetch run metadata: HTTP 404: Not Found
```

### Saving the Report

Save JSON output to a file:

```bash
python3 examples/diagnose_run.py owner/repo 12345 > report.json
```

Diagnostic messages still go to stderr, only JSON goes to the file.

---

## Reading Incident Reports

### Report Structure

An incident report contains:

1. **Schema version**: `1.0.0` (semantic versioning)
2. **Incident metadata**: Repository, run ID, commit SHA, branch, event
3. **Failure details**: Category, summary, failed job, locations
4. **Diagnosis**: Root cause, explanation, confidence, evidence references
5. **Evidence**: Collected logs, YAML, source files with unique IDs
6. **Proposed patch**: Suggested fix with risk assessment (if available)
7. **Verification**: Steps to test the fix (not run by default)
8. **Limitations**: What data was unavailable

### Example: Reading Root Cause

```python
import json
from pipeline_doctor.validator import IncidentReportValidator

# Load report
with open("report.json") as f:
    data = json.load(f)

# Validate
validator = IncidentReportValidator()
result = validator.validate(data)

if result.success:
    report = result.report
    
    # Access diagnosis
    print(f"Root cause: {report.diagnosis.root_cause}")
    print(f"Confidence: {report.diagnosis.confidence_level}")
    print(f"Explanation: {report.diagnosis.technical_explanation}")
    
    # Access evidence
    print(f"\nEvidence items: {len(report.evidence)}")
    for evidence in report.evidence:
        print(f"  - {evidence.id}: {evidence.type} - {evidence.observation}")
    
    # Check proposed patch
    if report.proposed_patch.available:
        print(f"\nPatch available: {report.proposed_patch.change_type}")
        print(f"Risk: {report.proposed_patch.risk.level}")
        print(f"Files: {', '.join(report.proposed_patch.target_files)}")
    else:
        print(f"\nNo patch available: {report.proposed_patch.rationale}")
else:
    print(f"Validation failed: {result.errors}")
```

### Confidence Levels

| Level | Threshold | Meaning |
|-------|-----------|---------|
| `high` | ≥ 0.8 | Strong evidence, clear root cause |
| `medium` | 0.5 - 0.79 | Reasonable evidence, some ambiguity |
| `low` | < 0.5 | Limited evidence, multiple plausible causes |
| `insufficient` | — | Not enough information to diagnose |

**Note**: Confidence is an **uncalibrated heuristic**, not a statistical probability.

### Failure Categories

| Category | Description |
|----------|-------------|
| `build_failure` | Compilation or build process failed |
| `test_failure` | Tests did not pass |
| `dependency_failure` | Package installation or dependency issues |
| `configuration_error` | Workflow or tool configuration problem |
| `permission_error` | Access or authentication issues |
| `timeout` | Operation exceeded time limit |
| `infrastructure_failure` | Runner or infrastructure problem |
| `external_service_failure` | Third-party service unavailable |
| `insufficient_evidence` | Cannot determine root cause |

---

## End-to-End Walkthrough

This walkthrough uses a deliberately broken workflow to demonstrate the full diagnosis process.

### Step 1: Create a Broken Workflow

In a **throwaway test repository**:

1. Create `.github/workflows/test.yml`:

```yaml
name: Test Workflow
on: push

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install requests
      
      - name: Run script
        run: python script.py
```

2. Create `script.py` (missing environment variable):

```python
import os

secret_key = os.environ["SECRET_KEY"]  # Will fail: not set
print(f"Secret: {secret_key}")
```

3. Commit and push:

```bash
git add .github/workflows/test.yml script.py
git commit -m "Add broken workflow"
git push
```

4. The workflow will **fail** with `KeyError: 'SECRET_KEY'`.

### Step 2: Find the Run ID

Go to GitHub Actions → Failed run → Copy run ID from URL.

Example: `https://github.com/yourname/test-repo/actions/runs/12345678` → Run ID: `12345678`

### Step 3: Run Diagnosis

```bash
export GITHUB_TOKEN="ghp_..."
export GROK_API_KEY="xai-..."

python3 examples/diagnose_run.py yourname/test-repo 12345678 > diagnosis.json
```

**Expected output** (stderr):

```
Diagnosing workflow run: yourname/test-repo run_id=12345678
GitHub token: ********** (redacted)
Grok client: real

Collecting evidence...

✅ Diagnosis successful!
Root cause: Missing SECRET_KEY environment variable
Confidence: high
Evidence items: 3
API requests made: 5

--- Full Report (JSON) ---
```

### Step 4: Examine the Report

```bash
cat diagnosis.json | python3 -m json.tool | head -50
```

**Expected sections**:

- **Incident**: Repository, run ID, commit SHA, workflow path
- **Failure**: Category `configuration_error` or `test_failure`
- **Diagnosis**: Root cause mentions `SECRET_KEY`, confidence `high`
- **Evidence**: Logs showing `KeyError: 'SECRET_KEY'`, workflow YAML
- **Proposed patch**: May suggest adding `SECRET_KEY` to workflow environment

### Step 5: Review Proposed Patch

```python
import json

with open("diagnosis.json") as f:
    report = json.load(f)

patch = report["proposed_patch"]

if patch["available"]:
    print(f"Change type: {patch['change_type']}")
    print(f"Target files: {', '.join(patch['target_files'])}")
    print(f"\nRationale: {patch['rationale']}")
    print(f"\nRisk level: {patch['risk']['level']}")
    print(f"Risk: {patch['risk']['description']}")
    
    if patch["unified_diff"]:
        print(f"\n--- Proposed Changes ---")
        print(patch["unified_diff"])
else:
    print(f"No patch available: {patch['rationale']}")
```

**Example output**:

```
Change type: configuration
Target files: ['.github/workflows/test.yml']

Rationale: Add SECRET_KEY environment variable to workflow configuration

Risk level: low
Risk: Low risk; only adds configuration, no code changes

--- Proposed Changes ---
--- a/.github/workflows/test.yml
+++ b/.github/workflows/test.yml
@@ -15,5 +15,7 @@
       - name: Run script
         run: python script.py
+        env:
+          SECRET_KEY: ${{ secrets.SECRET_KEY }}
```

### Step 6: Apply the Fix (Manual)

**⚠️ Pipeline Doctor NEVER applies patches automatically.** You must review and apply manually.

1. Review the proposed diff
2. Edit `.github/workflows/test.yml` manually
3. Add `SECRET_KEY` to GitHub Secrets (Settings → Secrets → Actions)
4. Commit and push

```bash
# After manual edits:
git add .github/workflows/test.yml
git commit -m "Fix: Add SECRET_KEY to workflow"
git push
```

### Step 7: Verify the Fix

Run the workflow again and verify it passes.

---

## Testing Safely

### Use a Throwaway Repository

**Do NOT test on production repositories.** Create a dedicated test repo:

```bash
# Create a new test repository on GitHub
# Clone it locally
git clone https://github.com/yourname/pipeline-doctor-test
cd pipeline-doctor-test

# Add test workflow and broken code
# Commit and push to trigger failures
```

### Use Fake Grok for Testing

Test the entire pipeline without consuming xAI credits:

```bash
python3 examples/diagnose_run.py --fake owner/repo 12345
```

This uses fake evidence and a canned incident report, but verifies:
- GitHub API access
- Evidence collection
- Redaction
- Validation
- Report generation

---

## Programmatic Usage

### Full Example

```python
import os
from pathlib import Path
from pipeline_doctor.github_client import GitHubClient
from pipeline_doctor.grok_client import GrokAPIClient
from pipeline_doctor.evidence import EvidenceCollector
from pipeline_doctor.orchestrator import DiagnosisOrchestrator
from pipeline_doctor.prompts import PromptLoader
from pipeline_doctor.redaction import SecretRedactor, SizeLimiter
from pipeline_doctor.validator import IncidentReportValidator

# Set up components
github = GitHubClient(token=os.environ.get("GITHUB_TOKEN"))
grok = GrokAPIClient(api_key=os.environ.get("GROK_API_KEY"))
redactor = SecretRedactor()
limiter = SizeLimiter()

evidence_collector = EvidenceCollector(github, redactor, limiter)
prompt_loader = PromptLoader(Path("prompts"))
validator = IncidentReportValidator()

orchestrator = DiagnosisOrchestrator(
    evidence_collector,
    grok,
    prompt_loader,
    validator,
    redactor
)

# Run diagnosis
result = orchestrator.diagnose("owner", "repo", run_id=12345)

# Handle result
if result.success:
    report = result.report
    print(f"✅ Root cause: {report.diagnosis.root_cause}")
    print(f"   Confidence: {report.diagnosis.confidence_level}")
    
    # Save report
    import json
    with open("report.json", "w") as f:
        json.dump(report.model_dump(mode="json"), f, indent=2)
else:
    print(f"❌ Diagnosis failed")
    for error in result.errors:
        print(f"  - {error}")
    
    if result.limitations:
        print("\nLimitations:")
        for limitation in result.limitations:
            print(f"  - {limitation}")
```

### Fetching Additional Source Files

```python
# Diagnose with additional context
result = orchestrator.diagnose(
    "owner",
    "repo",
    run_id=12345,
    additional_files=[
        "src/main.py",
        "tests/test_main.py",
        "requirements.txt"
    ]
)
```

**Note**: Files are fetched at the commit SHA of the workflow run (pinned for consistency).

---

## Best Practices

### ✅ DO

- Test on throwaway repositories first
- Review proposed patches before applying
- Check confidence levels (low = uncertain)
- Read limitations (missing data reduces confidence)
- Store tokens securely (environment variables, secret managers)
- Monitor GitHub and xAI API usage

### ❌ DON'T

- Never apply patches automatically
- Never run on production without testing
- Don't ignore low-confidence diagnoses
- Don't commit API keys or tokens
- Don't trust AI-generated commands without review

---

## Common Scenarios

### Scenario 1: Logs Expired (> 90 Days)

**Symptom**: Limitation: `"Failed to fetch job logs: HTTP 410"`

**Impact**: Diagnosis will be based on run metadata and workflow YAML only. Confidence will be lower.

**Fix**: No fix — logs are permanently deleted. Use remaining evidence.

### Scenario 2: Private Repository Without Token

**Symptom**: Error: `"HTTP 404: Not Found"`

**Fix**: Set `GITHUB_TOKEN` with access to the repository.

### Scenario 3: Insufficient Evidence

**Diagnosis**:
- Category: `insufficient_evidence`
- Confidence: `low` or `insufficient`
- Root cause: Generic or uncertain

**Fix**: Check limitations field for what data was missing. Add `GITHUB_TOKEN` or wait until run is recent (<90 days).

### Scenario 4: False Positive Redaction

**Symptom**: Docker image names redacted as secrets (e.g., `node:14-alpine@sha256:abcd...`)

**Impact**: Some context lost, but diagnosis usually unaffected.

**Fix**: Known issue; no fix yet. See [Roadmap](roadmap.md).

---

## Next Steps

- **[Troubleshooting](troubleshooting.md)** — Common errors and fixes
- **[Security](security.md)** — Read-only guarantee, redaction, prompt injection
- **[Incident Report Schema](incident-report.md)** — Detailed schema documentation
- **[Roadmap](roadmap.md)** — Future features and known issues
