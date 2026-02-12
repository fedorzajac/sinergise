import pytest
from unittest.mock import patch, Mock
from network import get_token

def test_get_token_success():
    """Test that get_token returns token on success."""
    mock_response = Mock()
    mock_response.json.return_value = {"access_token": "test-token-123"}

    with patch('network.requests.post', return_value=mock_response):
        token = get_token("client-id", "client-secret")

    assert token == "test-token-123"
    mock_response.raise_for_status.assert_called_once()

def test_get_token_missing_credentials():
    """Test that get_token raises error when credentials are missing."""
    with pytest.raises(ValueError, match="client_id and client_secret are required"):
        get_token(None, None)
