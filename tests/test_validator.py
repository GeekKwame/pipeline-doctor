"""Tests for validator module."""

import json

import pytest

from pipeline_doctor.validator import IncidentReportValidator, ValidationResult


def test_validate_valid_dict():
    """Test validation of valid dictionary."""
    validator = IncidentReportValidator()

    data = {
        "schema_version": "1.0.0",
        "incident": {
            "repository": "owner/repo",
            "run_id": 123,
            "run_url": "https://github.com/owner/repo/actions/runs/123",
            "commit_sha": "a" * 40,
            "branch": "main",
            "workflow_name": "CI",
            "workflow_path": ".github/workflows/ci.yml",
            "event": "push",
            "triggered_at": "2024-01-01T00:00:00Z",
            "conclusion": "failure",
        },
        "failure": {
            "category": "test_failure",
            "summary": "Test failed",
            "job": {"name": "test", "id": 1, "url": None},
            "failed_step": {"name": "Run tests", "number": 3, "status": "completed"},
            "locations": [],
        },
        "diagnosis": {
            "root_cause": "Test failure",
            "technical_explanation": "Tests failed",
            "observed_facts": ["fact"],
            "inferences": ["inference"],
            "confidence": 0.6,
            "confidence_level": "medium",
            "supporting_evidence_ids": ["E1"],
            "primary_vs_cascading": "primary",
            "alternative_hypotheses": [],
        },
        "evidence": [
            {
                "id": "E1",
                "type": "log",
                "source": "logs",
                "location": "job/1",
                "log_excerpt": None,
                "observation": "test",
                "supports": "diagnosis",
            }
        ],
        "proposed_patch": {
            "available": False,
            "target_files": [],
            "change_type": "none",
            "unified_diff": None,
            "rationale": "No patch",
            "risk": {"level": "low", "description": "none"},
            "requires_human_approval": True,
            "applied": False,
            "tested": False,
        },
        "verification": {
            "status": "not_run",
            "steps": [],
            "verified_at": None,
            "executed_by": None,
        },
        "limitations": [],
    }

    result = validator.validate(data)
    assert result.success
    assert result.report is not None


def test_validate_json_string():
    """Test validation of JSON string."""
    validator = IncidentReportValidator()

    data = {
        "schema_version": "1.0.0",
        "incident": {
            "repository": "owner/repo",
            "run_id": 123,
            "run_url": "https://github.com/owner/repo/actions/runs/123",
            "commit_sha": "b" * 40,
            "branch": "main",
            "workflow_name": "CI",
            "workflow_path": ".github/workflows/ci.yml",
            "event": "push",
            "triggered_at": None,
            "conclusion": "failure",
        },
        "failure": {
            "category": "build_failure",
            "summary": "Build failed",
            "job": None,
            "failed_step": {"name": "Build", "number": 2, "status": "completed"},
            "locations": [],
        },
        "diagnosis": {
            "root_cause": "Build failure",
            "technical_explanation": "Build failed",
            "observed_facts": ["fact"],
            "inferences": ["inference"],
            "confidence": 0.4,
            "confidence_level": "low",
            "supporting_evidence_ids": ["E1"],
            "primary_vs_cascading": "primary",
            "alternative_hypotheses": [],
        },
        "evidence": [
            {
                "id": "E1",
                "type": "log",
                "source": "logs",
                "location": "job/1",
                "log_excerpt": "error",
                "observation": "build error",
                "supports": "diagnosis",
            }
        ],
        "proposed_patch": {
            "available": False,
            "target_files": [],
            "change_type": "none",
            "unified_diff": None,
            "rationale": "No patch",
            "risk": {"level": "low", "description": "none"},
            "requires_human_approval": True,
        },
        "verification": {
            "status": "not_run",
            "steps": [],
            "verified_at": None,
            "executed_by": None,
        },
        "limitations": [],
    }

    json_str = json.dumps(data)
    result = validator.validate(json_str)
    assert result.success


