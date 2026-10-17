"""Tests for Pydantic models."""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from pipeline_doctor.models import (
    ChangeType,
    ConfidenceLevel,
    Diagnosis,
    Evidence,
    EvidenceType,
    FailedStep,
    Failure,
    FailureCategory,
    GitHubConclusion,
    Incident,
    IncidentReport,
    Job,
    Location,
    ProposedPatch,
    Risk,
    RiskLevel,
    StepStatus,
    Verification,
    VerificationStatus,
)


def test_valid_incident():
    """Test valid incident model."""
    incident = Incident(
        repository="owner/repo",
        run_id=123,
        run_url="https://github.com/owner/repo/actions/runs/123",
        commit_sha="a" * 40,
        branch="main",
        workflow_name="CI",
        workflow_path=".github/workflows/ci.yml",
        event="push",
        triggered_at=datetime.now(),
        conclusion=GitHubConclusion.FAILURE,
    )
    assert incident.repository == "owner/repo"
    assert incident.commit_sha == "a" * 40


def test_invalid_repository_format():
    """Test invalid repository format."""
    with pytest.raises(ValidationError) as exc_info:
        Incident(
            repository="invalid-repo",
            run_id=123,
            run_url="https://github.com/owner/repo/actions/runs/123",
            commit_sha="a" * 40,
            branch="main",
            workflow_name="CI",
            workflow_path=".github/workflows/ci.yml",
            event="push",
            triggered_at=None,
            conclusion=GitHubConclusion.FAILURE,
        )
    assert "repository" in str(exc_info.value)


def test_invalid_commit_sha():
    """Test invalid commit SHA."""
    with pytest.raises(ValidationError):
        Incident(
            repository="owner/repo",
            run_id=123,
            run_url="https://github.com/owner/repo/actions/runs/123",
            commit_sha="short",
            branch="main",
            workflow_name="CI",
            workflow_path=".github/workflows/ci.yml",
            event="push",
            triggered_at=None,
            conclusion=GitHubConclusion.FAILURE,
        )


def test_confidence_validation():
    """Test confidence score and level consistency."""
    evidence = [
        Evidence(
            id="E1",
            type=EvidenceType.LOG,
            source="logs",
            location="job/1",
            log_excerpt="error",
            observation="test",
            supports="diagnosis",
        )
    ]

    valid_diagnosis = Diagnosis(
        root_cause="Test failure",
        technical_explanation="Tests failed",
        observed_facts=["fact"],
        inferences=["inference"],
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
        supporting_evidence_ids=["E1"],
        primary_vs_cascading="primary",
        alternative_hypotheses=[],
    )
    assert valid_diagnosis.confidence == 0.85

    with pytest.raises(ValidationError) as exc_info:
        Diagnosis(
            root_cause="Test failure",
            technical_explanation="Tests failed",
            observed_facts=["fact"],
            inferences=["inference"],
            confidence=0.85,
            confidence_level=ConfidenceLevel.LOW,
            supporting_evidence_ids=["E1"],
            primary_vs_cascading="primary",
            alternative_hypotheses=[],
        )
    assert "Confidence" in str(exc_info.value)


def test_evidence_reference_validation():
    """Test evidence ID reference validation."""
    incident = Incident(
        repository="owner/repo",
        run_id=123,
        run_url="https://github.com/owner/repo/actions/runs/123",
        commit_sha="a" * 40,
        branch="main",
        workflow_name="CI",
        workflow_path=".github/workflows/ci.yml",
        event="push",
        triggered_at=None,
        conclusion=GitHubConclusion.FAILURE,
    )

    failure = Failure(
        category=FailureCategory.TEST_FAILURE,
        summary="Test failed",
        job=Job(name="test", id=1, url="https://example.com"),
        failed_step=FailedStep(name="Run tests", number=3, status=StepStatus.COMPLETED),
        locations=[],
    )

    diagnosis = Diagnosis(
        root_cause="Test failure",
        technical_explanation="Tests failed",
        observed_facts=["fact"],
        inferences=["inference"],
        confidence=0.6,
        confidence_level=ConfidenceLevel.MEDIUM,
        supporting_evidence_ids=["E1"],
        primary_vs_cascading="primary",
        alternative_hypotheses=[],
    )

    evidence = [
        Evidence(
            id="E1",
            type=EvidenceType.LOG,
            source="logs",
            location="job/1",
            log_excerpt="error",
            observation="test",
            supports="diagnosis",
        )
    ]

    proposed_patch = ProposedPatch(
        available=False,
        target_files=[],
        change_type=ChangeType.NONE,
        unified_diff=None,
        rationale="No patch",
        risk=Risk(level=RiskLevel.LOW, description="none"),
        requires_human_approval=True,
        applied=False,
        tested=False,
    )

    verification = Verification(
        status=VerificationStatus.NOT_RUN,
        steps=[],
        verified_at=None,
        executed_by=None,
    )

    report = IncidentReport(
        schema_version="1.0.0",
        incident=incident,
        failure=failure,
        diagnosis=diagnosis,
        evidence=evidence,
        proposed_patch=proposed_patch,
        verification=verification,
        limitations=[],
    )
    assert report is not None


