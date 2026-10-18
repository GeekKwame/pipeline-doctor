"""Tests for redirect handling improvements in GitHub client."""

import pytest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from pipeline_doctor.github_client import (
    GitHubClient,
    GitHubAPIError,
    CountingRedirectHandler,
    PermissionError,
)


def test_401_authentication_error():
    """Test that 401 errors are caught as PermissionError."""
    with patch("pipeline_doctor.github_client.urlopen") as mock_urlopen:
        error = HTTPError(
            url="https://api.github.com/test",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )
        error.read = MagicMock(return_value=b"Bad credentials")
        mock_urlopen.side_effect = error
        
        client = GitHubClient(token="ghp_test")
        
        with pytest.raises(PermissionError) as exc_info:
            client.get_workflow_run("owner", "repo", 12345)
        
        assert "401" in str(exc_info.value)


def test_redirect_count_increments_request_budget():
    """Test that redirects are counted in request budget."""
    with patch("pipeline_doctor.github_client.build_opener") as mock_build_opener:
        # Create a handler that reports 2 redirects
        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"log content"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_opener.open.return_value = mock_response
        
        mock_build_opener.return_value = mock_opener
        
        # Patch the handler to report redirects
        with patch("pipeline_doctor.github_client.CountingRedirectHandler") as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler.redirect_count = 2
            mock_handler_class.return_value = mock_handler
            
            client = GitHubClient(token="ghp_test")
            initial_count = client.request_count
            
            client.get_job_logs("owner", "repo", 1001)
            
            # Should count initial request + 2 redirects = 3 total
            assert client.request_count == initial_count + 3


def test_redirect_loop_detection():
    """Test that redirect loops are detected and rejected."""
    handler = CountingRedirectHandler("api.github.com", max_redirects=10)
    
    # First redirect should succeed
    req = MagicMock()
    req.full_url = "https://api.github.com/original"
    fp = MagicMock()
    
    with patch.object(handler.__class__.__bases__[0], 'http_error_302') as mock_parent:
        mock_parent.return_value = MagicMock()
        
        # First redirect to url1
        handler.redirect_request(req, fp, 302, "Found", {}, "https://storage.example.com/file")
        
        # Try to redirect to the same URL again - should raise
        with pytest.raises(GitHubAPIError) as exc_info:
            handler.redirect_request(req, fp, 302, "Found", {}, "https://storage.example.com/file")
        
        assert "loop" in str(exc_info.value).lower()


def test_redirect_invalid_scheme():
    """Test that redirects to invalid schemes are rejected."""
    handler = CountingRedirectHandler("api.github.com", max_redirects=10)
    
    req = MagicMock()
    req.full_url = "https://api.github.com/original"
    fp = MagicMock()
    
    with pytest.raises(GitHubAPIError) as exc_info:
        handler.redirect_request(req, fp, 302, "Found", {}, "ftp://evil.com/malware")
    
    assert "invalid" in str(exc_info.value).lower()
    assert "scheme" in str(exc_info.value).lower()


def test_redirect_max_hops_exceeded():
    """Test that too many redirects are rejected."""
    handler = CountingRedirectHandler("api.github.com", max_redirects=2)
    
    req = MagicMock()
    req.full_url = "https://api.github.com/original"
    fp = MagicMock()
    
    with patch.object(handler.__class__.__bases__[0], 'http_error_302') as mock_parent:
        mock_parent.return_value = MagicMock()
        
        # First two redirects should work
        handler.redirect_request(req, fp, 302, "Found", {}, "https://storage1.example.com/file")
        handler.redirect_request(req, fp, 302, "Found", {}, "https://storage2.example.com/file")
        
        # Third redirect should fail
        with pytest.raises(GitHubAPIError) as exc_info:
            handler.redirect_request(req, fp, 302, "Found", {}, "https://storage3.example.com/file")
        
        assert "too many redirects" in str(exc_info.value).lower()


def test_redirect_strips_auth_on_cross_host():
    """Test that CountingRedirectHandler strips auth on cross-host redirect."""
    handler = CountingRedirectHandler("api.github.com", "ghp_secret", max_redirects=10)
    
    req = MagicMock()
    req.full_url = "https://api.github.com/original"
    req.headers = {}
    fp = MagicMock()
    
    with patch.object(handler.__class__.__bases__[0], 'http_error_302') as mock_parent:
        new_req = MagicMock()
        new_req.headers = {"Authorization": "Bearer ghp_secret"}
        mock_parent.return_value = new_req
        
        result = handler.redirect_request(
            req, 
            fp, 
            302, 
            "Found", 
            {}, 
            "https://storage.googleapis.com/logs/file.zip"
        )
        
        # Should have removed Authorization header
        assert "Authorization" not in result.headers


def test_redirect_keeps_auth_on_same_host():
    """Test that CountingRedirectHandler keeps auth on same-host redirect."""
    handler = CountingRedirectHandler("api.github.com", "ghp_secret", max_redirects=10)
    
    req = MagicMock()
    req.full_url = "https://api.github.com/path1"
    req.headers = {}
    fp = MagicMock()
    
    with patch.object(handler.__class__.__bases__[0], 'http_error_302') as mock_parent:
        new_req = MagicMock()
        new_req.headers = {"Authorization": "Bearer ghp_secret"}
        mock_parent.return_value = new_req
        
        result = handler.redirect_request(
            req, 
            fp, 
            302, 
            "Found", 
            {}, 
            "https://api.github.com/path2"
        )
        
        # Should keep Authorization header for same host
        assert "Authorization" in result.headers


def test_redirect_error_descriptive_message():
    """Test that redirect-related errors have descriptive messages."""
    with patch("pipeline_doctor.github_client.urlopen") as mock_urlopen:
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("too many redirects")
        
        client = GitHubClient(token="ghp_test")
        
        with pytest.raises(GitHubAPIError) as exc_info:
            client.get_workflow_run("owner", "repo", 12345)
        
        assert "redirect" in str(exc_info.value).lower()


def test_request_budget_exceeded_with_redirects():
    """Test that request budget is enforced including redirects."""
    with patch("pipeline_doctor.github_client.build_opener") as mock_build_opener:
        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"content"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_opener.open.return_value = mock_response
        
        mock_build_opener.return_value = mock_opener
        
        with patch("pipeline_doctor.github_client.CountingRedirectHandler") as mock_handler_class:
            # Simulate 10 redirects
            mock_handler = MagicMock()
            mock_handler.redirect_count = 10
            mock_handler_class.return_value = mock_handler
            
            # Set budget to 5 (will be exceeded with 1 initial + 10 redirects)
            client = GitHubClient(token="ghp_test", max_requests=5)
            
            with pytest.raises(GitHubAPIError) as exc_info:
                client.get_job_logs("owner", "repo", 1001)
            
            assert "budget exceeded" in str(exc_info.value).lower()
            assert "redirect" in str(exc_info.value).lower()
