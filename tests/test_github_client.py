"""Tests for real GitHub client with mocked HTTP."""

import base64
import json
import zipfile
from io import BytesIO
from unittest.mock import MagicMock, patch, call
from urllib.error import HTTPError

import pytest

from pipeline_doctor.github_client import (
    GitHubAPIError,
    GitHubClient,
    NotFoundError,
    RateLimitError,
    PermissionError,
    NotAFileError,
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
    
    # Mock build_opener instead of urlopen since get_job_logs uses redirects
    with patch("pipeline_doctor.github_client.build_opener") as mock_build_opener:
        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = zip_data
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_opener.open.return_value = mock_response
        mock_build_opener.return_value = mock_opener
        
        client = GitHubClient(token="ghp_test")
        result = client.get_job_logs("owner", "repo", 1001)
        
        assert result == log_content


def test_get_job_logs_plain_text(mock_urlopen):
    """Test job logs download (plain text)."""
    log_content = "Plain text log\nNo zip compression\n"
    
    # Mock build_opener instead of urlopen since get_job_logs uses redirects
    with patch("pipeline_doctor.github_client.build_opener") as mock_build_opener:
        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = log_content.encode()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_opener.open.return_value = mock_response
        mock_build_opener.return_value = mock_opener
        
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


# ============================================================================
# REGRESSION TESTS FOR BUG FIXES
# ============================================================================


def test_bug1_authorization_header_not_leaked_on_redirect():
    """
    BUG 1 REGRESSION TEST: Authorization header should NOT be forwarded 
    to a different host when redirects occur.
    
    This test verifies that when GitHub redirects to a different host
    (e.g., storage.googleapis.com), the Authorization header is stripped.
    """
    with patch("pipeline_doctor.github_client.build_opener") as mock_build_opener:
        # Mock the opener and response
        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"log content"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_opener.open.return_value = mock_response
        mock_build_opener.return_value = mock_opener
        
        client = GitHubClient(token="ghp_secret_token_123")
        client.get_job_logs("owner", "repo", 1001)
        
        # Verify build_opener was called (indicating custom redirect handler)
        mock_build_opener.assert_called_once()
        
        # Verify the redirect handler is CountingRedirectHandler (which includes auth stripping)
        handler = mock_build_opener.call_args[0][0]
        from pipeline_doctor.github_client import CountingRedirectHandler
        assert isinstance(handler, CountingRedirectHandler)


def test_bug1_safe_redirect_handler_strips_auth_on_cross_host():
    """
    BUG 1 REGRESSION TEST: Verify SafeRedirectHandler strips Authorization
    header when redirecting to a different host.
    """
    from pipeline_doctor.github_client import SafeRedirectHandler
    from urllib.request import Request
    
    # Create a handler for api.github.com
    handler = SafeRedirectHandler("api.github.com", "ghp_secret")
    
    # Create a request with Authorization header
    req = Request("https://api.github.com/original")
    req.add_header("Authorization", "Bearer ghp_secret")
    
    # Simulate redirect to different host
    fp = MagicMock()
    new_url = "https://storage.googleapis.com/logs/file.zip"
    
    # Mock the parent class method to return a new request
    new_req = Request(new_url)
    new_req.add_header("Authorization", "Bearer ghp_secret")
    
    with patch.object(handler.__class__.__bases__[0], 'http_error_302', return_value=new_req):
        result = handler.redirect_request(req, fp, 302, "Found", {}, new_url)
        
        # Verify Authorization header was removed
        assert result is not None
        assert 'Authorization' not in result.headers


def test_bug2_redirect_not_fetched_twice():
    """
    BUG 2 REGRESSION TEST: Redirect target should only be fetched once,
    and the request counter should count it.
    
    Previously, the code would follow the redirect with urlopen AND then
    make a second request, fetching the redirect target twice.
    """
    with patch("pipeline_doctor.github_client.build_opener") as mock_build_opener:
        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"log content"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_opener.open.return_value = mock_response
        mock_build_opener.return_value = mock_opener
        
        client = GitHubClient(token="ghp_test")
        client.get_job_logs("owner", "repo", 1001)
        
        # Verify opener.open was called exactly once (not twice)
        assert mock_opener.open.call_count == 1
        
        # Verify request count is 1 (not 0 or 2)
        assert client.request_count == 1


def test_bug3_403_without_rate_limit_indicators_raises_permission_error():
    """
    BUG 3 REGRESSION TEST: 403 without rate limit indicators should raise
    PermissionError, not RateLimitError.
    """
    with patch("pipeline_doctor.github_client.urlopen") as mock_urlopen:
        # 403 without rate limit indicators
        headers = {}  # No X-RateLimit-Remaining, no Retry-After
        error = make_http_error(403, "Forbidden - access denied", headers)
        mock_urlopen.side_effect = error
        
        client = GitHubClient(token="ghp_test")
        
        with pytest.raises(PermissionError) as exc_info:
            client.get_workflow_run("owner", "repo", 12345)
        
        assert "403" in str(exc_info.value)


def test_bug3_403_with_rate_limit_remaining_zero_raises_rate_limit_error():
    """
    BUG 3 REGRESSION TEST: 403 with X-RateLimit-Remaining: 0 should raise
    RateLimitError.
    """
    with patch("pipeline_doctor.github_client.urlopen") as mock_urlopen:
        headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1234567890"}
        error = make_http_error(403, "Rate limit exceeded", headers)
        mock_urlopen.side_effect = error
        
        client = GitHubClient(token="ghp_test")
        
        with pytest.raises(RateLimitError) as exc_info:
            client.get_workflow_run("owner", "repo", 12345)
        
        assert exc_info.value.reset_at == 1234567890


def test_bug3_403_with_retry_after_raises_rate_limit_error():
    """
    BUG 3 REGRESSION TEST: 403 with Retry-After header should raise
    RateLimitError.
    """
    with patch("pipeline_doctor.github_client.urlopen") as mock_urlopen:
        headers = {"Retry-After": "60"}
        error = make_http_error(403, "Too many requests", headers)
        mock_urlopen.side_effect = error
        
        client = GitHubClient(token="ghp_test")
        
        with pytest.raises(RateLimitError):
            client.get_workflow_run("owner", "repo", 12345)


def test_bug3_403_with_rate_limit_message_raises_rate_limit_error():
    """
    BUG 3 REGRESSION TEST: 403 with rate limit message should raise
    RateLimitError.
    """
    with patch("pipeline_doctor.github_client.urlopen") as mock_urlopen:
        headers = {}
        error = make_http_error(403, "API rate limit exceeded for user", headers)
        mock_urlopen.side_effect = error
        
        client = GitHubClient(token="ghp_test")
        
        with pytest.raises(RateLimitError):
            client.get_workflow_run("owner", "repo", 12345)


def test_bug3_429_always_raises_rate_limit_error():
    """
    BUG 3 REGRESSION TEST: 429 should always raise RateLimitError.
    """
    with patch("pipeline_doctor.github_client.urlopen") as mock_urlopen:
        # 429 without any special headers should still be rate limit
        headers = {}
        error = make_http_error(429, "Too many requests", headers)
        mock_urlopen.side_effect = error
        
        client = GitHubClient(token="ghp_test")
        
        with pytest.raises(RateLimitError):
            client.get_workflow_run("owner", "repo", 12345)


def test_bug4_directory_path_raises_not_a_file_error():
    """
    BUG 4 REGRESSION TEST: get_file_content should raise NotAFileError
    when the path is a directory (API returns a list).
    """
    with patch("pipeline_doctor.github_client.urlopen") as mock_urlopen:
        # GitHub returns a list for directories
        directory_response = [
            {"name": "file1.py", "type": "file"},
            {"name": "file2.py", "type": "file"},
        ]
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(directory_response).encode()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_urlopen.return_value = mock_response
        
        client = GitHubClient(token="ghp_test")
        
        with pytest.raises(NotAFileError) as exc_info:
            client.get_file_content("owner", "repo", "src", "a" * 40)
        
        assert "directory" in str(exc_info.value).lower()


def test_bug6_file_path_is_url_encoded():
    """
    BUG 6 REGRESSION TEST: File paths should be URL-encoded in contents requests.
    """
    with patch("pipeline_doctor.github_client.urlopen") as mock_urlopen:
        file_content = "test content"
        content_b64 = base64.b64encode(file_content.encode()).decode()
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"content": content_b64}).encode()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_urlopen.return_value = mock_response
        
        client = GitHubClient(token="ghp_test")
        client.get_file_content("owner", "repo", "path with spaces/file.py", "a" * 40)
        
        # Check that the request URL has encoded path
        call_args = mock_urlopen.call_args[0][0]
        request_url = call_args.full_url
        
        # Should have %20 for spaces, not literal spaces
        assert "path%20with%20spaces" in request_url
        assert "path with spaces" not in request_url


