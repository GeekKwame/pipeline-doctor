"""Evidence collection from GitHub Actions runs."""

from typing import Dict, List, Optional

from .protocols import GitHubClient
from .redaction import SecretRedactor, SizeLimiter


class EvidenceItem:
    """Evidence item collected from GitHub."""

    def __init__(
        self,
        id: str,
        type: str,
        source: str,
        location: str,
        content: str,
        observation: str,
    ):
        self.id = id
        self.type = type
        self.source = source
        self.location = location
        self.content = content
        self.observation = observation


class EvidenceCollector:
    """Collects evidence from GitHub Actions runs."""

    def __init__(
        self,
        github_client: GitHubClient,
        redactor: SecretRedactor,
        limiter: SizeLimiter,
    ):
        """
        Initialize evidence collector.

        Args:
            github_client: GitHub API client
            redactor: Secret redactor
            limiter: Size limiter
        """
        self.github = github_client
        self.redactor = redactor
        self.limiter = limiter
        self.pinned_sha: Optional[str] = None
        self.evidence_counter = 0

    def collect_run_evidence(
        self,
        owner: str,
        repo: str,
        run_id: int,
    ) -> Dict[str, any]:
        """
        Collect evidence from a workflow run.

        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID

        Returns:
            Dictionary containing:
                - run_metadata: Run metadata dict
                - failed_job: Failed job dict or None
                - logs: Redacted log content or None
                - workflow_yaml: Workflow YAML content or None
                - evidence_items: List of EvidenceItem objects
                - limitations: List of limitation strings
                - pinned_sha: Commit SHA used for all file fetches
        """
        evidence_items = []
        limitations = []

        try:
            run_metadata = self.github.get_workflow_run(owner, repo, run_id)
        except Exception as e:
            limitations.append(f"Failed to fetch run metadata: {str(e)}")
            return {
                "run_metadata": None,
                "failed_job": None,
                "logs": None,
                "workflow_yaml": None,
                "evidence_items": [],
                "limitations": limitations,
                "pinned_sha": None,
            }

        self.pinned_sha = run_metadata.get("head_sha")
        if not self.pinned_sha:
            limitations.append("Could not determine commit SHA from run metadata")

        jobs = []
        try:
            jobs = self.github.list_jobs(owner, repo, run_id)
        except Exception as e:
            limitations.append(f"Failed to list jobs: {str(e)}")

        failed_job = None
        for job in jobs:
            if job.get("conclusion") == "failure":
                failed_job = job
                break

        logs = None
        if failed_job:
            try:
                raw_logs = self.github.get_job_logs(owner, repo, failed_job["id"])
                truncated_logs = self.limiter.truncate_log(raw_logs)
                logs = self.redactor.redact(truncated_logs)

                evidence_items.append(
                    EvidenceItem(
                        id=self._next_evidence_id(),
                        type="log",
                        source=f"Job: {failed_job.get('name', 'unknown')}",
                        location=failed_job.get("html_url", ""),
                        content=logs,
                        observation="Job failure logs",
                    )
                )
            except Exception as e:
                # Preserve specific error types for accurate limitation messages
                from .github_client import PermissionError as GitHubPermissionError, RateLimitError
                
                if isinstance(e, GitHubPermissionError):
                    limitations.append("insufficient permissions to download logs")
                elif isinstance(e, RateLimitError):
                    limitations.append(f"rate limit exceeded while fetching logs: {str(e)}")
                else:
                    limitations.append(f"Failed to fetch job logs: {str(e)}")

        workflow_yaml = None
        workflow_path = run_metadata.get("path")
        if workflow_path and self.pinned_sha:
            try:
                raw_yaml = self.github.get_workflow_file(owner, repo, workflow_path, self.pinned_sha)
                workflow_yaml = self.redactor.redact(raw_yaml)

                evidence_items.append(
                    EvidenceItem(
                        id=self._next_evidence_id(),
                        type="workflow_yaml",
                        source="GitHub Actions Workflow",
                        location=workflow_path,
                        content=workflow_yaml,
                        observation="Workflow configuration",
                    )
                )
            except Exception as e:
                limitations.append(f"Failed to fetch workflow file: {str(e)}")

        return {
            "run_metadata": run_metadata,
            "failed_job": failed_job,
            "logs": logs,
            "workflow_yaml": workflow_yaml,
            "evidence_items": evidence_items,
            "limitations": limitations,
            "pinned_sha": self.pinned_sha,
        }

    def fetch_source_files(
        self,
        owner: str,
        repo: str,
        file_paths: List[str],
    ) -> Dict[str, any]:
        """
        Fetch source files at the pinned commit SHA.

        Args:
            owner: Repository owner
            repo: Repository name
            file_paths: List of file paths to fetch

        Returns:
            Dictionary containing:
                - files: Dictionary mapping file paths to redacted content
                - limitations: List of limitation strings for failed fetches
        """
        if not self.pinned_sha:
            return {"files": {}, "limitations": ["No pinned SHA available for file fetching"]}

        files = {}
        limitations = []
        fetched_count = 0

        for path in file_paths:
            if fetched_count >= self.limiter.max_files:
                limitations.append(f"Maximum file limit reached ({self.limiter.max_files}), skipping remaining files")
                break

            try:
                raw_content = self.github.get_file_content(owner, repo, path, self.pinned_sha)
                truncated = self.limiter.truncate_file(raw_content)
                files[path] = self.redactor.redact(truncated)
                fetched_count += 1
            except Exception as e:
                # Record each failure as a limitation
                from .github_client import (
                    NotAFileError, 
                    NotFoundError, 
                    PermissionError as GitHubPermissionError,
                    RateLimitError
                )
                
                if isinstance(e, NotAFileError):
                    limitations.append(f"Cannot fetch {path}: path is a directory")
                elif isinstance(e, NotFoundError):
                    limitations.append(f"File not found: {path}")
                elif isinstance(e, GitHubPermissionError):
                    limitations.append(f"Insufficient permissions to fetch {path}")
                elif isinstance(e, RateLimitError):
                    limitations.append(f"Rate limit exceeded while fetching {path}")
                else:
                    limitations.append(f"Failed to fetch {path}: {str(e)}")

        return {"files": files, "limitations": limitations}

    def _next_evidence_id(self) -> str:
        """Generate next evidence ID."""
        self.evidence_counter += 1
        return f"E{self.evidence_counter}"
