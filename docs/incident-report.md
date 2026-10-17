# Incident Report Schema Documentation

Comprehensive documentation for the Pipeline Doctor incident report format.

## Schema Version

The schema follows JSON Schema Draft 2020-12 and is versioned semantically. Current version: `1.0.0`

## Top-Level Structure

```json
{
  "schema_version": "1.0.0",
  "incident": { ... },
  "failure": { ... },
  "diagnosis": { ... },
  "evidence": [ ... ],
  "proposed_patch": { ... },
  "verification": { ... },
  "limitations": [ ... ]
}
```

All top-level fields are required. `additionalProperties: false` is enforced throughout.

## Field Descriptions

### `schema_version`

**Type**: String (semantic version pattern `X.Y.Z`)

Version of the incident report schema. Allows consumers to handle format changes.

### `incident`

**Type**: Object

Metadata about the GitHub Actions workflow run that failed.

**Fields**:

- `repository` (string, required): Repository in `owner/name` format
- `run_id` (integer, required): GitHub Actions run ID (minimum: 1)
- `run_url` (string, required): Full URL to the workflow run
- `commit_sha` (string, required): Git commit SHA (exactly 40 hex characters)
- `branch` (string, required): Branch name
- `workflow_name` (string, required): Human-readable workflow name
- `workflow_path` (string, required): Path to workflow file (e.g., `.github/workflows/ci.yml`)
- `event` (string, required): GitHub event that triggered the workflow (e.g., `push`, `pull_request`)
- `triggered_at` (string or null, required): ISO 8601 timestamp when triggered
- `conclusion` (enum, required): GitHub Actions conclusion status

**Valid `conclusion` values**:
- `success`
- `failure`
- `cancelled`
- `skipped`
- `timed_out`
- `action_required`
- `neutral`
- `startup_failure`

### `failure`

**Type**: Object

Details about what failed in the workflow.

**Fields**:

- `category` (enum, required): High-level failure category
- `summary` (string, required): Brief human-readable summary
- `job` (object or null, required): Information about the failed job
  - `name` (string): Job name
  - `id` (integer): Job ID
  - `url` (string or null): URL to the job
- `failed_step` (object, required): The step that failed
  - `name` (string): Step name
  - `number` (integer, minimum 1): Step number in job
  - `status` (enum): Step status
- `locations` (array, required): Source code locations related to failure
  - `path` (string): File path
  - `start_line` (integer, minimum 1): Starting line number
  - `end_line` (integer, minimum 1): Ending line number (must be >= start_line)
  - `evidence_ids` (array of strings): Evidence IDs supporting this location

**Valid `category` values**:
- `build_failure` - Compilation or build process failed
- `test_failure` - Tests did not pass
- `dependency_failure` - Package installation or dependency issues
- `configuration_error` - Workflow or tool configuration problem
- `permission_error` - Access or authentication issues
- `timeout` - Operation exceeded time limit
- `infrastructure_failure` - Runner or infrastructure problem
- `external_service_failure` - Third-party service unavailable
- `insufficient_evidence` - Cannot determine root cause

**Valid `step.status` values**: `completed`, `in_progress`, `queued`, `pending`, `waiting`, `requested`

### `diagnosis`

**Type**: Object

Root cause analysis and diagnostic findings.

**Fields**:

- `root_cause` (string, required): The primary root cause
- `technical_explanation` (string, required): Detailed technical explanation
- `observed_facts` (array of strings, required): Direct observations from evidence
- `inferences` (array of strings, required): Logical conclusions drawn from facts
- `confidence` (number, required): Confidence score (0.0 to 1.0)
- `confidence_level` (enum, required): Categorical confidence level
- `supporting_evidence_ids` (array of strings, required): Evidence IDs (must not be empty)
- `primary_vs_cascading` (string, required): Analysis of whether this is primary or cascading
- `alternative_hypotheses` (array, required): Alternative explanations considered
  - `description` (string): Description of alternative
  - `evidence_ids` (array of strings): Supporting evidence
  - `likelihood` (string): Likelihood assessment

**Valid `confidence_level` values and thresholds**:
- `high`: confidence >= 0.8 (strong evidence, clear root cause)
- `medium`: 0.5 <= confidence < 0.8 (reasonable evidence with some ambiguity)
- `low`: confidence < 0.5 (limited evidence or multiple plausible causes)
- `insufficient`: Not enough information (typically with `insufficient_evidence` category)

**Important**: Confidence is an **uncalibrated heuristic**, not a statistical probability. It represents the AI's assessment based on available evidence, not a rigorous probability estimate.

**Validation rules**:
- Confidence score must match confidence level thresholds
- `insufficient_evidence` category forces `low` or `insufficient` level
- `supporting_evidence_ids` must not be empty
- All referenced evidence IDs must exist in the `evidence` array

### `evidence`

**Type**: Array of objects

Collection of evidence items with unique identifiers.

**Each evidence item**:

- `id` (string, required): Unique identifier (e.g., `E1`, `E2`)
- `type` (enum, required): Type of evidence
- `source` (string, required): Where the evidence came from
- `location` (string, required): Location or path to evidence
- `log_excerpt` (string or null, required): Relevant log excerpt (null if not applicable)
- `observation` (string, required): What was observed
- `supports` (string, required): What this evidence supports

**Valid `type` values**:
- `log` - Job or step logs
- `workflow_yaml` - Workflow configuration
- `source_file` - Source code file
- `dependency_manifest` - Package manifest (requirements.txt, package.json, etc.)
- `test_result` - Test output or results
- `api_response` - API response data
- `other` - Other evidence