def test_ref_parameter_is_url_encoded():
    """Test that ref parameter is URL-encoded in contents requests."""
    with patch("pipeline_doctor.github_client.urlopen") as mock_urlopen:
        file_content = "test content"
        content_b64 = base64.b64encode(file_content.encode()).decode()
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"content": content_b64}).encode()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_urlopen.return_value = mock_response
        
        client = GitHubClient(token="ghp_test")
        # Use a ref with special characters that need encoding
        ref_with_special_chars = "feature/test-branch#123"
        client.get_file_content("owner", "repo", "README.md", ref_with_special_chars)
        
        # Check that the request URL has encoded ref
        call_args = mock_urlopen.call_args[0][0]
        request_url = call_args.full_url
        
        # Should have encoded # character (%23), not literal #
        assert "ref=feature%2Ftest-branch%23123" in request_url
        assert "ref=feature/test-branch#123" not in request_url


def test_bug7_large_file_fallback_to_blob_api():
    """
    BUG 7 REGRESSION TEST: Files over 1 MB return empty content from contents API.
    Should fall back to git blob API.
    """
    with patch("pipeline_doctor.github_client.urlopen") as mock_urlopen:
        # First response: contents API with no content (large file)
        contents_response = {
            "name": "large_file.bin",
            "sha": "abc123def456",
            "content": "",  # Empty for large files
        }
        
        # Second response: blob API with content
        blob_content = "x" * 2000000  # 2 MB of data
        blob_b64 = base64.b64encode(blob_content.encode()).decode()
        blob_response = {
            "content": blob_b64,
            "encoding": "base64",
        }
        
        mock_response1 = MagicMock()
        mock_response1.read.return_value = json.dumps(contents_response).encode()
        mock_response1.__enter__.return_value = mock_response1
        mock_response1.__exit__.return_value = False
        
        mock_response2 = MagicMock()
        mock_response2.read.return_value = json.dumps(blob_response).encode()
        mock_response2.__enter__.return_value = mock_response2
        mock_response2.__exit__.return_value = False
        
        # Return different responses for different calls
        mock_urlopen.side_effect = [mock_response1, mock_response2]
        
        client = GitHubClient(token="ghp_test")
        result = client.get_file_content("owner", "repo", "large_file.bin", "a" * 40)
        
        # Verify it made 2 requests (contents API + blob API)
        assert mock_urlopen.call_count == 2
        assert client.request_count == 2
        
        # Verify blob API was called
        second_call_url = mock_urlopen.call_args_list[1][0][0].full_url
        assert "/git/blobs/" in second_call_url
        assert "abc123def456" in second_call_url
        
        # Verify content was returned
        assert result == blob_content


