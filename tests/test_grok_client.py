"""Tests for Grok client with mocked HTTP."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from pipeline_doctor.grok_client import (
    GrokAPIClient,
    GrokAPIError,
    FakeGrokClient,
)


@pytest.fixture
def mock_post():
    """Fixture for mocking requests.post."""
    with patch("requests.post") as mock:
        yield mock


def make_success_response(content: str = "test response", finish_reason: str = "stop"):
    """Helper to create successful API response."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {"content": content},
                "finish_reason": finish_reason,
            }
        ]
    }
    return mock_response


def make_error_response(status_code: int, body: str = ""):
    """Helper to create error response."""
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = status_code
    mock_response.text = body
    return mock_response


def test_init_with_api_key():
    """Test initialization with explicit API key."""
    client = GrokAPIClient(api_key="xai-test123")
    assert client.api_key == "xai-test123"
    assert client.default_model == "grok-beta"


def test_init_from_env_grok_api_key():
    """Test initialization from GROK_API_KEY environment variable."""
    with patch.dict("os.environ", {"GROK_API_KEY": "xai-fromenv"}):
        client = GrokAPIClient()
        assert client.api_key == "xai-fromenv"


def test_init_from_env_xai_api_key():
    """Test initialization from XAI_API_KEY environment variable."""
    with patch.dict("os.environ", {"XAI_API_KEY": "xai-fromenv2"}):
        client = GrokAPIClient()
        assert client.api_key == "xai-fromenv2"


def test_init_with_custom_model():
    """Test initialization with custom model."""
    client = GrokAPIClient(api_key="xai-test", model="grok-2-latest")
    assert client.default_model == "grok-2-latest"


def test_init_model_from_env():
    """Test initialization with model from GROK_MODEL env var."""
    with patch.dict("os.environ", {"GROK_MODEL": "grok-custom"}):
        client = GrokAPIClient(api_key="xai-test")
        assert client.default_model == "grok-custom"


