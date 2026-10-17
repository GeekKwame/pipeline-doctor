"""Tests for real GitHub client with mocked HTTP."""

import base64
import json
import zipfile
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest

from pipeline_doctor.github_client import (
    GitHubAPIError,
    GitHubClient,
    NotFoundError,
    RateLimitError,
)


@pytest.fixture
def mock_urlopen():
    """Fixture for mocking urlopen."""
    with patch("pipeline_doctor.github_client.urlopen") as mock:
        yield mock


def make_http_error(code: int, msg: str = "", headers: dict = None):
    """Helper to create HTTPError."""
    error = HTTPError(
        url="https://api.github.com/test",
        code=code,
        msg=msg,
        hdrs=headers or {},
        fp=None,
    )
    error.read = MagicMock(return_value=msg.encode())
    return error


def test_init_with_token():
    """Test initialization with explicit token."""
    client = GitHubClient(token="ghp_test123")
    assert client.token == "ghp_test123"
    assert client.max_requests == 50


def test_init_from_env():
    """Test initialization from environment variable."""
    with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_fromenv"}):
        client = GitHubClient()
        assert client.token == "ghp_fromenv"


def test_init_no_token():
    """Test initialization without token."""
    with patch.dict("os.environ", {}, clear=True):
        client = GitHubClient()
        assert client.token == ""


def test_get_workflow_run_success(mock_urlopen):
    """Test successful workflow run fetch."""
    run_data = {
        "id": 12345,
        "name": "CI",
        "head_sha": "a" * 40,
        "status": "completed",
        "conclusion": "failure",
    }
    
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(run_data).encode()
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    mock_urlopen.return_value = mock_response
    
    client = GitHubClient(token="ghp_test")
    result = client.get_workflow_run("owner", "repo", 12345)
    
    assert result == run_data
    assert client.request_count == 1


def test_list_jobs_success(mock_urlopen):
    """Test successful jobs listing."""
    jobs_data = {
        "jobs": [
            {"id": 1, "name": "test", "conclusion": "failure"},
            {"id": 2, "name": "build", "conclusion": "success"},
        ]
    }
    
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(jobs_data).encode()
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    mock_urlopen.return_value = mock_response
    
    client = GitHubClient(token="ghp_test")
    result = client.list_jobs("owner", "repo", 12345)
    
    assert len(result) == 2
    assert result[0]["name"] == "test"


def test_get_file_content_success(mock_urlopen):
    """Test successful file content fetch."""
    file_content = "print('hello world')\n"
    content_b64 = base64.b64encode(file_content.encode()).decode()
    
    file_data = {
        "name": "main.py",
        "path": "src/main.py",
        "content": content_b64,
        "encoding": "base64",
    }
    
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(file_data).encode()
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    mock_urlopen.return_value = mock_response
    
    client = GitHubClient(token="ghp_test")
    result = client.get_file_content("owner", "repo", "src/main.py", "a" * 40)
    
    assert result == file_content


def test_get_file_content_with_newlines_in_base64(mock_urlopen):
    """Test file content when GitHub adds newlines to base64."""
    file_content = "x" * 100
    content_b64 = base64.b64encode(file_content.encode()).decode()
    # Add newlines like GitHub does
    content_b64_with_newlines = "\n".join([content_b64[i:i+60] for i in range(0, len(content_b64), 60)])
    
    file_data = {
        "content": content_b64_with_newlines,
    }
    
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(file_data).encode()
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    mock_urlopen.return_value = mock_response
    
    client = GitHubClient(token="ghp_test")
    result = client.get_file_content("owner", "repo", "file.txt", "a" * 40)
    
    assert result == file_content


def test_get_workflow_file_success(mock_urlopen):
    """Test successful workflow file fetch."""
    workflow_yaml = "name: CI\non: push\n"
    content_b64 = base64.b64encode(workflow_yaml.encode()).decode()
    
    file_data = {"content": content_b64}
    
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(file_data).encode()
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    mock_urlopen.return_value = mock_response
    
    client = GitHubClient(token="ghp_test")
    result = client.get_workflow_file("owner", "repo", ".github/workflows/ci.yml", "a" * 40)
    
    assert result == workflow_yaml


def test_get_job_logs_zip(mock_urlopen):
    """Test job logs download (zip format)."""
    log_content = "Log line 1\nLog line 2\nERROR: test failed\n"
    
    # Create a zip file in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("job.log", log_content)
    zip_data = zip_buffer.getvalue()
    
    mock_response = MagicMock()
    mock_response.read.return_value = zip_data
    mock_response.geturl.return_value = "https://different-url.com/logs.zip"
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    mock_urlopen.return_value = mock_response
    
    client = GitHubClient(token="ghp_test")
    result = client.get_job_logs("owner", "repo", 1001)
    
    assert result == log_content


def test_get_job_logs_plain_text(mock_urlopen):
    """Test job logs download (plain text)."""
    log_content = "Plain text log\nNo zip compression\n"
    
    mock_response = MagicMock()
    mock_response.read.return_value = log_content.encode()
    mock_response.geturl.return_value = "https://different-url.com/logs.txt"
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    mock_urlopen.return_value = mock_response
    
    client = GitHubClient(token="ghp_test")
    result = client.get_job_logs("owner", "repo", 1001)
    
    assert result == log_content