def test_bug7_large_file_no_sha_raises_error():
    """
    BUG 7 REGRESSION TEST: If large file has no content and no sha,
    should raise a clear error.
    """
    with patch("pipeline_doctor.github_client.urlopen") as mock_urlopen:
        contents_response = {
            "name": "large_file.bin",
            "content": "",  # Empty
            # No sha field
        }
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(contents_response).encode()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_urlopen.return_value = mock_response
        
        client = GitHubClient(token="ghp_test")
        
        with pytest.raises(GitHubAPIError) as exc_info:
            client.get_file_content("owner", "repo", "large_file.bin", "a" * 40)
        
        assert "too large" in str(exc_info.value).lower()


def test_bug9_job_logs_plain_text_handled():
    """
    BUG 9 REGRESSION TEST: Job logs endpoint may return plain text (not zip).
    Both should be handled.
    """
    with patch("pipeline_doctor.github_client.build_opener") as mock_build_opener:
        log_content = "Plain text log\nNo zip compression\n"
        
        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = log_content.encode()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_opener.open.return_value = mock_response
        mock_build_opener.return_value = mock_opener
        
        client = GitHubClient(token="ghp_test")
        result = client.get_job_logs("owner", "repo", 1001)
        
        assert result == log_content


def test_bug9_job_logs_zip_handled():
    """
    BUG 9 REGRESSION TEST: Job logs endpoint may return a zip file.
    Both plain text and zip should be handled.
    """
    with patch("pipeline_doctor.github_client.build_opener") as mock_build_opener:
        log_content = "Log from zip file\nExtracted successfully\n"
        
        # Create a zip file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("job.log", log_content)
        zip_data = zip_buffer.getvalue()
        
        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = zip_data
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_opener.open.return_value = mock_response
        mock_build_opener.return_value = mock_opener
        
        client = GitHubClient(token="ghp_test")
        result = client.get_job_logs("owner", "repo", 1001)
        
        assert result == log_content