def test_init_no_api_key_raises():
    """Test that initialization without API key raises ValueError."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError) as exc_info:
            GrokAPIClient()
        assert "API key required" in str(exc_info.value)


def test_chat_completion_success(mock_post):
    """Test successful chat completion."""
    mock_post.return_value = make_success_response("Hello, world!")
    
    client = GrokAPIClient(api_key="xai-test")
    result = client.chat_completion(
        system_prompt="You are a helpful assistant.",
        user_message="Say hello",
    )
    
    assert result == "Hello, world!"
    mock_post.assert_called_once()
    
    # Check request structure
    call_args = mock_post.call_args
    assert call_args.kwargs["json"]["model"] == "grok-beta"
    assert call_args.kwargs["json"]["temperature"] == 0.1
    assert len(call_args.kwargs["json"]["messages"]) == 2


def test_chat_completion_with_custom_model(mock_post):
    """Test chat completion with custom model."""
    mock_post.return_value = make_success_response("response")
    
    client = GrokAPIClient(api_key="xai-test")
    client.chat_completion(
        system_prompt="system",
        user_message="user",
        model="grok-custom",
    )
    
    call_args = mock_post.call_args
    assert call_args.kwargs["json"]["model"] == "grok-custom"


def test_chat_completion_with_max_tokens(mock_post):
    """Test chat completion with max_tokens."""
    mock_post.return_value = make_success_response("response")
    
    client = GrokAPIClient(api_key="xai-test")
    client.chat_completion(
        system_prompt="system",
        user_message="user",
        max_tokens=1000,
    )
    
    call_args = mock_post.call_args
    assert call_args.kwargs["json"]["max_tokens"] == 1000


def test_chat_completion_with_response_format(mock_post):
    """Test chat completion with response_format (JSON mode)."""
    mock_post.return_value = make_success_response('{"key": "value"}')
    
    client = GrokAPIClient(api_key="xai-test")
    client.chat_completion(
        system_prompt="system",
        user_message="user",
        response_format="json_object",
    )
    
    call_args = mock_post.call_args
    assert call_args.kwargs["json"]["response_format"] == {"type": "json_object"}


def test_error_response_with_body(mock_post):
    """Test that error responses include status code and truncated body."""
    mock_post.return_value = make_error_response(
        400, 
        "Bad request: invalid temperature value"
    )
    
    client = GrokAPIClient(api_key="xai-test")
    
    with pytest.raises(GrokAPIError) as exc_info:
        client.chat_completion("system", "user")
    
    error = exc_info.value
    assert error.status_code == 400
    assert "invalid temperature" in str(error)
    assert "400" in str(error)


def test_error_403_credits_exhausted(mock_post):
    """Test handling of 403 when credits are exhausted."""
    mock_post.return_value = make_error_response(
        403,
        "Forbidden: Your account credits have been exhausted"
    )
    
    client = GrokAPIClient(api_key="xai-test")
    
    with pytest.raises(GrokAPIError) as exc_info:
        client.chat_completion("system", "user")
    
    error = exc_info.value
    assert error.status_code == 403
    assert "credits" in str(error).lower()


def test_error_429_retry(mock_post):
    """Test that 429 errors trigger retries."""
    # First two calls return 429, third succeeds
    mock_post.side_effect = [
        make_error_response(429, "Too many requests"),
        make_error_response(429, "Too many requests"),
        make_success_response("success after retry"),
    ]
    
    client = GrokAPIClient(api_key="xai-test", max_retries=2)
    
    # Should succeed after retries
    result = client.chat_completion("system", "user")
    assert result == "success after retry"
    assert mock_post.call_count == 3


def test_error_429_max_retries_exceeded(mock_post):
    """Test that 429 errors raise after max retries."""
    mock_post.return_value = make_error_response(429, "Too many requests")
    
    client = GrokAPIClient(api_key="xai-test", max_retries=1)
    
    with pytest.raises(GrokAPIError) as exc_info:
        client.chat_completion("system", "user")
    
    # Should have tried initial + 1 retry = 2 calls
    assert mock_post.call_count == 2
    assert "429" in str(exc_info.value)


def test_error_5xx_retry(mock_post):
    """Test that 5xx errors trigger retries."""
    mock_post.side_effect = [
        make_error_response(500, "Internal server error"),
        make_success_response("success after retry"),
    ]
    
    client = GrokAPIClient(api_key="xai-test", max_retries=1)
    result = client.chat_completion("system", "user")
    assert result == "success after retry"
    assert mock_post.call_count == 2


def test_api_key_redacted_in_errors(mock_post):
    """Test that API keys are redacted from error messages."""
    secret_key = "xai-secretkey123456"
    mock_post.return_value = make_error_response(
        400,
        f"Invalid API key: {secret_key}"
    )
    
    client = GrokAPIClient(api_key=secret_key)
    
    with pytest.raises(GrokAPIError) as exc_info:
        client.chat_completion("system", "user")
    
    error_str = str(exc_info.value)
    assert secret_key not in error_str
    assert "[REDACTED-API-KEY]" in error_str


def test_response_missing_choices(mock_post):
    """Test error when response is missing 'choices' field."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"error": "no choices"}
    mock_post.return_value = mock_response
    
    client = GrokAPIClient(api_key="xai-test")
    
    with pytest.raises(GrokAPIError) as exc_info:
        client.chat_completion("system", "user")
    
    assert "missing 'choices'" in str(exc_info.value).lower()


