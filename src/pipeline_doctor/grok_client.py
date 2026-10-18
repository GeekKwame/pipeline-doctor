"""Grok AI client implementation."""

import json
import os
import time
from typing import Optional

import requests


class GrokAPIError(Exception):
    """Base exception for Grok API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class GrokAPIClient:
    """Real Grok API client implementation."""

    def __init__(
        self, 
        api_key: Optional[str] = None, 
        base_url: str = "https://api.x.ai/v1",
        model: Optional[str] = None,
        connect_timeout: float = 30.0,
        read_timeout: float = 120.0,
        max_retries: int = 3,
    ):
        """
        Initialize Grok API client.

        Args:
            api_key: xAI API key (defaults to GROK_API_KEY or XAI_API_KEY env var)
            base_url: Base URL for xAI API
            model: Default model to use (defaults to GROK_MODEL env var or 'grok-beta')
            connect_timeout: Connection timeout in seconds
            read_timeout: Read timeout in seconds
            max_retries: Maximum number of retries for 429/5xx errors
        """
        self.api_key = api_key or os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("Grok API key required: set GROK_API_KEY or XAI_API_KEY environment variable")

        self.base_url = base_url
        self.default_model = model or os.environ.get("GROK_MODEL", "grok-beta")
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_retries = max_retries

    def chat_completion(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,
    ) -> str:
        """
        Send chat completion request to Grok.

        Args:
            system_prompt: System prompt
            user_message: User message
            model: Model identifier (defaults to constructor default or 'grok-beta')
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate (optional)
            response_format: Response format, e.g. 'json_object' for JSON mode (optional)

        Returns:
            Model response as string

        Raises:
            GrokAPIError: On API errors with status code and truncated response body
        """
        url = f"{self.base_url}/chat/completions"
        
        model_to_use = model or self.default_model

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": model_to_use,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        if response_format is not None:
            payload["response_format"] = {"type": response_format}

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    url, 
                    headers=headers, 
                    json=payload, 
                    timeout=(self.connect_timeout, self.read_timeout)
                )
                
                # Check for errors - this may retry or raise
                if not response.ok:
                    should_retry = self._handle_error_response(response, attempt)
                    if should_retry:
                        continue  # Retry the loop
                    # If we reach here, _handle_error_response raised
                
                data = response.json()
                
                # Validate response structure
                if "choices" not in data:
                    raise GrokAPIError(
                        "Response missing 'choices' field",
                        status_code=response.status_code,
                        response_body=self._truncate_response(response.text)
                    )
                
                if not data["choices"]:
                    raise GrokAPIError(
                        "Response has empty 'choices' array",
                        status_code=response.status_code,
                        response_body=self._truncate_response(response.text)
                    )
                
                choice = data["choices"][0]
                if "message" not in choice:
                    raise GrokAPIError(
                        "Choice missing 'message' field",
                        status_code=response.status_code,
                        response_body=self._truncate_response(response.text)
                    )
                
                message = choice["message"]
                if "content" not in message:
                    raise GrokAPIError(
                        "Message missing 'content' field",
                        status_code=response.status_code,
                        response_body=self._truncate_response(response.text)
                    )
                
                content = message["content"]
                if content is None:
                    raise GrokAPIError(
                        "Message content is null",
                        status_code=response.status_code,
                        response_body=self._truncate_response(response.text)
                    )
                
                # Check for truncation
                finish_reason = choice.get("finish_reason")
                if finish_reason == "length":
                    raise GrokAPIError(
                        "Response was truncated (finish_reason: length). Increase max_tokens.",
                        status_code=response.status_code,
                        response_body=self._truncate_response(response.text)
                    )
                
                return content
                
            except GrokAPIError:
                raise
            except requests.exceptions.Timeout as e:
                last_exception = GrokAPIError(f"Request timeout: {str(e)}")
                if attempt == self.max_retries:
                    raise last_exception
            except requests.exceptions.RequestException as e:
                last_exception = GrokAPIError(f"Request failed: {str(e)}")
                if attempt == self.max_retries:
                    raise last_exception
            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
                raise GrokAPIError(f"Failed to parse response: {str(e)}")
        
        # Should not reach here, but just in case
        raise last_exception or GrokAPIError("Maximum retries exceeded")
    
    def _handle_error_response(self, response: requests.Response, attempt: int) -> bool:
        """
        Handle non-2xx responses with retries for 429/5xx.
        
        Args:
            response: Response object
            attempt: Current attempt number (0-indexed)
            
        Returns:
            True if should retry, False otherwise (will raise)
            
        Raises:
            GrokAPIError: Always raises if not retrying
        """
        status_code = response.status_code
        
        # Get response body, redacting API key if present
        try:
            body = response.text
        except:
            body = ""
        
        body = self._redact_api_key(body)
        truncated_body = self._truncate_response(body)
        
        # Retry logic for 429 and 5xx
        if status_code == 429 or (500 <= status_code < 600):
            if attempt < self.max_retries:
                # Exponential backoff: 1s, 2s, 4s, 8s, etc.
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                return True  # Signal retry
        
        # Build error message
        error_msg = f"API request failed with status {status_code}"
        if truncated_body:
            error_msg += f": {truncated_body}"
        
        raise GrokAPIError(error_msg, status_code=status_code, response_body=truncated_body)
    
    def _truncate_response(self, text: str, max_length: int = 500) -> str:
        """Truncate response body to avoid huge error messages."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "... (truncated)"
    
    def _redact_api_key(self, text: str) -> str:
        """Redact API key from text if present."""
        if self.api_key and self.api_key in text:
            return text.replace(self.api_key, "[REDACTED-API-KEY]")
        return text


class FakeGrokClient:
    """Fake Grok client for testing."""

    def __init__(
        self, 
        canned_response: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize fake client.

        Args:
            canned_response: Fixed response to return
            model: Default model (unused, for compatibility)
        """
        self.canned_response = canned_response or self._default_response()
        self.default_model = model or "grok-beta"
        self.calls = []

    def chat_completion(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,
    ) -> str:
        """
        Return canned response and record call.

        Args:
            system_prompt: System prompt
            user_message: User message
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens (unused)
            response_format: Response format (unused)

        Returns:
            Canned response string
        """
        self.calls.append({
            "system_prompt": system_prompt,
            "user_message": user_message,
            "model": model or self.default_model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": response_format,
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
