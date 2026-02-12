import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from requests import RequestException

from src.ndvi_processor.network.network import (get_s2_acquisition_dates,
                                                get_token)


def test_get_token_success():
    """Test that get_token returns token on success."""
    mock_response = Mock()
    mock_response.json.return_value = {"access_token": "test-token-123"}

    with patch('ndvi_processor.network.network.requests.post', return_value=mock_response):
        token = get_token("client-id", "client-secret")

    assert token == "test-token-123"
    mock_response.raise_for_status.assert_called_once()

def test_get_token_missing_credentials():
    """Test that get_token raises error when credentials are missing."""
    with pytest.raises(ValueError, match="client_id and client_secret are required"):
        get_token(None, None)

# -----

import json


@pytest.fixture
def tmp_geojson(tmp_path):
    """Create a temporary AOI GeoJSON file."""
    aoi = {
        "type": "Polygon",
        "coordinates": [
            [
                [16.0, 48.0],
                [16.1, 48.0],
                [16.1, 48.1],
                [16.0, 48.1],
                [16.0, 48.0]
            ]
        ]
    }
    file_path = tmp_path / "aoi.geojson"
    file_path.write_text(json.dumps(aoi))
    return file_path


def test_get_s2_acquisition_dates_success(tmp_geojson):
    """Test successful retrieval and parsing of acquisition dates."""

    mock_response = {
        "features": [
            {"properties": {"datetime": "2024-01-05T10:20:00Z"}},
            {"properties": {"datetime": "2024-01-03T09:15:00Z"}},
            {"properties": {"datetime": "2024-01-05T11:00:00Z"}},  # duplicate date
        ]
    }

    with patch("ndvi_processor.network.network.requests.post") as mock_post:
        mock = MagicMock()
        mock.json.return_value = mock_response
        mock.raise_for_status.return_value = None
        mock_post.return_value = mock

        dates = get_s2_acquisition_dates(
            aoi_geojson_path=str(tmp_geojson),
            cdse_search_url="https://example.com/stac/search",
            token="fake-token",
            start="2024-01-01",
            end="2024-01-10"
        )

    assert dates == ["2024-01-03", "2024-01-05"]


def test_get_s2_acquisition_dates_invalid_geojson(tmp_path):
    """Test handling of invalid GeoJSON file."""

    bad_file = tmp_path / "bad.geojson"
    bad_file.write_text("{ invalid json }")

    with pytest.raises(ValueError):
        get_s2_acquisition_dates(
            aoi_geojson_path=str(bad_file),
            cdse_search_url="https://example.com/stac/search",
            token="fake-token",
            start="2024-01-01",
            end="2024-01-10"
        )


def test_get_s2_acquisition_dates_api_error(tmp_geojson):
    """Test handling of API request failure."""

    with patch("ndvi_processor.network.network.requests.post") as mock_post:
        mock_post.side_effect = RequestException("Network error")

        with pytest.raises(RuntimeError):
            get_s2_acquisition_dates(
                aoi_geojson_path=str(tmp_geojson),
                cdse_search_url="https://example.com/stac/search",
                token="fake-token",
                start="2024-01-01",
                end="2024-01-10"
            )