def test_response_empty_choices(mock_post):
    """Test error when choices array is empty."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": []}
    mock_post.return_value = mock_response
    
    client = GrokAPIClient(api_key="xai-test")
    
    with pytest.raises(GrokAPIError) as exc_info:
        client.chat_completion("system", "user")
    
    assert "empty 'choices'" in str(exc_info.value).lower()


def test_response_missing_message(mock_post):
    """Test error when choice is missing 'message' field."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"index": 0}]}
    mock_post.return_value = mock_response
    
    client = GrokAPIClient(api_key="xai-test")
    
    with pytest.raises(GrokAPIError) as exc_info:
        client.chat_completion("system", "user")
    
    assert "missing 'message'" in str(exc_info.value).lower()


def test_response_missing_content(mock_post):
    """Test error when message is missing 'content' field."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"role": "assistant"}}]
    }
    mock_post.return_value = mock_response
    
    client = GrokAPIClient(api_key="xai-test")
    
    with pytest.raises(GrokAPIError) as exc_info:
        client.chat_completion("system", "user")
    
    assert "missing 'content'" in str(exc_info.value).lower()


def test_response_null_content(mock_post):
    """Test error when content is null."""
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": None}, "finish_reason": "stop"}]
    }
    mock_post.return_value = mock_response
    
    client = GrokAPIClient(api_key="xai-test")
    
    with pytest.raises(GrokAPIError) as exc_info:
        client.chat_completion("system", "user")
    
    assert "content is null" in str(exc_info.value).lower()


def test_response_truncated_finish_reason_length(mock_post):
    """Test error when response is truncated (finish_reason: length)."""
    mock_post.return_value = make_success_response(
        "partial response...",
        finish_reason="length"
    )
    
    client = GrokAPIClient(api_key="xai-test")
    
    with pytest.raises(GrokAPIError) as exc_info:
        client.chat_completion("system", "user")
    
    assert "truncated" in str(exc_info.value).lower()
    assert "max_tokens" in str(exc_info.value)


def test_timeout_error(mock_post):
    """Test handling of timeout errors."""
    mock_post.side_effect = requests.exceptions.Timeout("Connection timeout")
    
    client = GrokAPIClient(api_key="xai-test", max_retries=0)
    
    with pytest.raises(GrokAPIError) as exc_info:
        client.chat_completion("system", "user")
    
    assert "timeout" in str(exc_info.value).lower()


def test_network_error(mock_post):
    """Test handling of network errors."""
    mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
    
    client = GrokAPIClient(api_key="xai-test", max_retries=0)
    
    with pytest.raises(GrokAPIError) as exc_info:
        client.chat_completion("system", "user")
    
    assert "request failed" in str(exc_info.value).lower()


def test_custom_timeouts():
    """Test custom timeout configuration."""
    client = GrokAPIClient(
        api_key="xai-test",
        connect_timeout=10.0,
        read_timeout=60.0
    )
    
    assert client.connect_timeout == 10.0
    assert client.read_timeout == 60.0


def test_fake_client_basic():
    """Test FakeGrokClient basic functionality."""
    fake = FakeGrokClient(canned_response='{"test": "response"}')
    
    result = fake.chat_completion("system", "user")
    assert result == '{"test": "response"}'
    assert len(fake.calls) == 1


def test_fake_client_records_calls():
    """Test that FakeGrokClient records all parameters."""
    fake = FakeGrokClient()
    
    fake.chat_completion(
        system_prompt="sys",
        user_message="msg",
        model="custom-model",
        temperature=0.5,
        max_tokens=500,
        response_format="json_object",
    )
    
    call = fake.calls[0]
    assert call["system_prompt"] == "sys"
    assert call["user_message"] == "msg"
    assert call["model"] == "custom-model"
    assert call["temperature"] == 0.5
    assert call["max_tokens"] == 500
    assert call["response_format"] == "json_object"


def test_fake_client_default_response():
    """Test that FakeGrokClient generates valid default response."""
    fake = FakeGrokClient()
    result = fake.chat_completion("system", "user")
    
    # Should be valid JSON
    parsed = json.loads(result)
    assert "schema_version" in parsed
    assert "incident" in parsed
    assert "diagnosis" in parsed