def test_validate_json_in_markdown_fences():
    """Test extraction of JSON from markdown code fences."""
    validator = IncidentReportValidator()

    data = {
        "schema_version": "1.0.0",
        "incident": {
            "repository": "owner/repo",
            "run_id": 123,
            "run_url": "https://github.com/owner/repo/actions/runs/123",
            "commit_sha": "c" * 40,
            "branch": "main",
            "workflow_name": "CI",
            "workflow_path": ".github/workflows/ci.yml",
            "event": "push",
            "triggered_at": None,
            "conclusion": "failure",
        },
        "failure": {
            "category": "test_failure",
            "summary": "Test failed",
            "job": None,
            "failed_step": {"name": "test", "number": 1, "status": "completed"},
            "locations": [],
        },
        "diagnosis": {
            "root_cause": "test",
            "technical_explanation": "test",
            "observed_facts": ["f"],
            "inferences": ["i"],
            "confidence": 0.5,
            "confidence_level": "medium",
            "supporting_evidence_ids": ["E1"],
            "primary_vs_cascading": "p",
            "alternative_hypotheses": [],
        },
        "evidence": [
            {
                "id": "E1",
                "type": "log",
                "source": "s",
                "location": "l",
                "log_excerpt": None,
                "observation": "o",
                "supports": "s",
            }
        ],
        "proposed_patch": {
            "available": False,
            "target_files": [],
            "change_type": "none",
            "unified_diff": None,
            "rationale": "r",
            "risk": {"level": "low", "description": "d"},
            "requires_human_approval": True,
        },
        "verification": {"status": "not_run", "steps": [], "verified_at": None, "executed_by": None},
        "limitations": [],
    }

    markdown_str = f"```json\n{json.dumps(data)}\n```"
    result = validator.validate(markdown_str)
    assert result.success


def test_validate_malformed_json():
    """Test handling of malformed JSON."""
    validator = IncidentReportValidator()

    result = validator.validate("not valid json {")
    assert not result.success
    assert len(result.errors) > 0


def test_validate_missing_required_field():
    """Test validation fails on missing required field."""
    validator = IncidentReportValidator()

    data = {
        "schema_version": "1.0.0",
        "incident": {
            "repository": "owner/repo",
            "run_id": 123,
        },
    }

    result = validator.validate(data)
    assert not result.success
    assert len(result.errors) > 0


def test_validate_invalid_enum():
    """Test validation fails on invalid enum value."""
    validator = IncidentReportValidator()

    data = {
        "schema_version": "1.0.0",
        "incident": {
            "repository": "owner/repo",
            "run_id": 123,
            "run_url": "https://github.com/owner/repo/actions/runs/123",
            "commit_sha": "d" * 40,
            "branch": "main",
            "workflow_name": "CI",
            "workflow_path": ".github/workflows/ci.yml",
            "event": "push",
            "triggered_at": None,
            "conclusion": "invalid_conclusion",
        },
        "failure": {
            "category": "test_failure",
            "summary": "Test failed",
            "job": None,
            "failed_step": {"name": "test", "number": 1, "status": "completed"},
            "locations": [],
        },
        "diagnosis": {
            "root_cause": "test",
            "technical_explanation": "test",
            "observed_facts": ["f"],
            "inferences": ["i"],
            "confidence": 0.5,
            "confidence_level": "medium",
            "supporting_evidence_ids": ["E1"],
            "primary_vs_cascading": "p",
            "alternative_hypotheses": [],
        },
        "evidence": [
            {
                "id": "E1",
                "type": "log",
                "source": "s",
                "location": "l",
                "log_excerpt": None,
                "observation": "o",
                "supports": "s",
            }
        ],
        "proposed_patch": {
            "available": False,
            "target_files": [],
            "change_type": "none",
            "unified_diff": None,
            "rationale": "r",
            "risk": {"level": "low", "description": "d"},
            "requires_human_approval": True,
        },
        "verification": {"status": "not_run", "steps": [], "verified_at": None, "executed_by": None},
        "limitations": [],
    }

    result = validator.validate(data)
    assert not result.success


