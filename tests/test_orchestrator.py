"""Tests for diagnosis orchestrator."""

import json
from pathlib import Path

import pytest

from pipeline_doctor.evidence import EvidenceCollector
from pipeline_doctor.github_client import FakeGitHubClient
from pipeline_doctor.grok_client import FakeGrokClient
from pipeline_doctor.orchestrator import DiagnosisOrchestrator
from pipeline_doctor.prompts import PromptLoader
from pipeline_doctor.redaction import SecretRedactor, SizeLimiter
from pipeline_doctor.validator import IncidentReportValidator


def test_orchestrator_successful_diagnosis(tmp_path):
    """Test successful diagnosis pipeline."""
    github = FakeGitHubClient()
    grok = FakeGrokClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()
    evidence_collector = EvidenceCollector(github, redactor, limiter)

    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "diagnosis_system_prompt.md").write_text("System prompt")

    prompt_loader = PromptLoader(prompts_dir)
    validator = IncidentReportValidator()

    orchestrator = DiagnosisOrchestrator(
        evidence_collector, grok, prompt_loader, validator, redactor
    )

    result = orchestrator.diagnose("owner", "repo", 12345)

    assert result.success
    assert result.report is not None
    assert len(grok.calls) == 1


def test_orchestrator_with_additional_files(tmp_path):
    """Test orchestrator with additional source files."""
    github = FakeGitHubClient(files={"src/main.py": "print('test')"})
    grok = FakeGrokClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()
    evidence_collector = EvidenceCollector(github, redactor, limiter)

    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "diagnosis_system_prompt.md").write_text("System prompt")

    prompt_loader = PromptLoader(prompts_dir)
    validator = IncidentReportValidator()

    orchestrator = DiagnosisOrchestrator(
        evidence_collector, grok, prompt_loader, validator, redactor
    )

    result = orchestrator.diagnose("owner", "repo", 12345, additional_files=["src/main.py"])

    assert result.success


def test_orchestrator_grok_api_error(tmp_path):
    """Test handling of Grok API errors."""

    class FailingGrokClient:
        def chat_completion(self, system_prompt, user_message, model="grok-beta", temperature=0.1):
            raise Exception("API error")

    github = FakeGitHubClient()
    grok = FailingGrokClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()
    evidence_collector = EvidenceCollector(github, redactor, limiter)

    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "diagnosis_system_prompt.md").write_text("System prompt")

    prompt_loader = PromptLoader(prompts_dir)
    validator = IncidentReportValidator()

    orchestrator = DiagnosisOrchestrator(
        evidence_collector, grok, prompt_loader, validator, redactor
    )

    result = orchestrator.diagnose("owner", "repo", 12345)

    assert not result.success
    assert any("Grok API error" in err for err in result.errors)


def test_orchestrator_malformed_grok_response(tmp_path):
    """Test handling of malformed Grok response."""
    github = FakeGitHubClient()
    grok = FakeGrokClient(canned_response="This is not valid JSON")
    redactor = SecretRedactor()
    limiter = SizeLimiter()
    evidence_collector = EvidenceCollector(github, redactor, limiter)

    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "diagnosis_system_prompt.md").write_text("System prompt")

    prompt_loader = PromptLoader(prompts_dir)
    validator = IncidentReportValidator()

    orchestrator = DiagnosisOrchestrator(
        evidence_collector, grok, prompt_loader, validator, redactor
    )

    result = orchestrator.diagnose("owner", "repo", 12345)

    assert not result.success
    assert len(result.errors) > 0


def test_orchestrator_sha_drift(tmp_path):
    """Test detection of commit SHA drift."""

    class DriftingGitHubClient(FakeGitHubClient):
        def __init__(self):
            super().__init__()
            self.call_count = 0

        def get_workflow_run(self, owner, repo, run_id):
            self.call_count += 1
            data = super().get_workflow_run(owner, repo, run_id)
            if self.call_count > 1:
                data["head_sha"] = "b" * 40
            return data

    github = DriftingGitHubClient()
    grok = FakeGrokClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()
    evidence_collector = EvidenceCollector(github, redactor, limiter)

    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "diagnosis_system_prompt.md").write_text("System prompt")

    prompt_loader = PromptLoader(prompts_dir)
    validator = IncidentReportValidator()

    orchestrator = DiagnosisOrchestrator(
        evidence_collector, grok, prompt_loader, validator, redactor
    )

    evidence_data = evidence_collector.collect_run_evidence("owner", "repo", 12345)
    pinned = evidence_data["pinned_sha"]

    run_metadata = evidence_data["run_metadata"]
    run_metadata["head_sha"] = "different" + pinned[9:]

    assert run_metadata["head_sha"] != pinned
