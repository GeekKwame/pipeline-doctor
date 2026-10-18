#!/usr/bin/env python3
"""
CLI tool to diagnose a GitHub Actions workflow run.

This script demonstrates the real GitHub client in action.
GITHUB_TOKEN is optional (works with public repos, logs may be unavailable).
Grok client can be real (with GROK_API_KEY) or fake (with --fake flag).

Usage:
    # With real Grok (requires GROK_API_KEY):
    export GROK_API_KEY="xai-..."
    python examples/diagnose_run.py owner/repo 12345
    
    # With fake Grok (for testing):
    python examples/diagnose_run.py --fake owner/repo 12345
    
    # Public repo without GitHub token (logs may be unavailable):
    python examples/diagnose_run.py owner/repo 12345

Output:
    Prints a validated incident report in JSON format.
    Does NOT execute any AI-generated commands.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline_doctor.evidence import EvidenceCollector
from pipeline_doctor.github_client import GitHubClient, GitHubAPIError, NotFoundError, RateLimitError
from pipeline_doctor.grok_client import FakeGrokClient, GrokAPIClient, GrokAPIError
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
    parser = argparse.ArgumentParser(
        description="Diagnose a GitHub Actions workflow run failure",
        epilog="Does NOT execute AI-generated commands automatically."
    )
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Use fake Grok client instead of real API (for testing)"
    )
    parser.add_argument(
        "repository",
        help="Repository in owner/repo format"
    )
    parser.add_argument(
        "run_id",
        type=int,
        help="GitHub Actions run ID"
    )
    
    args = parser.parse_args()
    
    # Parse arguments
    try:
        owner, repo = parse_repository(args.repository)
        run_id = args.run_id
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Check for tokens
    github_token = os.environ.get("GITHUB_TOKEN")
    grok_api_key = os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY")
    
    if not github_token:
        print("Warning: GITHUB_TOKEN not set. Using unauthenticated GitHub access.", file=sys.stderr)
        print("         Job logs may be unavailable.", file=sys.stderr)
        print("", file=sys.stderr)
    
    # Determine which Grok client to use
    use_fake_grok = args.fake or not grok_api_key
    
    if use_fake_grok and not args.fake:
        print("Warning: GROK_API_KEY not set. Using fake Grok client.", file=sys.stderr)
        print("", file=sys.stderr)
    elif args.fake:
        print("Using fake Grok client (--fake flag)", file=sys.stderr)
        print("", file=sys.stderr)

    print(f"Diagnosing workflow run: {owner}/{repo} run_id={run_id}", file=sys.stderr)
    if github_token:
        print(f"GitHub token: {'*' * 10} (redacted)", file=sys.stderr)
    print(f"Grok client: {'fake' if use_fake_grok else 'real'}", file=sys.stderr)
    print("", file=sys.stderr)

    # Set up components
    try:
        github = GitHubClient(token=github_token, max_requests=50)
        redactor = SecretRedactor()
        limiter = SizeLimiter()
        
        if use_fake_grok:
            grok = FakeGrokClient()
        else:
            grok = GrokAPIClient(api_key=grok_api_key)

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
            
            if result.limitations:
                print(f"\nLimitations:", file=sys.stderr)
                for limitation in result.limitations:
                    print(f"  - {limitation}", file=sys.stderr)
            
            print("\n--- Full Report (JSON) ---\n", file=sys.stderr)
            
            # Output JSON to stdout
            report_dict = result.report.model_dump(mode="json")
            print(json.dumps(report_dict, indent=2))
        else:
            print("\n❌ Diagnosis failed", file=sys.stderr)
            print("Errors:", file=sys.stderr)
            for error in result.errors:
                print(f"  - {error}", file=sys.stderr)
            
            if result.limitations:
                print(f"\nLimitations:", file=sys.stderr)
                for limitation in result.limitations:
                    print(f"  - {limitation}", file=sys.stderr)
            
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
    except GrokAPIError as e:
        print(f"\n❌ Grok API error: {e}", file=sys.stderr)
        if hasattr(e, 'status_code') and e.status_code:
            print(f"Status code: {e.status_code}", file=sys.stderr)
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
