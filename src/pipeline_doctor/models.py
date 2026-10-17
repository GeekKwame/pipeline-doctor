"""Pydantic models for Pipeline Doctor incident reports."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class GitHubConclusion(str, Enum):
    """GitHub Actions run conclusions."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"
    NEUTRAL = "neutral"
    STARTUP_FAILURE = "startup_failure"


class FailureCategory(str, Enum):
    """Failure categories."""

    BUILD_FAILURE = "build_failure"
    TEST_FAILURE = "test_failure"
    DEPENDENCY_FAILURE = "dependency_failure"
    CONFIGURATION_ERROR = "configuration_error"
    PERMISSION_ERROR = "permission_error"
    TIMEOUT = "timeout"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    EXTERNAL_SERVICE_FAILURE = "external_service_failure"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class StepStatus(str, Enum):
    """GitHub Actions step statuses."""

    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    QUEUED = "queued"
    PENDING = "pending"
    WAITING = "waiting"
    REQUESTED = "requested"


class ConfidenceLevel(str, Enum):
    """Confidence levels for diagnosis."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    INSUFFICIENT = "insufficient"


class EvidenceType(str, Enum):
    """Types of evidence."""

    LOG = "log"
    WORKFLOW_YAML = "workflow_yaml"
    SOURCE_FILE = "source_file"
    DEPENDENCY_MANIFEST = "dependency_manifest"
    TEST_RESULT = "test_result"
    API_RESPONSE = "api_response"
    OTHER = "other"


class ChangeType(str, Enum):
    """Types of changes in proposed patches."""

    FIX = "fix"
    CONFIGURATION = "configuration"
    DEPENDENCY_UPDATE = "dependency_update"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"
    NONE = "none"


class RiskLevel(str, Enum):
    """Risk levels for proposed patches."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VerificationStatus(str, Enum):
    """Verification statuses."""

    NOT_RUN = "not_run"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"


class Incident(BaseModel):
    """Metadata about the CI/CD incident."""

    repository: str = Field(..., pattern=r"^[^/]+/[^/]+$")
    run_id: int = Field(..., ge=1)
    run_url: str
    commit_sha: str = Field(..., pattern=r"^[a-f0-9]{40}$")
    branch: str
    workflow_name: str
    workflow_path: str
    event: str
    triggered_at: Optional[datetime] = None
    conclusion: GitHubConclusion

    model_config = {"extra": "forbid"}


class Job(BaseModel):
    """Job information."""

    name: str
    id: int
    url: Optional[str] = None

    model_config = {"extra": "forbid"}


class FailedStep(BaseModel):
    """Step that failed."""

    name: str
    number: int = Field(..., ge=1)
    status: StepStatus

    model_config = {"extra": "forbid"}


class Location(BaseModel):
    """Source code location related to failure."""

    path: str
    start_line: int = Field(..., ge=1)
    end_line: int = Field(..., ge=1)
    evidence_ids: List[str]

    model_config = {"extra": "forbid"}

    @field_validator("end_line")
    @classmethod
    def validate_line_range(cls, v: int, info) -> int:
        """Ensure end_line >= start_line."""
        if "start_line" in info.data and v < info.data["start_line"]:
            raise ValueError("end_line must be >= start_line")
        return v


class Failure(BaseModel):
    """Details about the failure."""

    category: FailureCategory
    summary: str
    job: Optional[Job] = None
    failed_step: FailedStep
    locations: List[Location]

    model_config = {"extra": "forbid"}


class AlternativeHypothesis(BaseModel):
    """Alternative explanation for the failure."""

    description: str
    evidence_ids: List[str]
    likelihood: str

    model_config = {"extra": "forbid"}


class Diagnosis(BaseModel):
    """Root cause analysis and diagnosis."""

    root_cause: str
    technical_explanation: str
    observed_facts: List[str]
    inferences: List[str]
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    supporting_evidence_ids: List[str]
    primary_vs_cascading: str
    alternative_hypotheses: List[AlternativeHypothesis]

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_confidence_consistency(self) -> "Diagnosis":
        """Validate confidence score matches confidence_level."""
        confidence = self.confidence
        level = self.confidence_level

        if confidence >= 0.8 and level not in [ConfidenceLevel.HIGH]:
            raise ValueError(f"Confidence {confidence} should have 'high' level, got {level}")
        elif 0.5 <= confidence < 0.8 and level not in [ConfidenceLevel.MEDIUM]:
            raise ValueError(f"Confidence {confidence} should have 'medium' level, got {level}")
        elif confidence < 0.5 and level not in [ConfidenceLevel.LOW, ConfidenceLevel.INSUFFICIENT]:
            raise ValueError(f"Confidence {confidence} should have 'low' or 'insufficient' level, got {level}")

        return self


