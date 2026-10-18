"""Tests for enhanced JSON extraction in validator."""

import pytest

from pipeline_doctor.validator import IncidentReportValidator


@pytest.fixture
def validator():
    """Create a basic validator."""
    return IncidentReportValidator()


def test_extract_json_from_prose_wrapped():
    """Test extraction of JSON object from prose text."""
    validator = IncidentReportValidator()
    
    prose_text = """
    Here is the incident report you requested:
    
    {"schema_version": "1.0.0", "test": "data", "nested": {"key": "value"}}
    
    I hope this helps!
    """
    
    result = validator._extract_json(prose_text)
    assert result is not None
    assert result["schema_version"] == "1.0.0"
    assert result["test"] == "data"
    assert result["nested"]["key"] == "value"


def test_extract_json_with_balanced_braces():
    """Test extraction handles nested braces correctly."""
    validator = IncidentReportValidator()
    
    text = 'Here is the data: {"outer": {"inner": {"deep": "value"}}} and some more text'
    
    result = validator._extract_json(text)
    assert result is not None
    assert result["outer"]["inner"]["deep"] == "value"


def test_extract_json_with_strings_containing_braces():
    """Test extraction handles braces inside strings."""
    validator = IncidentReportValidator()
    
    text = 'Data: {"message": "Error: {variable} is null", "code": 42}'
    
    result = validator._extract_json(text)
    assert result is not None
    assert result["message"] == "Error: {variable} is null"
    assert result["code"] == 42


def test_extract_json_with_escaped_quotes():
    """Test extraction handles escaped quotes in strings."""
    validator = IncidentReportValidator()
    
    text = 'Result: {"text": "She said \\"hello\\" to me"}'
    
    result = validator._extract_json(text)
    assert result is not None
    assert result["text"] == 'She said "hello" to me'


def test_validate_empty_response():
    """Test validation of empty response."""
    validator = IncidentReportValidator()
    
    result = validator.validate("")
    assert not result.success
    assert "empty" in result.errors[0].lower()


def test_validate_whitespace_only():
    """Test validation of whitespace-only response."""
    validator = IncidentReportValidator()
    
    result = validator.validate("   \n\t  \n  ")
    assert not result.success
    assert "empty" in result.errors[0].lower()


def test_validate_json_array_not_object():
    """Test validation rejects JSON arrays."""
    validator = IncidentReportValidator()
    
    result = validator.validate('[{"item": 1}, {"item": 2}]')
    assert not result.success
    assert "array" in result.errors[0].lower()
    assert "object" in result.errors[0].lower()


def test_validate_json_string_not_object():
    """Test validation rejects JSON strings."""
    validator = IncidentReportValidator()
    
    result = validator.validate('"this is a string"')
    assert not result.success
    assert "string" in result.errors[0].lower()
    assert "object" in result.errors[0].lower()


def test_validate_json_null():
    """Test validation rejects JSON null."""
    validator = IncidentReportValidator()
    
    result = validator.validate('null')
    assert not result.success
    assert "primitive" in result.errors[0].lower()


def test_validate_json_boolean():
    """Test validation rejects JSON booleans."""
    validator = IncidentReportValidator()
    
    result = validator.validate('true')
    assert not result.success
    assert "primitive" in result.errors[0].lower()


def test_validate_json_number():
    """Test validation rejects JSON numbers."""
    validator = IncidentReportValidator()
    
    result = validator.validate('42')
    assert not result.success
    assert "primitive" in result.errors[0].lower()


def test_validate_no_json_in_text():
    """Test validation when no JSON object is found."""
    validator = IncidentReportValidator()
    
    result = validator.validate("This is plain text with no JSON")
    assert not result.success
    assert "no json object" in result.errors[0].lower()


def test_validate_truncated_json():
    """Test validation when JSON is truncated."""
    validator = IncidentReportValidator()
    
    result = validator.validate('{"schema_version": "1.0.0", "incomplete": ')
    assert not result.success
    # Should mention truncation or malformed
    assert any(word in result.errors[0].lower() for word in ["truncated", "malformed", "parse"])


def test_validate_evidence_ids_against_collected():
    """Test validation of evidence IDs against collected set."""
    validator = IncidentReportValidator(
        collected_evidence_ids={"E1", "E2", "E3"}
    )
    
    # Valid minimal report that uses collected evidence IDs
    valid_report = {
        "schema_version": "1.0.0",
        "incident": {
            "repository": "owner/repo",
            "run_id": 1,
            "run_url": "https://example.com",
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
            "failed_step": {"name": "Run tests", "number": 1, "status": "completed"},
            "locations": [],
        },
        "diagnosis": {
            "root_cause": "Test failure",
            "technical_explanation": "Tests failed",
            "observed_facts": ["Test failed"],
            "inferences": ["Bug present"],
            "confidence": 0.7,
            "confidence_level": "medium",
            "supporting_evidence_ids": ["E1"],
            "primary_vs_cascading": "Primary",
            "alternative_hypotheses": [],
        },
        "evidence": [
            {
                "id": "E1",
                "type": "log",
                "source": "logs",
                "location": "url",
                "log_excerpt": "error",
                "observation": "obs",
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
    
    # Should succeed with E1 which is in collected set
    result = validator.validate(valid_report)
    assert result.success
    
    # Now test with evidence ID not in collected set
    invalid_report = valid_report.copy()
    invalid_report["evidence"] = [
        {
            "id": "E99",
            "type": "log",
            "source": "logs",
            "location": "url",
            "log_excerpt": "error",
            "observation": "obs",
            "supports": "diagnosis",
        }
    ]
    invalid_report["diagnosis"] = invalid_report["diagnosis"].copy()
    invalid_report["diagnosis"]["supporting_evidence_ids"] = ["E99"]
    
    result = validator.validate(invalid_report)
    assert not result.success
    assert any("not in the collected set" in err for err in result.errors)


def test_extract_first_json_object_no_json():
    """Test _extract_first_json_object when there's no JSON."""
    validator = IncidentReportValidator()
    
    result = validator._extract_first_json_object("plain text")
    assert result is None


def test_extract_first_json_object_unbalanced():
    """Test _extract_first_json_object with unbalanced braces."""
    validator = IncidentReportValidator()
    
    result = validator._extract_first_json_object('{"incomplete": "data"')
    assert result is None


def test_extract_json_markdown_fence():
    """Test extraction from markdown code fence."""
    validator = IncidentReportValidator()
    
    markdown = """
```json
{
  "key": "value",
  "number": 42
}
```
"""
    
    result = validator._extract_json(markdown)
    assert result is not None
    assert result["key"] == "value"
    assert result["number"] == 42


def test_extract_json_markdown_fence_no_language():
    """Test extraction from markdown code fence without language specifier."""
    validator = IncidentReportValidator()
    
    markdown = """
```
{"key": "value"}
```
"""
    
    result = validator._extract_json(markdown)
    assert result is not None
    assert result["key"] == "value"
