"""GitHub API client implementations."""

from typing import Any, Dict, List


class FakeGitHubClient:
    """Fake GitHub client for testing."""

    def __init__(
        self,
        run_data: Dict[str, Any] = None,
        jobs_data: List[Dict[str, Any]] = None,
        logs: str = "",
        files: Dict[str, str] = None,
    ):
        """
        Initialize fake client with test data.

        Args:
            run_data: Workflow run metadata
            jobs_data: List of job dictionaries
            logs: Job log content
            files: Dictionary mapping file paths to content
        """
        self.run_data = run_data or self._default_run_data()
        self.jobs_data = jobs_data or self._default_jobs_data()
        self.logs = logs or self._default_logs()
        self.files = files or {}

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> Dict[str, Any]:
        """Get workflow run metadata."""
        return self.run_data

    def list_jobs(self, owner: str, repo: str, run_id: int) -> List[Dict[str, Any]]:
        """List jobs for a workflow run."""
        return self.jobs_data

    def get_job_logs(self, owner: str, repo: str, job_id: int) -> str:
        """Download logs for a job."""
        return self.logs

    def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        """Get file content at a specific commit."""
        if path in self.files:
            return self.files[path]
        raise FileNotFoundError(f"File not found: {path}")

    def get_workflow_file(self, owner: str, repo: str, workflow_path: str, ref: str) -> str:
        """Get workflow YAML content."""
        if workflow_path in self.files:
            return self.files[workflow_path]
        return self._default_workflow_yaml()

    def _default_run_data(self) -> Dict[str, Any]:
        """Generate default run data."""
        return {
            "id": 12345,
            "name": "CI",
            "head_sha": "a" * 40,
            "head_branch": "main",
            "event": "push",
            "status": "completed",
            "conclusion": "failure",
            "workflow_id": 123,
            "html_url": "https://github.com/owner/repo/actions/runs/12345",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:05:00Z",
            "path": ".github/workflows/ci.yml",
            "repository": {
                "full_name": "owner/repo",
            },
        }

    def _default_jobs_data(self) -> List[Dict[str, Any]]:
        """Generate default jobs data."""
        return [
            {
                "id": 1001,
                "run_id": 12345,
                "name": "test",
                "status": "completed",
                "conclusion": "failure",
                "started_at": "2024-01-01T00:01:00Z",
                "completed_at": "2024-01-01T00:05:00Z",
                "html_url": "https://github.com/owner/repo/actions/runs/12345/job/1001",
                "steps": [
                    {
                        "name": "Set up job",
                        "status": "completed",
                        "conclusion": "success",
                        "number": 1,
                    },
                    {
                        "name": "Checkout code",
                        "status": "completed",
                        "conclusion": "success",
                        "number": 2,
                    },
                    {
                        "name": "Run tests",
                        "status": "completed",
                        "conclusion": "failure",
                        "number": 3,
                    },
                ],
            }
        ]

    def _default_logs(self) -> str:
        """Generate default log content."""
        return """2024-01-01T00:01:00.000Z Setting up job
2024-01-01T00:01:05.000Z Checking out code
2024-01-01T00:02:00.000Z Running tests
2024-01-01T00:03:00.000Z pytest test_example.py
2024-01-01T00:03:05.000Z ERROR: test_critical_function failed
2024-01-01T00:03:05.000Z AssertionError: expected 42 but got 43
2024-01-01T00:03:05.000Z   File "test_example.py", line 15, in test_critical_function
2024-01-01T00:03:05.000Z     assert result == 42
2024-01-01T00:05:00.000Z Tests failed
"""

    def _default_workflow_yaml(self) -> str:
        """Generate default workflow YAML."""
        return """name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest
"""