def test_404_error(mock_urlopen):
    """Test handling of 404 errors."""
    mock_urlopen.side_effect = make_http_error(404, "Not Found")
    
    client = GitHubClient(token="ghp_test")
    
    with pytest.raises(NotFoundError) as exc_info:
        client.get_workflow_run("owner", "repo", 99999)
    
    assert "404" in str(exc_info.value)


def test_rate_limit_403(mock_urlopen):
    """Test handling of rate limit (403)."""
    headers = {"X-RateLimit-Reset": "1704067200"}
    mock_urlopen.side_effect = make_http_error(403, "Rate limit exceeded", headers)
    
    client = GitHubClient(token="ghp_test")
    
    with pytest.raises(RateLimitError) as exc_info:
        client.get_workflow_run("owner", "repo", 12345)
    
    assert exc_info.value.reset_at == 1704067200


def test_rate_limit_429(mock_urlopen):
    """Test handling of rate limit (429)."""
    headers = {"X-RateLimit-Reset": "1704067200"}
    mock_urlopen.side_effect = make_http_error(429, "Too many requests", headers)
    
    client = GitHubClient(token="ghp_test")
    
    with pytest.raises(RateLimitError) as exc_info:
        client.get_workflow_run("owner", "repo", 12345)
    
    assert exc_info.value.reset_at == 1704067200


def test_token_redaction_in_errors(mock_urlopen):
    """Test that tokens are redacted from error messages."""
    secret_token = "ghp_secrettoken123456"
    error_msg = f"Authentication failed for token {secret_token}"
    mock_urlopen.side_effect = make_http_error(401, error_msg)
    
    client = GitHubClient(token=secret_token)
    
    with pytest.raises(GitHubAPIError) as exc_info:
        client.get_workflow_run("owner", "repo", 12345)
    
    error_str = str(exc_info.value)
    assert secret_token not in error_str
    assert "[REDACTED-TOKEN]" in error_str


def test_request_budget_limit(mock_urlopen):
    """Test request budget enforcement."""
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"id": 1}'
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    mock_urlopen.return_value = mock_response
    
    client = GitHubClient(token="ghp_test", max_requests=3)
    
    # First 3 requests should succeed
    for i in range(3):
        client.get_workflow_run("owner", "repo", i)
    
    assert client.request_count == 3
    
    # 4th request should fail
    with pytest.raises(GitHubAPIError) as exc_info:
        client.get_workflow_run("owner", "repo", 4)
    
    assert "budget exceeded" in str(exc_info.value).lower()


def test_network_error(mock_urlopen):
    """Test handling of network errors."""
    from urllib.error import URLError
    mock_urlopen.side_effect = URLError("Connection refused")
    
    client = GitHubClient(token="ghp_test")
    
    with pytest.raises(GitHubAPIError) as exc_info:
        client.get_workflow_run("owner", "repo", 12345)
    
    assert "network error" in str(exc_info.value).lower()


def test_no_write_methods():
    """Test that client has no write methods (only GET)."""
    client = GitHubClient(token="ghp_test")
    
    # Verify no POST, PUT, PATCH, DELETE methods exist
    disallowed_methods = ["post", "put", "patch", "delete", "create", "update"]
    
    for method_name in dir(client):
        if method_name.startswith("_"):
            continue
        lower_name = method_name.lower()
        for disallowed in disallowed_methods:
            assert disallowed not in lower_name, f"Client should not have write method: {method_name}"


def test_authorization_header_format(mock_urlopen):
    """Test that authorization header uses Bearer format."""
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"id": 1}'
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    mock_urlopen.return_value = mock_response
    
    client = GitHubClient(token="ghp_test123")
    client.get_workflow_run("owner", "repo", 12345)
    
    # Check the request that was made
    call_args = mock_urlopen.call_args[0][0]
    headers = call_args.headers
    
    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer ghp_test123"


def test_no_token_in_request_when_empty(mock_urlopen):
    """Test that no Authorization header is sent when token is empty."""
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"id": 1}'
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    mock_urlopen.return_value = mock_response
    
    with patch.dict("os.environ", {}, clear=True):
        client = GitHubClient()
        client.get_workflow_run("owner", "repo", 12345)
    
    # Check the request that was made
    call_args = mock_urlopen.call_args[0][0]
    headers = call_args.headers
    
    assert "Authorization" not in headers


def test_pinning_to_commit_sha():
    """Test that file fetches use ref parameter for SHA pinning."""
    # This is a documentation test - the actual SHA pinning is done
    # by passing the ref parameter to get_file_content and get_workflow_file
    client = GitHubClient(token="ghp_test")
    
    # These methods require ref parameter
    import inspect
    
    file_sig = inspect.signature(client.get_file_content)
    assert "ref" in file_sig.parameters
    
    workflow_sig = inspect.signature(client.get_workflow_file)
    assert "ref" in workflow_sig.parameters
