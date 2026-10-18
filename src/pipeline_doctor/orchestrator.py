"""Diagnosis pipeline orchestrator."""

from pathlib import Path
from typing import Dict, List, Optional, Set

from .evidence import EvidenceCollector
from .grok_client import FakeGrokClient, GrokAPIClient
from .models import IncidentReport
from .prompts import PromptLoader
from .protocols import GrokClient
from .redaction import SecretRedactor, SizeLimiter
from .validator import IncidentReportValidator, ValidationResult


class DiagnosisResult:
    """Result of diagnosis pipeline."""

    def __init__(
        self,
        success: bool,
        report: Optional[IncidentReport] = None,
        errors: Optional[List[str]] = None,
        limitations: Optional[List[str]] = None,
    ):
        self.success = success
        self.report = report
        self.errors = errors or []
        self.limitations = limitations or []

    def __bool__(self) -> bool:
        return self.success


class DiagnosisOrchestrator:
    """Orchestrates the diagnosis pipeline."""

    def __init__(
        self,
        evidence_collector: EvidenceCollector,
        grok_client: GrokClient,
        prompt_loader: PromptLoader,
        validator: IncidentReportValidator,
        redactor: SecretRedactor,
    ):
        """
        Initialize orchestrator.

        Args:
            evidence_collector: Evidence collector
            grok_client: Grok AI client
            prompt_loader: Prompt loader
            validator: Report validator
            redactor: Secret redactor
        """
        self.evidence_collector = evidence_collector
        self.grok_client = grok_client
        self.prompt_loader = prompt_loader
        self.validator = validator
        self.redactor = redactor
        # Store GitHub client reference for SHA drift check
        self.github_client = evidence_collector.github

    def diagnose(
        self,
        owner: str,
        repo: str,
        run_id: int,
        additional_files: Optional[List[str]] = None,
    ) -> DiagnosisResult:
        """
        Run complete diagnosis pipeline.

        Steps:
        1. Collect evidence (run metadata, logs, workflow YAML)
        2. Optionally fetch additional source files
        3. Redact all collected data
        4. Send to Grok for diagnosis
        5. Validate response
        6. Return validated report or errors

        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID
            additional_files: Optional list of additional file paths to fetch

        Returns:
            DiagnosisResult with success status, report, and errors
        """
        evidence_data = self.evidence_collector.collect_run_evidence(owner, repo, run_id)

        pinned_sha = evidence_data["pinned_sha"]
        if not pinned_sha:
            return DiagnosisResult(
                success=False,
                errors=["Could not determine commit SHA for the workflow run"],
                limitations=evidence_data["limitations"],
            )

        run_metadata = evidence_data["run_metadata"]
        if not run_metadata:
            return DiagnosisResult(
                success=False,
                errors=["Failed to fetch run metadata"],
                limitations=evidence_data["limitations"],
            )

        failed_job = evidence_data["failed_job"]
        logs = evidence_data["logs"] or ""
        workflow_yaml = evidence_data["workflow_yaml"] or ""
        evidence_items = evidence_data["evidence_items"]
        limitations = evidence_data["limitations"].copy()

        # Check for SHA drift by re-fetching run metadata
        try:
            current_run_metadata = self.github_client.get_workflow_run(owner, repo, run_id)
            current_sha = current_run_metadata.get("head_sha")
            if current_sha != pinned_sha:
                return DiagnosisResult(
                    success=False,
                    errors=[f"Commit SHA drift detected: started with {pinned_sha}, now at {current_sha}"],
                    limitations=limitations,
                )
        except Exception as e:
            # If re-fetch fails, log limitation but continue
            limitations.append(f"Could not verify SHA consistency: {str(e)}")

        source_files = {}
        fetch_limitations = []
        if additional_files:
            fetch_result = self.evidence_collector.fetch_source_files(
                owner, repo, additional_files
            )
            source_files = fetch_result.get("files", {})
            fetch_limitations = fetch_result.get("limitations", [])

        limitations = limitations + fetch_limitations

        system_prompt = self.prompt_loader.load_system_prompt()
        user_message = self.prompt_loader.format_user_message(
            run_metadata=run_metadata,
            failed_job=failed_job,
            logs=logs,
            workflow_yaml=workflow_yaml,
            source_files=source_files,
            limitations=limitations,
            evidence_items=evidence_items,
        )

        user_message_redacted = self.redactor.redact(user_message)

        try:
            grok_response = self.grok_client.chat_completion(
                system_prompt=system_prompt,
                user_message=user_message_redacted,
                temperature=0.1,
            )
        except Exception as e:
            # Surface structured error details if available
            error_msg = str(e)
            if hasattr(e, 'status_code') and hasattr(e, 'response_body'):
                error_msg = f"Grok API error (status {e.status_code}): {e.response_body}"
            else:
                error_msg = f"Grok API error: {str(e)}"
            return DiagnosisResult(
                success=False,
                errors=[error_msg],
                limitations=limitations,
            )

        grok_response_redacted = self.redactor.redact(grok_response)

        known_files = set(source_files.keys()) if source_files else None
        collected_evidence_ids = {item.id for item in evidence_items}
        self.validator.known_files = known_files
        self.validator.collected_evidence_ids = collected_evidence_ids

        validation_result = self.validator.validate(grok_response_redacted)

        if not validation_result.success:
            return DiagnosisResult(
                success=False,
                errors=validation_result.errors,
                limitations=limitations,
            )

        return DiagnosisResult(
            success=True,
            report=validation_result.report,
            limitations=limitations,
        )