def test_missing_evidence_reference():
    """Test validation fails when evidence ID is missing."""
    incident = Incident(
        repository="owner/repo",
        run_id=123,
        run_url="https://github.com/owner/repo/actions/runs/123",
        commit_sha="a" * 40,
        branch="main",
        workflow_name="CI",
        workflow_path=".github/workflows/ci.yml",
        event="push",
        triggered_at=None,
        conclusion=GitHubConclusion.FAILURE,
    )

    failure = Failure(
        category=FailureCategory.TEST_FAILURE,
        summary="Test failed",
        job=Job(name="test", id=1, url=None),
        failed_step=FailedStep(name="Run tests", number=3, status=StepStatus.COMPLETED),
        locations=[],
    )

    diagnosis = Diagnosis(
        root_cause="Test failure",
        technical_explanation="Tests failed",
        observed_facts=["fact"],
        inferences=["inference"],
        confidence=0.6,
        confidence_level=ConfidenceLevel.MEDIUM,
        supporting_evidence_ids=["E999"],
        primary_vs_cascading="primary",
        alternative_hypotheses=[],
    )

    evidence = [
        Evidence(
            id="E1",
            type=EvidenceType.LOG,
            source="logs",
            location="job/1",
            log_excerpt=None,
            observation="test",
            supports="diagnosis",
        )
    ]

    with pytest.raises(ValidationError) as exc_info:
        IncidentReport(
            schema_version="1.0.0",
            incident=incident,
            failure=failure,
            diagnosis=diagnosis,
            evidence=evidence,
            proposed_patch=ProposedPatch(
                available=False,
                target_files=[],
                change_type=ChangeType.NONE,
                unified_diff=None,
                rationale="none",
                risk=Risk(level=RiskLevel.LOW, description="none"),
                requires_human_approval=True,
            ),
            verification=Verification(
                status=VerificationStatus.NOT_RUN,
                steps=[],
                verified_at=None,
                executed_by=None,
            ),
            limitations=[],
        )
    assert "E999" in str(exc_info.value)


def test_root_cause_without_evidence():
    """Test validation fails when root cause has no supporting evidence."""
    incident = Incident(
        repository="owner/repo",
        run_id=123,
        run_url="https://github.com/owner/repo/actions/runs/123",
        commit_sha="a" * 40,
        branch="main",
        workflow_name="CI",
        workflow_path=".github/workflows/ci.yml",
        event="push",
        triggered_at=None,
        conclusion=GitHubConclusion.FAILURE,
    )

    failure = Failure(
        category=FailureCategory.TEST_FAILURE,
        summary="Test failed",
        job=None,
        failed_step=FailedStep(name="Run tests", number=3, status=StepStatus.COMPLETED),
        locations=[],
    )

    diagnosis = Diagnosis(
        root_cause="Test failure",
        technical_explanation="Tests failed",
        observed_facts=["fact"],
        inferences=["inference"],
        confidence=0.6,
        confidence_level=ConfidenceLevel.MEDIUM,
        supporting_evidence_ids=[],
        primary_vs_cascading="primary",
        alternative_hypotheses=[],
    )

    with pytest.raises(ValidationError) as exc_info:
        IncidentReport(
            schema_version="1.0.0",
            incident=incident,
            failure=failure,
            diagnosis=diagnosis,
            evidence=[],
            proposed_patch=ProposedPatch(
                available=False,
                target_files=[],
                change_type=ChangeType.NONE,
                unified_diff=None,
                rationale="none",
                risk=Risk(level=RiskLevel.LOW, description="none"),
                requires_human_approval=True,
            ),
            verification=Verification(
                status=VerificationStatus.NOT_RUN,
                steps=[],
                verified_at=None,
                executed_by=None,
            ),
            limitations=[],
        )
    assert "supporting evidence" in str(exc_info.value).lower()


def test_patch_requires_human_approval():
    """Test patch available=true requires human approval."""
    with pytest.raises(ValidationError) as exc_info:
        ProposedPatch(
            available=True,
            target_files=["file.py"],
            change_type=ChangeType.FIX,
            unified_diff="diff content",
            rationale="fix bug",
            risk=Risk(level=RiskLevel.LOW, description="safe"),
            requires_human_approval=False,
        )
    assert "requires_human_approval" in str(exc_info.value).lower()


def test_verification_consistency():
    """Test verification status requires verified_at and executed_by."""
    verification = Verification(
        status=VerificationStatus.NOT_RUN,
        steps=[],
        verified_at=None,
        executed_by=None,
    )
    assert verification.status == VerificationStatus.NOT_RUN

    with pytest.raises(ValidationError):
        Verification(
            status=VerificationStatus.PASSED,
            steps=[],
            verified_at=None,
            executed_by=None,
        )


