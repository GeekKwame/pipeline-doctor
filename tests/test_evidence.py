"""Tests for evidence collector."""

import pytest

from pipeline_doctor.evidence import EvidenceCollector
from pipeline_doctor.github_client import FakeGitHubClient
from pipeline_doctor.redaction import SecretRedactor, SizeLimiter


def test_collect_run_evidence():
    """Test collecting evidence from a workflow run."""
    github = FakeGitHubClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()

    collector = EvidenceCollector(github, redactor, limiter)

    result = collector.collect_run_evidence("owner", "repo", 12345)

    assert result["run_metadata"] is not None
    assert result["failed_job"] is not None
    assert result["logs"] is not None
    assert result["workflow_yaml"] is not None
    assert len(result["evidence_items"]) > 0
    assert result["pinned_sha"] == "a" * 40


def test_collect_with_failed_logs():
    """Test handling failed log retrieval."""

    class FailingGitHubClient(FakeGitHubClient):
        def get_job_logs(self, owner, repo, job_id):
            raise Exception("Log download failed")

    github = FailingGitHubClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()

    collector = EvidenceCollector(github, redactor, limiter)
    result = collector.collect_run_evidence("owner", "repo", 12345)

    assert result["logs"] is None
    assert any("Failed to fetch job logs" in lim for lim in result["limitations"])


def test_collect_with_unavailable_workflow():
    """Test handling unavailable workflow file."""

    class NoWorkflowGitHubClient(FakeGitHubClient):
        def get_workflow_file(self, owner, repo, workflow_path, ref):
            raise FileNotFoundError("Workflow not found")

    github = NoWorkflowGitHubClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()

    collector = EvidenceCollector(github, redactor, limiter)
    result = collector.collect_run_evidence("owner", "repo", 12345)

    assert result["workflow_yaml"] is None
    assert any("Failed to fetch workflow file" in lim for lim in result["limitations"])


def test_fetch_source_files():
    """Test fetching source files."""
    github = FakeGitHubClient(files={"src/main.py": "print('hello')"})
    redactor = SecretRedactor()
    limiter = SizeLimiter()

    collector = EvidenceCollector(github, redactor, limiter)
    collector.collect_run_evidence("owner", "repo", 12345)

    files = collector.fetch_source_files("owner", "repo", ["src/main.py"])

    assert "src/main.py" in files
    assert files["src/main.py"] == "print('hello')"


def test_fetch_source_files_respects_limit():
    """Test that file fetching respects max_files limit."""
    files = {f"file{i}.py": f"content{i}" for i in range(100)}
    github = FakeGitHubClient(files=files)
    redactor = SecretRedactor()
    limiter = SizeLimiter(max_files=5)

    collector = EvidenceCollector(github, redactor, limiter)
    collector.collect_run_evidence("owner", "repo", 12345)

    file_paths = [f"file{i}.py" for i in range(100)]
    fetched = collector.fetch_source_files("owner", "repo", file_paths)

    assert len(fetched) <= 5


def test_sha_pinning():
    """Test that commit SHA is pinned at start."""
    github = FakeGitHubClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()

    collector = EvidenceCollector(github, redactor, limiter)
    result = collector.collect_run_evidence("owner", "repo", 12345)

    assert collector.pinned_sha is not None
    assert collector.pinned_sha == result["pinned_sha"]


def test_evidence_id_generation():
    """Test evidence ID generation."""
    github = FakeGitHubClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()

    collector = EvidenceCollector(github, redactor, limiter)
    result = collector.collect_run_evidence("owner", "repo", 12345)

    ids = [item.id for item in result["evidence_items"]]
    assert len(ids) == len(set(ids))
    assert all(id.startswith("E") for id in ids)