def test_validate_known_files():
    """Test validation against known files."""
    known_files = {"src/main.py", "tests/test_main.py"}
    validator = IncidentReportValidator(known_files=known_files)

    data = {
        "schema_version": "1.0.0",
        "incident": {
            "repository": "owner/repo",
            "run_id": 123,
            "run_url": "https://github.com/owner/repo/actions/runs/123",
            "commit_sha": "e" * 40,
            "branch": "main",
            "workflow_name": "CI",
            "workflow_path": ".github/workflows/ci.yml",
            "event": "push",
            "triggered_at": None,
            "conclusion": "failure",
        },
        "failure": {
            "category": "test_failure",
            "summary": "Test failed",
            "job": None,
            "failed_step": {"name": "test", "number": 1, "status": "completed"},
            "locations": [],
        },
        "diagnosis": {
            "root_cause": "test",
            "technical_explanation": "test",
            "observed_facts": ["f"],
            "inferences": ["i"],
            "confidence": 0.5,
            "confidence_level": "medium",
            "supporting_evidence_ids": ["E1"],
            "primary_vs_cascading": "p",
            "alternative_hypotheses": [],
        },
        "evidence": [
            {
                "id": "E1",
                "type": "log",
                "source": "s",
                "location": "l",
                "log_excerpt": None,
                "observation": "o",
                "supports": "s",
            }
        ],
        "proposed_patch": {
            "available": True,
            "target_files": ["nonexistent.py"],
            "change_type": "fix",
            "unified_diff": "diff",
            "rationale": "r",
            "risk": {"level": "low", "description": "d"},
            "requires_human_approval": True,
        },
        "verification": {"status": "not_run", "steps": [], "verified_at": None, "executed_by": None},
        "limitations": [],
    }

    result = validator.validate(data)
    assert not result.success
    assert any("nonexistent.py" in err for err in result.errors)


def test_validate_line_ranges():
    """Test validation of line ranges against file bounds."""
    file_line_counts = {"src/main.py": 100}
    validator = IncidentReportValidator(file_line_counts=file_line_counts)

    data = {
        "schema_version": "1.0.0",
        "incident": {
            "repository": "owner/repo",
            "run_id": 123,
            "run_url": "https://github.com/owner/repo/actions/runs/123",
            "commit_sha": "f" * 40,
            "branch": "main",
            "workflow_name": "CI",
            "workflow_path": ".github/workflows/ci.yml",
            "event": "push",
            "triggered_at": None,
            "conclusion": "failure",
        },
        "failure": {
            "category": "test_failure",
            "summary": "Test failed",
            "job": None,
            "failed_step": {"name": "test", "number": 1, "status": "completed"},
            "locations": [
                {"path": "src/main.py", "start_line": 50, "end_line": 200, "evidence_ids": ["E1"]}
            ],
        },
        "diagnosis": {
            "root_cause": "test",
            "technical_explanation": "test",
            "observed_facts": ["f"],
            "inferences": ["i"],
            "confidence": 0.5,
            "confidence_level": "medium",
            "supporting_evidence_ids": ["E1"],
            "primary_vs_cascading": "p",
            "alternative_hypotheses": [],
        },
        "evidence": [
            {
                "id": "E1",
                "type": "log",
                "source": "s",
                "location": "l",
                "log_excerpt": None,
                "observation": "o",
                "supports": "s",
            }
        ],
        "proposed_patch": {
            "available": False,
            "target_files": [],
            "change_type": "none",
            "unified_diff": None,
            "rationale": "r",
            "risk": {"level": "low", "description": "d"},
            "requires_human_approval": True,
        },
        "verification": {"status": "not_run", "steps": [], "verified_at": None, "executed_by": None},
        "limitations": [],
    }

    result = validator.validate(data)
    assert not result.success
    assert any("200" in err and "100" in err for err in result.errors)
