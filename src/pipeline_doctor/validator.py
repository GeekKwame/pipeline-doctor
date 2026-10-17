"""Validation module for incident reports."""

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from pydantic import ValidationError

from .models import IncidentReport


class ValidationResult:
    """Result of validation operation."""

    def __init__(self, success: bool, errors: Optional[List[str]] = None, report: Optional[IncidentReport] = None):
        self.success = success
        self.errors = errors or []
        self.report = report

    def __bool__(self) -> bool:
        return self.success

    def __repr__(self) -> str:
        if self.success:
            return f"ValidationResult(success=True)"
        return f"ValidationResult(success=False, errors={self.errors})"


class IncidentReportValidator:
    """Validator for incident reports."""

    def __init__(
        self,
        known_files: Optional[Set[str]] = None,
        file_line_counts: Optional[Dict[str, int]] = None,
    ):
        """
        Initialize validator.

        Args:
            known_files: Set of known file paths in the repository
            file_line_counts: Mapping of file paths to their line counts
        """
        self.known_files = known_files
        self.file_line_counts = file_line_counts or {}

    def validate(self, data: Any) -> ValidationResult:
        """
        Validate incident report data.

        Handles malformed Grok output safely:
        - Non-JSON input
        - JSON in markdown fences
        - Truncated data
        - Wrong types

        Args:
            data: Raw data (string, dict, or any other type)

        Returns:
            ValidationResult with success status, errors, and parsed report
        """
        errors = []

        parsed_data = self._extract_json(data)
        if parsed_data is None:
            return ValidationResult(success=False, errors=["Failed to parse JSON from input"])

        try:
            report = IncidentReport.model_validate(parsed_data)
        except ValidationError as e:
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                errors.append(f"{loc}: {error['msg']}")
            return ValidationResult(success=False, errors=errors)
        except Exception as e:
            return ValidationResult(success=False, errors=[f"Validation error: {str(e)}"])

        validation_errors = self._validate_against_known_files(report)
        if validation_errors:
            return ValidationResult(success=False, errors=validation_errors)

        line_validation_errors = self._validate_line_ranges(report)
        if line_validation_errors:
            return ValidationResult(success=False, errors=line_validation_errors)

        return ValidationResult(success=True, report=report)

    def _extract_json(self, data: Any) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from various formats.

        Handles:
        - Direct dict
        - JSON string
        - JSON wrapped in markdown code fences
        - Truncated or malformed JSON

        Returns:
            Parsed dict or None if extraction fails
        """
        if isinstance(data, dict):
            return data

        if not isinstance(data, str):
            return None

        data_str = data.strip()

        json_fence_pattern = r"```(?:json)?\s*\n(.*?)\n```"
        match = re.search(json_fence_pattern, data_str, re.DOTALL)
        if match:
            data_str = match.group(1).strip()

        try:
            return json.loads(data_str)
        except json.JSONDecodeError:
            pass

        return None

    def _validate_against_known_files(self, report: IncidentReport) -> List[str]:
        """
        Validate that patch targets and locations reference known files.

        Args:
            report: Validated incident report

        Returns:
            List of validation errors
        """
        if self.known_files is None:
            return []

        errors = []

        if report.proposed_patch.available:
            for target_file in report.proposed_patch.target_files:
                if target_file not in self.known_files:
                    errors.append(f"Patch targets unknown file: {target_file}")

        for location in report.failure.locations:
            if location.path not in self.known_files:
                errors.append(f"Location references unknown file: {location.path}")

        return errors

    def _validate_line_ranges(self, report: IncidentReport) -> List[str]:
        """
        Validate that line ranges fall within file bounds.

        Args:
            report: Validated incident report

        Returns:
            List of validation errors
        """
        if not self.file_line_counts:
            return []

        errors = []

        for location in report.failure.locations:
            if location.path in self.file_line_counts:
                max_lines = self.file_line_counts[location.path]
                if location.end_line > max_lines:
                    errors.append(
                        f"Location {location.path} end_line {location.end_line} "
                        f"exceeds file length {max_lines}"
                    )

        return errors

    @staticmethod
    def validate_json_schema(schema_path: Path) -> ValidationResult:
        """
        Validate that the JSON schema itself is valid Draft 2020-12.

        Args:
            schema_path: Path to the JSON schema file

        Returns:
            ValidationResult indicating if schema is valid
        """
        try:
            import jsonschema
            from jsonschema import Draft202012Validator
        except ImportError:
            return ValidationResult(
                success=False,
                errors=["jsonschema library not installed; cannot validate schema"],
            )

        try:
            with open(schema_path) as f:
                schema = json.load(f)

            Draft202012Validator.check_schema(schema)

            return ValidationResult(success=True)
        except jsonschema.SchemaError as e:
            return ValidationResult(success=False, errors=[f"Schema validation error: {e.message}"])
        except json.JSONDecodeError as e:
            return ValidationResult(success=False, errors=[f"JSON parse error: {str(e)}"])
        except Exception as e:
            return ValidationResult(success=False, errors=[f"Unexpected error: {str(e)}"])


def create_validator(
    known_files: Optional[Set[str]] = None,
    file_line_counts: Optional[Dict[str, int]] = None,
) -> IncidentReportValidator:
    """
    Factory function to create a validator.

    Args:
        known_files: Set of known file paths
        file_line_counts: Mapping of file paths to line counts

    Returns:
        Configured validator instance
    """
    return IncidentReportValidator(known_files=known_files, file_line_counts=file_line_counts)
