#!/usr/bin/env python3
"""
CLI tool to diagnose a GitHub Actions workflow run.

This script demonstrates the real GitHub client in action.
Requires GITHUB_TOKEN environment variable.

Usage:
    export GITHUB_TOKEN="ghp_your_token_here"
    python examples/diagnose_run.py owner/repo 12345

Output:
    Prints a validated incident report in JSON format.
    Does NOT execute any AI-generated commands.
"""

import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline_doctor.evidence import EvidenceCollector
from pipeline_doctor.github_client import GitHubClient, GitHubAPIError, NotFoundError, RateLimitError
from pipeline_doctor.grok_client import FakeGrokClient
from pipeline_doctor.orchestrator import DiagnosisOrchestrator
from pipeline_doctor.prompts import PromptLoader
from pipeline_doctor.redaction import SecretRedactor, SizeLimiter
from pipeline_doctor.validator import IncidentReportValidator


def parse_repository(repo_arg: str) -> tuple[str, str]:
    """Parse owner/repo format."""
    if "/" not in repo_arg:
        raise ValueError("Repository must be in owner/repo format")
    parts = repo_arg.split("/")
    if len(parts) != 2:
        raise ValueError("Repository must be in owner/repo format")
    return parts[0], parts[1]


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage: python diagnose_run.py owner/repo run_id", file=sys.stderr)
        print("\nExample: python diagnose_run.py octocat/hello-world 12345", file=sys.stderr)
        sys.exit(1)

    # Parse arguments
    try:
        owner, repo = parse_repository(sys.argv[1])
        run_id = int(sys.argv[2])
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Check for token
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set", file=sys.stderr)
        print("\nSet your token with:", file=sys.stderr)
        print("  export GITHUB_TOKEN='ghp_your_token_here'", file=sys.stderr)
        sys.exit(1)

    print(f"Diagnosing workflow run: {owner}/{repo} run_id={run_id}", file=sys.stderr)
    print(f"Token: {'*' * 10} (redacted)", file=sys.stderr)
    print("", file=sys.stderr)

    # Set up components
    try:
        github = GitHubClient(token=token, max_requests=50)
        redactor = SecretRedactor()
        limiter = SizeLimiter()
        grok = FakeGrokClient()  # Using fake client for demo

        evidence_collector = EvidenceCollector(github, redactor, limiter)
        
        # Try to find prompts directory
        prompts_dir = Path(__file__).parent.parent / "prompts"
        if not prompts_dir.exists():
            prompts_dir = Path("prompts")
        
        prompt_loader = PromptLoader(prompts_dir)
        validator = IncidentReportValidator()

        orchestrator = DiagnosisOrchestrator(
            evidence_collector,
            grok,
            prompt_loader,
            validator,
            redactor,
        )

        print("Collecting evidence...", file=sys.stderr)
        result = orchestrator.diagnose(owner, repo, run_id)

        if result.success:
            print("\n✅ Diagnosis successful!", file=sys.stderr)
            print(f"Root cause: {result.report.diagnosis.root_cause}", file=sys.stderr)
            print(f"Confidence: {result.report.diagnosis.confidence_level}", file=sys.stderr)
            print(f"Evidence items: {len(result.report.evidence)}", file=sys.stderr)
            print(f"API requests made: {github.request_count}", file=sys.stderr)
            print("\n--- Full Report (JSON) ---\n", file=sys.stderr)
            
            # Output JSON to stdout
            report_dict = result.report.model_dump(mode="json")
            print(json.dumps(report_dict, indent=2))
        else:
            print("\n❌ Diagnosis failed", file=sys.stderr)
            print("Errors:", file=sys.stderr)
            for error in result.errors:
                print(f"  - {error}", file=sys.stderr)
            sys.exit(1)

    except NotFoundError as e:
        print(f"\n❌ Resource not found: {e}", file=sys.stderr)
        print("\nMake sure the run_id exists and you have access to it.", file=sys.stderr)
        sys.exit(1)
    except RateLimitError as e:
        print(f"\n❌ Rate limit exceeded: {e}", file=sys.stderr)
        if e.reset_at:
            import datetime
            reset_time = datetime.datetime.fromtimestamp(e.reset_at)
            print(f"Rate limit resets at: {reset_time}", file=sys.stderr)
        sys.exit(1)
    except GitHubAPIError as e:
        print(f"\n❌ GitHub API error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