**Evidence Traceability**:
- Every evidence ID must be unique
- All referenced IDs in `diagnosis.supporting_evidence_ids`, `failure.locations[].evidence_ids`, and `diagnosis.alternative_hypotheses[].evidence_ids` must exist
- Root cause must have at least one supporting evidence ID

### `proposed_patch`

**Type**: Object

Proposed fix for the identified issue.

**Fields**:

- `available` (boolean, required): Whether a patch is available
- `target_files` (array of strings, required): Files to be modified (empty if no patch)
- `change_type` (enum, required): Type of change
- `unified_diff` (string or null, required): Unified diff of changes (null if unavailable)
- `rationale` (string, required): Explanation of why this fixes the issue
- `risk` (object, required): Risk assessment
  - `level` (enum): Risk level (`low`, `medium`, `high`)
  - `description` (string): Risk description
- `requires_human_approval` (boolean, required): Whether human approval is required
- `applied` (boolean, optional, default false): Whether patch has been applied
- `tested` (boolean, optional, default false): Whether patch has been tested

**Valid `change_type` values**:
- `fix` - Bug fix or error correction
- `configuration` - Configuration file change
- `dependency_update` - Update dependencies
- `refactor` - Code refactoring
- `documentation` - Documentation change
- `none` - No patch available

**Validation rules**:
- If `available` is true, `requires_human_approval` must be true (safety requirement)
- If `available` is true, `target_files` must not be empty
- If `available` is true, `unified_diff` should be provided (null only when truly unavailable)
- `tested` or `applied` cannot be true if `verification.status` is `not_run`
- Target files should exist in the repository (validated if known files provided)

### `verification`

**Type**: Object

Verification status and steps for testing the proposed fix.

**Fields**:

- `status` (enum, required): Verification status
- `steps` (array, required): Verification steps to execute
  - `description` (string): Step description
  - `command` (string or null): Command to run (null for manual steps)
  - `expected_result` (string): Expected outcome
- `verified_at` (string or null, required): ISO 8601 timestamp when verified
- `executed_by` (string or null, required): Who executed verification

**Valid `status` values**:
- `not_run` - Not yet verified (initial state)
- `passed` - Verification passed
- `failed` - Verification failed
- `partial` - Partial verification

**Validation rules**:
- If `status` is not `not_run`, both `verified_at` and `executed_by` must be set
- Initial reports should always have `status: "not_run"` with null timestamps
- Verification happens externally; the diagnosis pipeline never sets status to passed/failed/partial

### `limitations`

**Type**: Array of strings

Limitations and caveats about the analysis.

**Common limitation types**:
- Missing or inaccessible logs
- Unavailable workflow files
- Cannot access certain source files
- Incomplete evidence
- External dependencies not analyzed
- Assumptions made due to missing information

**Purpose**: Provides transparency about what the analysis could not cover and where uncertainty exists.

## Design Rationale

### Schema Design Choices

**Why JSON Schema Draft 2020-12?**
- Modern, well-supported standard
- Strong validation capabilities
- `additionalProperties: false` prevents silent data corruption

**Why Pydantic v2?**
- Runtime validation
- Type safety
- Cross-field validation (e.g., evidence ID references)
- Excellent error messages

**Why separate observed_facts and inferences?**
- Transparency: distinguishes direct evidence from logical conclusions
- Traceability: makes reasoning explicit
- Confidence: helps assess diagnosis reliability

**Why confidence as uncalibrated heuristic?**
- Honest: not claiming statistical rigor
- Useful: still provides relative certainty indicator
- Thresholds: documented boundaries for interpretation

**Why requires_human_approval always true?**
- Safety: prevents automatic code changes
- Trust: maintains human oversight
- Liability: clear responsibility chain

### Security Considerations

**Secret Redaction**:
- Applied before sending to AI
- Applied to final report
- Comprehensive pattern matching
- High-entropy detection

**Commit SHA Pinning**:
- All file fetches use the same SHA
- Prevents race conditions
- Ensures consistency

**Untrusted Data**:
- Prompt treats all repo content as potentially malicious
- Delimited blocks prevent prompt injection
- No embedded instructions followed

**No Automatic Execution**:
- Commands in verification steps are documentation only
- Patches require explicit human application
- No side effects from report generation

## Examples

See `examples/example-incident-report.json` for a complete, valid incident report.

The example is clearly marked as illustrative with fictional data and demonstrates:
- All required fields
- Proper evidence traceability
- Confidence scoring
- Alternative hypotheses
- Patch proposal with risk assessment
- Verification steps
- Honest limitations

## Validation

Use the provided validator to ensure reports are valid:

```python
from pipeline_doctor.validator import IncidentReportValidator

validator = IncidentReportValidator(
    known_files={"src/main.py", "tests/test_main.py"},
    file_line_counts={"src/main.py": 150}
)

result = validator.validate(report_data)
if result.success:
    print("Valid report!")
else:
    print("Errors:", result.errors)
```

Validation checks:
- Schema compliance
- Evidence ID uniqueness and references
- Confidence score/level consistency
- Patch consistency (approval, files, diff)
- Verification state consistency
- Line ranges within file bounds (if line counts provided)
- Files exist in repository (if known files provided)

## Future Extensions

Potential schema additions (would bump version):
- Performance metrics (runtime, resource usage)
- Historical failure correlation
- Suggested repository improvements
- Related issues/PRs
- Estimated fix effort
