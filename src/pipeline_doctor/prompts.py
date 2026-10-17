"""Prompt template loading and formatting."""

from pathlib import Path
from typing import Dict, List


class PromptLoader:
    """Loads and formats prompt templates."""

    def __init__(self, prompts_dir: Path):
        """
        Initialize prompt loader.

        Args:
            prompts_dir: Directory containing prompt templates
        """
        self.prompts_dir = prompts_dir

    def load_system_prompt(self) -> str:
        """
        Load the diagnosis system prompt.

        Returns:
            System prompt text
        """
        prompt_path = self.prompts_dir / "diagnosis_system_prompt.md"
        with open(prompt_path, "r") as f:
            return f.read()

    def format_user_message(
        self,
        run_metadata: Dict,
        failed_job: Dict,
        logs: str,
        workflow_yaml: str,
        source_files: Dict[str, str],
        limitations: List[str],
    ) -> str:
        """
        Format user message with evidence.

        Args:
            run_metadata: Workflow run metadata
            failed_job: Failed job metadata
            logs: Job logs (redacted)
            workflow_yaml: Workflow YAML content (redacted)
            source_files: Dictionary of file paths to content (redacted)
            limitations: List of limitations

        Returns:
            Formatted user message
        """
        parts = ["# GitHub Actions Failure Analysis Request\n"]

        parts.append("## Run Metadata")
        parts.append("```json")
        parts.append(self._format_dict(run_metadata))
        parts.append("```\n")

        if failed_job:
            parts.append("## Failed Job")
            parts.append("```json")
            parts.append(self._format_dict(failed_job))
            parts.append("```\n")

        if logs:
            parts.append("## Job Logs")
            parts.append("```")
            parts.append(logs)
            parts.append("```\n")

        if workflow_yaml:
            parts.append("## Workflow Configuration")
            parts.append("```yaml")
            parts.append(workflow_yaml)
            parts.append("```\n")

        if source_files:
            parts.append("## Source Files")
            for path, content in source_files.items():
                parts.append(f"### {path}")
                parts.append("```")
                parts.append(content)
                parts.append("```\n")

        if limitations:
            parts.append("## Limitations")
            for limitation in limitations:
                parts.append(f"- {limitation}")
            parts.append("")

        parts.append("Analyze this failure and provide a complete incident report in JSON format.")

        return "\n".join(parts)

    def _format_dict(self, data: Dict) -> str:
        """Format dictionary as pretty JSON."""
        import json
        return json.dumps(data, indent=2, default=str)


def create_prompt_loader(prompts_dir: Path) -> PromptLoader:
    """
    Factory function to create a prompt loader.

    Args:
        prompts_dir: Directory containing prompt templates

    Returns:
        Configured prompt loader
    """
    return PromptLoader(prompts_dir)
