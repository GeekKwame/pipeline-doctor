# Pipeline Doctor

AI-powered GitHub Actions troubleshooting bot - incident report core library.

## Overview

Pipeline Doctor is a standalone Python library that analyzes GitHub Actions workflow failures and generates comprehensive, structured incident reports. It uses AI (Grok) to diagnose issues, identify root causes, and propose fixes.

This is the **incident report core** - a standalone library providing diagnosis and reporting capabilities. It is **NOT yet integrated** into any production bot or automation system.

## Features

- **Structured Incident Reports**: JSON Schema Draft 2020-12 compliant reports
- **Evidence-Based Diagnosis**: Collects and analyzes logs, workflow YAML, and source files
- **Root Cause Analysis**: Distinguishes primary failures from cascading effects
- **Confidence Scoring**: Uncalibrated heuristic confidence levels (high/medium/low/insufficient)
- **Security-First**: Automatic secret redaction before AI processing
- **Validation**: Comprehensive Pydantic v2 models with cross-field validation
- **Safety**: AI-generated fixes require human approval; nothing executes automatically

## Requirements

- Python 3.11+
- Pydantic v2
- requests (for Grok API)

## Installation

```bash
pip install -e .
```

For development with testing:

```bash
pip install -e ".[dev]"
```

## Quick Start

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
github = GitHubClient(token=os.environ["GITHUB_TOKEN"])
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

if result.success:
    print("Root cause:", result.report.diagnosis.root_cause)
    print("Confidence:", result.report.diagnosis.confidence_level)
else:
    print("Errors:", result.errors)
```

## Schema

The incident report schema is defined in `schemas/incident-report.schema.json` (JSON Schema Draft 2020-12).

See `docs/incident-report.md` for detailed field descriptions.

## Testing

Run tests with pytest:

```bash
pytest
```

All tests use deterministic fixtures and mocked dependencies - no network calls or credentials required.

## Security

**Secret Redaction**: Automatically redacts:
- GitHub tokens (ghp_, gho_, ghs_, github_pat_)
- AWS keys (AKIA..., aws_secret_access_key)
- Bearer tokens
- Private keys (PEM blocks)
- Password/token/secret assignments
- JWTs
- ::add-mask:: values
- High-entropy strings (potential credentials)

**Size Limits**:
- Logs truncated to 100KB (keeping context around errors)
- Source files truncated to 50KB
- Maximum 20 files fetched
- Maximum 50 API requests

**Safety**:
- AI-generated commands are never executed automatically
- Proposed patches always require human approval
- All repo content and logs treated as untrusted data in prompts

## Integration Status

### What Works

- ✅ Standalone library with full validation
- ✅ Protocol-based dependency injection
- ✅ Fake clients for testing
- ✅ Evidence collection pipeline
- ✅ Grok prompt template
- ✅ Comprehensive validation

### What's NOT Integrated Yet

- ❌ Production bot/automation workflow
- ❌ GitHub App integration
- ❌ Webhook handlers
- ❌ Automated PR creation with fixes

### GitHub API Integration

✅ **Real GitHub client implemented** (`GitHubClient` in `src/pipeline_doctor/github_client.py`)

**Features**:
- Read-only operations (GET requests only)
- Token from environment variable or constructor
- Token redaction from error messages
- Rate limit handling (403/429 with reset headers)
- 404 handling for missing resources
- Log download with redirect/zip handling
- Commit SHA pinning for file fetches
- Request budget enforcement (max 50 requests)

**GitHub REST API endpoints used**:
- `GET /repos/{owner}/{repo}/actions/runs/{run_id}` - Get workflow run
- `GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs` - List jobs
- `GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs` - Download logs
- `GET /repos/{owner}/{repo}/contents/{path}?ref={sha}` - Get file at commit

**Authentication**: Read-only personal access token with `repo` or `actions:read` scope.

**Testing status**: Comprehensive tests with mocked HTTP (no network calls). Tests cover success paths, 404s, rate limiting, log redirects/zip, token redaction, request budget, and verification that no write methods exist.

**CLI Example**: See `examples/diagnose_run.py` for a working example that runs diagnosis against real GitHub Actions runs.

**Testing**: For tests, use `FakeGitHubClient` from the same module, which implements the same protocol but uses in-memory test data.

### Grok API Integration

The `GrokAPIClient` in `src/pipeline_doctor/grok_client.py` is implemented but **untested with live API**.

Set environment variable:
```bash
export GROK_API_KEY="your-xai-api-key"
# or
export XAI_API_KEY="your-xai-api-key"
```

## Documentation

- `README.md` - This file
- `docs/incident-report.md` - Detailed schema and field documentation

## Example

See `examples/example-incident-report.json` for a complete, valid incident report (fictional data, marked illustrative).

## License

See repository for license information.

## Contributing

This is a standalone library. Contributions welcome for:
- Real GitHub API client implementation
- Additional evidence collectors
- Improved redaction patterns
- Enhanced validation rules
