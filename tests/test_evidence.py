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

    result = collector.fetch_source_files("owner", "repo", ["src/main.py"])

    assert "src/main.py" in result["files"]
    assert result["files"]["src/main.py"] == "print('hello')"


def test_fetch_source_files_respects_limit():
    """Test that file fetching respects max_files limit."""
    files = {f"file{i}.py": f"content{i}" for i in range(100)}
    github = FakeGitHubClient(files=files)
    redactor = SecretRedactor()
    limiter = SizeLimiter(max_files=5)

    collector = EvidenceCollector(github, redactor, limiter)
    collector.collect_run_evidence("owner", "repo", 12345)

    file_paths = [f"file{i}.py" for i in range(100)]
    result = collector.fetch_source_files("owner", "repo", file_paths)

    assert len(result["files"]) <= 5
    assert any("maximum file limit" in lim.lower() for lim in result["limitations"])


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


# ============================================================================
# REGRESSION TESTS FOR BUG FIXES
# ============================================================================


def test_bug3_permission_error_preserved_in_limitations():
    """
    BUG 3 REGRESSION TEST: When get_job_logs raises PermissionError,
    the collector should record an accurate limitation message.
    """
    from pipeline_doctor.github_client import PermissionError as GitHubPermissionError
    
    class PermissionDeniedGitHubClient(FakeGitHubClient):
        def get_job_logs(self, owner, repo, job_id):
            raise GitHubPermissionError("HTTP 403: Forbidden")
    
    github = PermissionDeniedGitHubClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()
    
    collector = EvidenceCollector(github, redactor, limiter)
    result = collector.collect_run_evidence("owner", "repo", 12345)
    
    # Check that the limitation mentions insufficient permissions
    assert any("insufficient permissions" in lim.lower() for lim in result["limitations"])


def test_bug3_rate_limit_error_preserved_in_limitations():
    """
    BUG 3 REGRESSION TEST: When get_job_logs raises RateLimitError,
    the collector should record it accurately.
    """
    from pipeline_doctor.github_client import RateLimitError
    
    class RateLimitedGitHubClient(FakeGitHubClient):
        def get_job_logs(self, owner, repo, job_id):
            raise RateLimitError("Rate limit exceeded", reset_at=1234567890)
    
    github = RateLimitedGitHubClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()
    
    collector = EvidenceCollector(github, redactor, limiter)
    result = collector.collect_run_evidence("owner", "repo", 12345)
    
    # Check that the limitation mentions rate limit
    assert any("rate limit" in lim.lower() for lim in result["limitations"])


def test_bug5_fetch_source_files_records_all_failures():
    """
    BUG 5 REGRESSION TEST: fetch_source_files should record each failure
    as a limitation instead of silently swallowing exceptions.
    """
    from pipeline_doctor.github_client import NotFoundError
    
    class SelectiveGitHubClient(FakeGitHubClient):
        def get_file_content(self, owner, repo, path, ref):
            if path == "exists.py":
                return "print('exists')"
            elif path == "missing.py":
                raise NotFoundError("HTTP 404: Not Found")
            elif path == "denied.py":
                from pipeline_doctor.github_client import PermissionError as GitHubPermissionError
                raise GitHubPermissionError("HTTP 403: Forbidden")
            else:
                raise Exception("Unknown error")
    
    github = SelectiveGitHubClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()
    
    collector = EvidenceCollector(github, redactor, limiter)
    collector.collect_run_evidence("owner", "repo", 12345)
    
    result = collector.fetch_source_files("owner", "repo", [
        "exists.py", "missing.py", "denied.py", "error.py"
    ])
    
    # Should successfully fetch the one that exists
    assert "exists.py" in result["files"]
    
    # Should have limitations for the failures
    limitations = result["limitations"]
    assert any("missing.py" in lim and "not found" in lim.lower() for lim in limitations)
    assert any("denied.py" in lim and "permission" in lim.lower() for lim in limitations)
    assert any("error.py" in lim for lim in limitations)


def test_bug5_fetch_source_files_directory_error():
    """
    BUG 5 REGRESSION TEST: When fetch_source_files encounters a directory,
    it should record a clear limitation.
    """
    from pipeline_doctor.github_client import NotAFileError
    
    class DirectoryGitHubClient(FakeGitHubClient):
        def get_file_content(self, owner, repo, path, ref):
            if path == "src":
                raise NotAFileError("Path is a directory, not a file: src")
            return "content"
    
    github = DirectoryGitHubClient()
    redactor = SecretRedactor()
    limiter = SizeLimiter()
    
    collector = EvidenceCollector(github, redactor, limiter)
    collector.collect_run_evidence("owner", "repo", 12345)
    
    result = collector.fetch_source_files("owner", "repo", ["src", "file.py"])
    
    # Should record the directory limitation
    limitations = result["limitations"]
    assert any("src" in lim and "directory" in lim.lower() for lim in limitations)
    
    # Should still fetch the file
    assert "file.py" in result["files"]


def test_bug5_fetch_source_files_returns_dict_with_limitations():
    """
    BUG 5 REGRESSION TEST: fetch_source_files should return a dict with
    both 'files' and 'limitations' keys.
    """
    github = FakeGitHubClient(files={"test.py": "content"})
    redactor = SecretRedactor()
    limiter = SizeLimiter()
    
    collector = EvidenceCollector(github, redactor, limiter)
    collector.collect_run_evidence("owner", "repo", 12345)
    
    result = collector.fetch_source_files("owner", "repo", ["test.py"])
    
    # Should return a dict with both keys
    assert isinstance(result, dict)
    assert "files" in result
    assert "limitations" in result
    assert isinstance(result["files"], dict)
    assert isinstance(result["limitations"], list)
