"""GitHub API client implementations."""

import base64
import os
import re
import zipfile
from io import BytesIO
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, quote
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""
    pass


class RateLimitError(GitHubAPIError):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, reset_at: Optional[int] = None):
        super().__init__(message)
        self.reset_at = reset_at


class NotFoundError(GitHubAPIError):
    """Raised when resource is not found."""
    pass


class GitHubPermissionError(GitHubAPIError):
    """Raised when access is denied (not rate limit)."""
    def __init__(self, message: str, status_code: int = None, response_message: str = None, accepted_permissions: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_message = response_message
        self.accepted_permissions = accepted_permissions


# Backward-compatible alias (avoid shadowing Python's builtin PermissionError)
PermissionError = GitHubPermissionError


class NotAFileError(GitHubAPIError):
    """Raised when path points to a directory, not a file."""
    pass


class SafeRedirectHandler(HTTPRedirectHandler):
    """
    Custom redirect handler that strips Authorization header on cross-host redirects.
    
    This prevents leaking credentials when GitHub redirects to a different host
    (e.g., storage.googleapis.com for log downloads).
    """
    
    def __init__(self, original_host: str, auth_header: Optional[str] = None):
        super().__init__()
        self.original_host = original_host
        self.auth_header = auth_header
    
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Strip Authorization header if redirecting to a different host."""
        # Call parent's redirect_request to get the new request
        m = super().redirect_request(req, fp, code, msg, headers, newurl)
        if m:
            # Check if host changed
            from urllib.parse import urlparse
            original_parsed = urlparse(req.full_url)
            new_parsed = urlparse(newurl)
            
            if original_parsed.netloc != new_parsed.netloc:
                # Cross-host redirect - remove Authorization header
                if 'Authorization' in m.headers:
                    del m.headers['Authorization']
        return m


class CountingRedirectHandler(HTTPRedirectHandler):
    """
    Redirect handler that counts redirects and strips auth on cross-host redirects.
    
    Also validates redirect schemes and detects redirect loops.
    """
    
    def __init__(self, original_host: str, auth_header: Optional[str] = None, max_redirects: int = 10):
        super().__init__()
        self.original_host = original_host
        self.auth_header = auth_header
        self.max_redirects = max_redirects
        self.redirect_count = 0
        self.seen_urls = set()
    
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Count redirects, detect loops, validate schemes, and strip auth on cross-host."""
        from urllib.parse import urlparse
        
        # Check for redirect loop
        if newurl in self.seen_urls:
            raise GitHubAPIError(f"Redirect loop detected: {newurl}")
        
        self.seen_urls.add(newurl)
        
        # Validate scheme
        new_parsed = urlparse(newurl)
        if new_parsed.scheme not in ('http', 'https'):
            raise GitHubAPIError(f"Invalid redirect scheme: {new_parsed.scheme}")
        
        # Increment counter
        self.redirect_count += 1
        
        if self.redirect_count > self.max_redirects:
            raise GitHubAPIError(f"Too many redirects (>{self.max_redirects})")
        
        # Call parent to create new request
        m = self.http_error_302(req, fp, code, msg, headers, newurl)
        
        if m:
            # Check if host changed
            original_parsed = urlparse(req.full_url)
            
            if original_parsed.netloc != new_parsed.netloc:
                # Cross-host redirect - remove Authorization header
                if 'Authorization' in m.headers:
                    del m.headers['Authorization']
        
        return m
    
    http_error_301 = http_error_303 = http_error_307 = http_error_308 = redirect_request


class GitHubClient:
    """
    Read-only GitHub REST API client.
    
    Uses only GET requests. Token is never logged or exposed in error messages.
    Respects rate limits and request budgets.
    """
    
    API_BASE = "https://api.github.com"
    
    def __init__(self, token: Optional[str] = None, max_requests: int = 50):
        """
        Initialize GitHub client.
        
        Args:
            token: GitHub personal access token. If not provided, reads from 
                   GITHUB_TOKEN environment variable.
            max_requests: Maximum number of API requests to make (default: 50)
        """
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.max_requests = max_requests
        self.request_count = 0
        
    def _redact_token_from_message(self, message: str) -> str:
        """Redact any tokens from error messages."""
        if not self.token:
            return message
        return message.replace(self.token, "[REDACTED-TOKEN]")
    
    def _make_request(self, url: str, follow_redirects: bool = False, max_redirect_hops: int = 10) -> bytes:
        """
        Make a GET request to GitHub API.
        
        Args:
            url: Full URL to request
            follow_redirects: Whether to follow redirects (for log downloads)
            max_redirect_hops: Maximum redirect hops to count in budget
            
        Returns:
            Response body as bytes
            
        Raises:
            RateLimitError: When rate limit is exceeded
            NotFoundError: When resource is not found
            PermissionError: When access is denied (not rate limit)
            GitHubAPIError: For other API errors including redirect loops
        """
        if self.request_count >= self.max_requests:
            raise GitHubAPIError(f"Request budget exceeded (max: {self.max_requests})")
        
        self.request_count += 1
        
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        request = Request(url, headers=headers)
        
        try:
            if follow_redirects:
                # Use custom opener with safe redirect handler
                from urllib.parse import urlparse
                original_host = urlparse(url).netloc
                redirect_handler = CountingRedirectHandler(
                    original_host, 
                    self.token, 
                    max_redirects=max_redirect_hops
                )
                opener = build_opener(redirect_handler)
                with opener.open(request) as response:
                    # Count redirects against budget
                    redirect_count = redirect_handler.redirect_count
                    if redirect_count > 0:
                        # Add redirect hops to request count
                        self.request_count += redirect_count
                        if self.request_count > self.max_requests:
                            raise GitHubAPIError(
                                f"Request budget exceeded after {redirect_count} redirects (max: {self.max_requests})"
                            )
                    return response.read()
            else:
                with urlopen(request) as response:
                    return response.read()
                
        except HTTPError as e:
            # Redact token from error message
            error_body = e.read().decode("utf-8", errors="replace")
            error_msg = self._redact_token_from_message(f"HTTP {e.code}: {error_body}")
            
            if e.code == 401:
                # Authentication failed
                raise PermissionError(error_msg)
            elif e.code == 404:
                raise NotFoundError(error_msg)
            elif e.code in (403, 429):
                # Check if it's actually a rate limit error
                headers_dict = dict(e.headers)
                
                # Check for rate limit indicators
                is_rate_limit = False
                
                # Check X-RateLimit-Remaining header
                if 'X-RateLimit-Remaining' in headers_dict:
                    try:
                        remaining = int(headers_dict['X-RateLimit-Remaining'])
                        if remaining == 0:
                            is_rate_limit = True
                    except (ValueError, TypeError):
                        pass
                
                # Check for Retry-After header
                if 'Retry-After' in headers_dict:
                    is_rate_limit = True
                
                # Check error message for rate limit keywords
                error_lower = error_body.lower()
                rate_limit_keywords = ['rate limit', 'rate-limit', 'ratelimit', 'too many requests']
                if any(keyword in error_lower for keyword in rate_limit_keywords):
                    is_rate_limit = True
                
                if is_rate_limit:
                    reset_at = headers_dict.get("X-RateLimit-Reset")
                    reset_int = int(reset_at) if reset_at else None
                    raise RateLimitError(error_msg, reset_at=reset_int)
                else:
                    # Not a rate limit, it's a permission error
                    # Extract GitHub's response message for better diagnostics
                    response_message = None
                    try:
                        import json
                        error_json = json.loads(error_body)
                        response_message = error_json.get("message")
                    except (json.JSONDecodeError, ValueError):
                        # If not JSON, use the raw error body (already redacted)
                        response_message = error_body
                    
                    # Get X-Accepted-GitHub-Permissions header if present
                    accepted_permissions = headers_dict.get('X-Accepted-GitHub-Permissions')
                    
                    # Build a more informative error message
                    detailed_msg = error_msg
                    if e.code == 401:
                        detailed_msg = f"Authentication failed (401): {response_message or 'Missing or invalid token'}"
                    elif e.code == 403:
                        if accepted_permissions:
                            detailed_msg = f"Insufficient permissions (403): Token lacks required scope. Required: {accepted_permissions}. Response: {response_message or 'Access denied'}"
                        else:
                            detailed_msg = f"Insufficient permissions (403): {response_message or 'Access denied'}"
                    
                    raise GitHubPermissionError(
                        detailed_msg,
                        status_code=e.code,
                        response_message=response_message,
                        accepted_permissions=accepted_permissions
                    )
            else:
                raise GitHubAPIError(error_msg)
                
        except URLError as e:
            error_msg = self._redact_token_from_message(str(e.reason))
            # Check for specific redirect errors
            reason_str = str(e.reason).lower()
            if 'redirect' in reason_str:
                raise GitHubAPIError(f"Redirect error: {error_msg}")
            raise GitHubAPIError(f"Network error: {error_msg}")
            
        except Exception as e:
            error_msg = self._redact_token_from_message(str(e))
            # Check for redirect-related errors
            if 'redirect' in str(e).lower():
                raise GitHubAPIError(f"Redirect error: {error_msg}")
            raise GitHubAPIError(f"Request failed: {error_msg}")
    
    def _get_json(self, path: str) -> Dict[str, Any]:
        """
        Make a GET request and parse JSON response.
        
        Args:
            path: API path (e.g., "/repos/owner/repo/actions/runs/123")
            
        Returns:
            Parsed JSON response
        """
        url = urljoin(self.API_BASE, path)
        data = self._make_request(url)
        import json
        return json.loads(data.decode("utf-8"))
    
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
        path = f"/repos/{owner}/{repo}/actions/runs/{run_id}"
        return self._get_json(path)
    
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
        path = f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        response = self._get_json(path)
        return response.get("jobs", [])
    
    def get_job_logs(self, owner: str, repo: str, job_id: int) -> str:
        """
        Download logs for a job.
        
        GitHub returns logs as a redirect to a zip file or plain text.
        
        Args:
            owner: Repository owner
            repo: Repository name
            job_id: Job ID
            
        Returns:
            Log content as string
            
        Raises:
            RateLimitError: When rate limit is exceeded
            PermissionError: When access is denied
            NotFoundError: When job is not found
            GitHubAPIError: For other API errors
        """
        path = f"/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
        url = urljoin(self.API_BASE, path)
        
        # GitHub redirects to log storage; follow with safe redirect handler
        data = self._make_request(url, follow_redirects=True)
        
        # Try to extract from zip first
        try:
            with zipfile.ZipFile(BytesIO(data)) as zf:
                # Usually a single file in the zip
                names = zf.namelist()
                if names:
                    with zf.open(names[0]) as f:
                        return f.read().decode("utf-8", errors="replace")
        except zipfile.BadZipFile:
            # Not a zip, treat as plain text
            pass
        
        # Return as plain text
        return data.decode("utf-8", errors="replace")
    
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
            
        Raises:
            NotAFileError: When path points to a directory
            GitHubAPIError: For other API errors
        """
        # URL-encode the path and ref
        encoded_path = quote(path, safe='/')
        encoded_ref = quote(ref, safe='')
        api_path = f"/repos/{owner}/{repo}/contents/{encoded_path}?ref={encoded_ref}"
        response = self._get_json(api_path)
        
        # Check if it's a directory
        if isinstance(response, list):
            raise NotAFileError(f"Path is a directory, not a file: {path}")
        
        # GitHub returns base64-encoded content for small files
        content_b64 = response.get("content", "")
        
        # Check if content is empty (files over 1 MB)
        if not content_b64:
            # Try to get the file via git blob API
            sha = response.get("sha")
            if sha:
                try:
                    blob_path = f"/repos/{owner}/{repo}/git/blobs/{sha}"
                    blob_response = self._get_json(blob_path)
                    blob_content = blob_response.get("content", "")
                    if blob_content:
                        content_b64 = blob_content
                    else:
                        raise GitHubAPIError(f"File too large and blob API returned no content: {path}")
                except Exception as e:
                    raise GitHubAPIError(f"File over 1 MB and failed to fetch via blob API: {path}")
            else:
                raise GitHubAPIError(f"No content returned for {path} (file may be too large)")
        
        # Remove whitespace that GitHub adds
        content_b64 = content_b64.replace("\n", "").replace(" ", "")
        
        try:
            content_bytes = base64.b64decode(content_b64)
            return content_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            error_msg = self._redact_token_from_message(str(e))
            raise GitHubAPIError(f"Failed to decode file content: {error_msg}")
    
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
        # Same as get_file_content
        return self.get_file_content(owner, repo, workflow_path, ref)


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
