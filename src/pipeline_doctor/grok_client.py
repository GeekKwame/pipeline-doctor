"""Grok AI client implementation."""

import json
import os
from typing import Optional

import requests


class GrokAPIClient:
    """Real Grok API client implementation."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.x.ai/v1"):
        """
        Initialize Grok API client.

        Args:
            api_key: xAI API key (defaults to GROK_API_KEY or XAI_API_KEY env var)
            base_url: Base URL for xAI API
        """
        self.api_key = api_key or os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("Grok API key required: set GROK_API_KEY or XAI_API_KEY environment variable")

        self.base_url = base_url

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

        Raises:
            requests.RequestException: On API errors
        """
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
        }

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]


class FakeGrokClient:
    """Fake Grok client for testing."""

    def __init__(self, canned_response: Optional[str] = None):
        """
        Initialize fake client.

        Args:
            canned_response: Fixed response to return
        """
        self.canned_response = canned_response or self._default_response()
        self.calls = []

    def chat_completion(
        self,
        system_prompt: str,
        user_message: str,
        model: str = "grok-beta",
        temperature: float = 0.1,
    ) -> str:
        """
        Return canned response and record call.

        Args:
            system_prompt: System prompt
            user_message: User message
            model: Model identifier
            temperature: Sampling temperature

        Returns:
            Canned response string
        """
        self.calls.append({
            "system_prompt": system_prompt,
            "user_message": user_message,
            "model": model,
            "temperature": temperature,
        })
        return self.canned_response

    def _default_response(self) -> str:
        """Generate a minimal valid incident report."""
        report = {
            "schema_version": "1.0.0",
            "incident": {
                "repository": "owner/repo",
                "run_id": 12345,
                "run_url": "https://github.com/owner/repo/actions/runs/12345",
                "commit_sha": "a" * 40,
                "branch": "main",
                "workflow_name": "CI",
                "workflow_path": ".github/workflows/ci.yml",
                "event": "push",
                "triggered_at": "2024-01-01T00:00:00Z",
                "conclusion": "failure",
            },
            "failure": {
                "category": "test_failure",
                "summary": "Tests failed",
                "job": {"name": "test", "id": 1, "url": "https://example.com"},
                "failed_step": {"name": "Run tests", "number": 3, "status": "completed"},
                "locations": [],
            },
            "diagnosis": {
                "root_cause": "Test failure",
                "technical_explanation": "Tests did not pass",
                "observed_facts": ["Test failed"],
                "inferences": ["Code has a bug"],
                "confidence": 0.6,
                "confidence_level": "medium",
                "supporting_evidence_ids": ["E1"],
                "primary_vs_cascading": "Primary failure",
                "alternative_hypotheses": [],
            },
            "evidence": [
                {
                    "id": "E1",
                    "type": "log",
                    "source": "Job logs",
                    "location": "https://example.com",
                    "log_excerpt": "Error: test failed",
                    "observation": "Test failure in logs",
                    "supports": "Root cause diagnosis",
                }
            ],
            "proposed_patch": {
                "available": False,
                "target_files": [],
                "change_type": "none",
                "unified_diff": None,
                "rationale": "Insufficient information for patch",
                "risk": {"level": "low", "description": "No changes proposed"},
                "requires_human_approval": True,
                "applied": False,
                "tested": False,
            },
            "verification": {
                "status": "not_run",
                "steps": [],
                "verified_at": None,
                "executed_by": None,
            },
            "limitations": ["Fake response for testing"],
        }
        return json.dumps(report, indent=2)
