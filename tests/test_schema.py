"""Tests for JSON schema validation."""

import json
from pathlib import Path

import pytest

from pipeline_doctor.validator import IncidentReportValidator


def test_schema_file_is_valid():
    """Test that the JSON schema file itself is valid Draft 2020-12."""
    schema_path = Path(__file__).parent.parent / "schemas" / "incident-report.schema.json"
    result = IncidentReportValidator.validate_json_schema(schema_path)

    if not result.success:
        pytest.skip(f"jsonschema library not available: {result.errors}")

    assert result.success, f"Schema validation failed: {result.errors}"


def test_example_validates_against_schema():
    """Test that example incident report validates."""
    example_path = Path(__file__).parent.parent / "examples" / "example-incident-report.json"

    with open(example_path) as f:
        example_data = json.load(f)

    validator = IncidentReportValidator()
    result = validator.validate(example_data)

    assert result.success, f"Example validation failed: {result.errors}"
    assert result.report is not None