def test_insufficient_evidence_category():
    """Test insufficient_evidence category forces low/insufficient confidence."""
    incident = Incident(
        repository="owner/repo",
        run_id=123,
        run_url="https://github.com/owner/repo/actions/runs/123",
        commit_sha="a" * 40,
        branch="main",
        workflow_name="CI",
        workflow_path=".github/workflows/ci.yml",
        event="push",
        triggered_at=None,
        conclusion=GitHubConclusion.FAILURE,
    )

    failure = Failure(
        category=FailureCategory.INSUFFICIENT_EVIDENCE,
        summary="Cannot determine cause",
        job=None,
        failed_step=FailedStep(name="Unknown", number=1, status=StepStatus.COMPLETED),
        locations=[],
    )

    diagnosis = Diagnosis(
        root_cause="Unknown",
        technical_explanation="Not enough information",
        observed_facts=["minimal facts"],
        inferences=[],
        confidence=0.3,
        confidence_level=ConfidenceLevel.LOW,
        supporting_evidence_ids=["E1"],
        primary_vs_cascading="unknown",
        alternative_hypotheses=[],
    )

    evidence = [
        Evidence(
            id="E1",
            type=EvidenceType.LOG,
            source="logs",
            location="job/1",
            log_excerpt=None,
            observation="limited info",
            supports="none",
        )
    ]

    report = IncidentReport(
        schema_version="1.0.0",
        incident=incident,
        failure=failure,
        diagnosis=diagnosis,
        evidence=evidence,
        proposed_patch=ProposedPatch(
            available=False,
            target_files=[],
            change_type=ChangeType.NONE,
            unified_diff=None,
            rationale="insufficient evidence",
            risk=Risk(level=RiskLevel.LOW, description="none"),
            requires_human_approval=True,
        ),
        verification=Verification(
            status=VerificationStatus.NOT_RUN,
            steps=[],
            verified_at=None,
            executed_by=None,
        ),
        limitations=["Cannot access logs"],
    )
    assert report.diagnosis.confidence_level == ConfidenceLevel.LOW


def test_patch_tested_without_verification():
    """Test patch cannot be tested when verification is not_run."""
    incident = Incident(
        repository="owner/repo",
        run_id=123,
        run_url="https://github.com/owner/repo/actions/runs/123",
        commit_sha="a" * 40,
        branch="main",
        workflow_name="CI",
        workflow_path=".github/workflows/ci.yml",
        event="push",
        triggered_at=None,
        conclusion=GitHubConclusion.FAILURE,
    )

    failure = Failure(
        category=FailureCategory.TEST_FAILURE,
        summary="Test failed",
        job=None,
        failed_step=FailedStep(name="test", number=1, status=StepStatus.COMPLETED),
        locations=[],
    )

    diagnosis = Diagnosis(
        root_cause="bug",
        technical_explanation="code bug",
        observed_facts=["fact"],
        inferences=["inference"],
        confidence=0.6,
        confidence_level=ConfidenceLevel.MEDIUM,
        supporting_evidence_ids=["E1"],
        primary_vs_cascading="primary",
        alternative_hypotheses=[],
    )

    evidence = [
        Evidence(
            id="E1",
            type=EvidenceType.LOG,
            source="logs",
            location="job/1",
            log_excerpt=None,
            observation="error",
            supports="diagnosis",
        )
    ]

    with pytest.raises(ValidationError) as exc_info:
        IncidentReport(
            schema_version="1.0.0",
            incident=incident,
            failure=failure,
            diagnosis=diagnosis,
            evidence=evidence,
            proposed_patch=ProposedPatch(
                available=True,
                target_files=["test.py"],
                change_type=ChangeType.FIX,
                unified_diff="diff",
                rationale="fix",
                risk=Risk(level=RiskLevel.LOW, description="safe"),
                requires_human_approval=True,
                tested=True,
            ),
            verification=Verification(
                status=VerificationStatus.NOT_RUN,
                steps=[],
                verified_at=None,
                executed_by=None,
            ),
            limitations=[],
        )
    assert "tested" in str(exc_info.value).lower() or "verification" in str(exc_info.value).lower()


def test_extra_properties_forbidden():
    """Test that extra properties are forbidden."""
    with pytest.raises(ValidationError):
        Incident(
            repository="owner/repo",
            run_id=123,
            run_url="https://github.com/owner/repo/actions/runs/123",
            commit_sha="a" * 40,
            branch="main",
            workflow_name="CI",
            workflow_path=".github/workflows/ci.yml",
            event="push",
            triggered_at=None,
            conclusion=GitHubConclusion.FAILURE,
            extra_field="not allowed",
        )
