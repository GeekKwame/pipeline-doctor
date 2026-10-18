"""Tests for SHA drift detection."""

import pytest

from pipeline_doctor.evidence import EvidenceCollector
from pipeline_doctor.github_client import FakeGitHubClient
from pipeline_doctor.orchestrator import DiagnosisOrchestrator
from pipeline_doctor.grok_client import FakeGrokClient
from pipeline_doctor.prompts import PromptLoader
from pipeline_doctor.redaction import SecretRedactor, SizeLimiter
from pipeline_doctor.validator import IncidentReportValidator
from pathlib import Path


def test_sha_drift_detection_with_different_shas():
    """Test that SHA drift is detected when run metadata SHA changes."""
    # Create a GitHub client that returns different SHAs on subsequent calls
    class DriftingGitHubClient:
        def __init__(self):
            self.call_count = 0
            self.run_data = {
                "id": 12345,
                "name": "CI",
                "head_sha": "a" * 40,  # Initial SHA
                "head_branch": "main",
                "event": "push",
                "status": "completed",
                "conclusion": "failure",
                "workflow_id": 123,
                "html_url": "https://github.com/owner/repo/actions/runs/12345",
                "path": ".github/workflows/ci.yml",
            }
        
        def get_workflow_run(self, owner: str, repo: str, run_id: int):
            self.call_count += 1
            if self.call_count > 1:
                # Simulate drift on second call (the drift check in orchestrator)
                result = self.run_data.copy()
                result["head_sha"] = "b" * 40
                return result
            return self.run_data
        
        def list_jobs(self, owner: str, repo: str, run_id: int):
            return []
        
        def get_job_logs(self, owner: str, repo: str, job_id: int):
            return "logs"
        
        def get_file_content(self, owner: str, repo: str, path: str, ref: str):
            return "content"
        
        def get_workflow_file(self, owner: str, repo: str, workflow_path: str, ref: str):
            return "name: CI\non: push"
    
    github = DriftingGitHubClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()
    grok = FakeGrokClient()
    
    evidence_collector = EvidenceCollector(github, redactor, limiter)
    
    prompts_dir = Path(__file__).parent.parent / "prompts"
    prompt_loader = PromptLoader(prompts_dir)
    validator = IncidentReportValidator()
    
    orchestrator = DiagnosisOrchestrator(
        evidence_collector,
        grok,
        prompt_loader,
        validator,
        redactor,
    )
    
    result = orchestrator.diagnose("owner", "repo", 12345)
    
    # Should detect drift and fail
    assert not result.success
    assert len(result.errors) == 1
    assert "drift" in result.errors[0].lower()
    assert "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in result.errors[0]
    assert "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" in result.errors[0]


def test_sha_pinning_prevents_inconsistent_file_fetches():
    """Test that SHA pinning ensures all files are fetched at the same commit."""
    github = FakeGitHubClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()
    
    evidence_collector = EvidenceCollector(github, redactor, limiter)
    
    # Collect evidence
    evidence_data = evidence_collector.collect_run_evidence("owner", "repo", 12345)
    
    pinned_sha = evidence_data["pinned_sha"]
    assert pinned_sha == "a" * 40
    
    # Fetch additional files
    fetch_result = evidence_collector.fetch_source_files(
        "owner", "repo", ["src/main.py"]
    )
    
    # Both should use the same pinned SHA
    assert evidence_collector.pinned_sha == pinned_sha


def test_evidence_collector_pins_sha_on_first_fetch():
    """Test that evidence collector pins SHA from first run fetch."""
    run_data = {
        "id": 12345,
        "name": "CI",
        "head_sha": "1234567890abcdef" * 2 + "12345678",
        "head_branch": "main",
        "event": "push",
        "status": "completed",
        "conclusion": "failure",
        "workflow_id": 123,
        "html_url": "https://github.com/owner/repo/actions/runs/12345",
        "path": ".github/workflows/ci.yml",
    }
    
    github = FakeGitHubClient(run_data=run_data)
    redactor = SecretRedactor()
    limiter = SizeLimiter()
    
    evidence_collector = EvidenceCollector(github, redactor, limiter)
    
    assert evidence_collector.pinned_sha is None
    
    evidence_data = evidence_collector.collect_run_evidence("owner", "repo", 12345)
    
    assert evidence_collector.pinned_sha == "1234567890abcdef" * 2 + "12345678"
    assert evidence_data["pinned_sha"] == evidence_collector.pinned_sha
