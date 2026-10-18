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
        evidence_items: List = None,
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
            evidence_items: List of evidence items with IDs

        Returns:
            Formatted user message
        """
        parts = ["# GitHub Actions Failure Analysis Request\n"]

        # Add Evidence Index at the top if evidence items are provided
        if evidence_items:
            parts.append("## Evidence Index")
            parts.append("")
            parts.append("The following evidence items have been collected. Use these IDs when citing evidence:")
            parts.append("")
            for item in evidence_items:
                parts.append(f"- **{item.id}**: {item.type} - {item.source}")
                parts.append(f"  Location: {item.location}")
                parts.append(f"  Observation: {item.observation}")
            parts.append("")

        parts.append("<!-- UNTRUSTED DATA BEGINS -->")
        parts.append("")

        parts.append("## Run Metadata")
        parts.append("```json")
        parts.append(self._format_dict(self._filter_run_metadata(run_metadata)))
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

        parts.append("<!-- UNTRUSTED DATA ENDS -->")
        parts.append("")

        if limitations:
            parts.append("## Limitations")
            parts.append("")
            parts.append("The following information was unavailable or incomplete:")
            parts.append("")
            for limitation in limitations:
                parts.append(f"- {limitation}")
            parts.append("")
            parts.append("**Important**: When evidence is thin or logs are missing, you MUST:")
            parts.append("- Use category 'insufficient_evidence' if you cannot determine the root cause")
            parts.append("- Set confidence_level to 'low' or 'insufficient'")
            parts.append("- List the specific missing data in the limitations field")
            parts.append("- Explain in the diagnosis what additional information would be needed")
            parts.append("")

        parts.append("Analyze this failure and provide a complete incident report in JSON format.")
        parts.append("IMPORTANT: Reference evidence using the IDs from the Evidence Index above (E1, E2, etc.).")

        return "\n".join(parts)

    def _format_dict(self, data: Dict) -> str:
        """Format dictionary as pretty JSON."""
        import json
        return json.dumps(data, indent=2, default=str)

    def _filter_run_metadata(self, run_metadata: Dict) -> Dict:
        """
        Filter run metadata to include only relevant fields.
        
        Removes noisy fields like avatar URLs, follower counts, etc.
        
        Args:
            run_metadata: Full GitHub run metadata
            
        Returns:
            Filtered metadata dictionary
        """
        # Whitelist of fields to include
        allowed_fields = {
            'id', 'name', 'head_sha', 'head_branch', 'event', 'status', 
            'conclusion', 'workflow_id', 'html_url', 'created_at', 
            'updated_at', 'run_started_at', 'path', 'run_number', 
            'run_attempt', 'display_title'
        }
        
        filtered = {k: v for k, v in run_metadata.items() if k in allowed_fields}
        
        # Include simplified repository info
        if 'repository' in run_metadata:
            repo = run_metadata['repository']
            if isinstance(repo, dict):
                filtered['repository'] = {
                    'full_name': repo.get('full_name'),
                    'private': repo.get('private'),
                }
        
        return filtered


def create_prompt_loader(prompts_dir: Path) -> PromptLoader:
    """
    Factory function to create a prompt loader.

    Args:
        prompts_dir: Directory containing prompt templates

    Returns:
        Configured prompt loader
    """
    return PromptLoader(prompts_dir)