class Evidence(BaseModel):
    """Evidence item."""

    id: str
    type: EvidenceType
    source: str
    location: str
    log_excerpt: Optional[str] = None
    observation: str
    supports: str

    model_config = {"extra": "forbid"}


class Risk(BaseModel):
    """Risk assessment for proposed patch."""

    level: RiskLevel
    description: str

    model_config = {"extra": "forbid"}


class ProposedPatch(BaseModel):
    """Proposed fix for the issue."""

    available: bool
    target_files: List[str]
    change_type: ChangeType
    unified_diff: Optional[str] = None
    rationale: str
    risk: Risk
    requires_human_approval: bool
    applied: bool = False
    tested: bool = False

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_patch_consistency(self) -> "ProposedPatch":
        """Validate patch fields are consistent."""
        if self.available and not self.requires_human_approval:
            raise ValueError("requires_human_approval must be true when patch is available")

        if self.available and not self.target_files:
            raise ValueError("target_files must be provided when patch is available")

        if self.available and self.unified_diff is None:
            raise ValueError("unified_diff should be provided when patch is available")

        return self


class VerificationStep(BaseModel):
    """Verification step."""

    description: str
    command: Optional[str] = None
    expected_result: str

    model_config = {"extra": "forbid"}


class Verification(BaseModel):
    """Verification status and steps."""

    status: VerificationStatus
    steps: List[VerificationStep]
    verified_at: Optional[datetime] = None
    executed_by: Optional[str] = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_verification_consistency(self) -> "Verification":
        """Ensure verification status matches execution state."""
        if self.status != VerificationStatus.NOT_RUN:
            if self.verified_at is None or self.executed_by is None:
                raise ValueError(
                    f"verified_at and executed_by must be set when status is {self.status}"
                )
        return self


class IncidentReport(BaseModel):
    """Complete incident report."""

    schema_version: str = Field(..., pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    incident: Incident
    failure: Failure
    diagnosis: Diagnosis
    evidence: List[Evidence]
    proposed_patch: ProposedPatch
    verification: Verification
    limitations: List[str]

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_evidence_references(self) -> "IncidentReport":
        """Validate all evidence IDs are unique and all references exist."""
        evidence_ids = {e.id for e in self.evidence}

        if len(evidence_ids) != len(self.evidence):
            raise ValueError("Evidence IDs must be unique")

        all_referenced_ids = set()

        for loc in self.failure.locations:
            all_referenced_ids.update(loc.evidence_ids)

        all_referenced_ids.update(self.diagnosis.supporting_evidence_ids)

        for hyp in self.diagnosis.alternative_hypotheses:
            all_referenced_ids.update(hyp.evidence_ids)

        missing_ids = all_referenced_ids - evidence_ids
        if missing_ids:
            raise ValueError(f"Referenced evidence IDs not found: {missing_ids}")

        if not self.diagnosis.supporting_evidence_ids:
            raise ValueError("Root cause must have supporting evidence")

        return self

    @model_validator(mode="after")
    def validate_insufficient_evidence_category(self) -> "IncidentReport":
        """Validate insufficient_evidence category forces low/insufficient confidence."""
        if self.failure.category == FailureCategory.INSUFFICIENT_EVIDENCE:
            if self.diagnosis.confidence_level not in [
                ConfidenceLevel.LOW,
                ConfidenceLevel.INSUFFICIENT,
            ]:
                raise ValueError(
                    "insufficient_evidence category requires low or insufficient confidence level"
                )
        return self

    @model_validator(mode="after")
    def validate_verification_vs_patch_state(self) -> "IncidentReport":
        """Ensure patch tested/applied state aligns with verification."""
        if self.verification.status == VerificationStatus.NOT_RUN:
            if self.proposed_patch.tested or self.proposed_patch.applied:
                raise ValueError(
                    "Patch cannot be tested or applied when verification status is not_run"
                )
        return self
