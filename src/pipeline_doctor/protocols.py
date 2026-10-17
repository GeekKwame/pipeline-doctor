"""Protocol interfaces for dependency injection."""

from typing import Any, Dict, List, Optional, Protocol


class GitHubClient(Protocol):
    """Protocol for GitHub API client (read-only operations)."""

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> Dict[str, Any]:
        """
        Get workflow run metadata.

        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID

        Returns:
            Run metadata dictionary
        """
        ...

    def list_jobs(self, owner: str, repo: str, run_id: int) -> List[Dict[str, Any]]:
        """
        List jobs for a workflow run.

        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID

        Returns:
            List of job dictionaries
        """
        ...

    def get_job_logs(self, owner: str, repo: str, job_id: int) -> str:
        """
        Download logs for a job.

        Args:
            owner: Repository owner
            repo: Repository name
            job_id: Job ID

        Returns:
            Log content as string
        """
        ...

    def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        """
        Get file content at a specific commit.

        Args:
            owner: Repository owner
            repo: Repository name
            path: File path
            ref: Git ref (commit SHA)

        Returns:
            File content as string
        """
        ...

    def get_workflow_file(self, owner: str, repo: str, workflow_path: str, ref: str) -> str:
        """
        Get workflow YAML content.

        Args:
            owner: Repository owner
            repo: Repository name
            workflow_path: Path to workflow file
            ref: Git ref (commit SHA)

        Returns:
            Workflow YAML content
        """
        ...


class GrokClient(Protocol):
    """Protocol for Grok AI client."""

    def chat_completion(
        self,
        system_prompt: str,
        user_message: str,
        model: str = "grok-beta",
        temperature: float = 0.1,
    ) -> str:
        """
        Send chat completion request to Grok.

        Args:
            system_prompt: System prompt
            user_message: User message
            model: Model identifier
            temperature: Sampling temperature

        Returns:
            Model response as string
        """
        ...
