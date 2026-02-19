import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from requests import RequestException
import numpy as np

from cli_tool.network import (
    get_s2_acquisition_dates,
    download_tile,
    download_and_merge_tiles,
    get_token)

from cli_tool.settings import Settings


def test_get_token_success():
    """Test that get_token returns token on success."""
    mock_response = Mock()
    mock_response.json.return_value = {"access_token": "test-token-123"}

    with patch('cli_tool.network.requests.post', return_value=mock_response):
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

    with patch("cli_tool.network.requests.post") as mock_post:
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

    with patch("cli_tool.network.requests.post") as mock_post:
        mock_post.side_effect = RequestException("Network error")

        with pytest.raises(RuntimeError):
            get_s2_acquisition_dates(
                aoi_geojson_path=str(tmp_geojson),
                cdse_search_url="https://example.com/stac/search",
                token="fake-token",
                start="2024-01-01",
                end="2024-01-10"
            )

def test_download_tile_success():
    """Test successful tile download."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"fake tiff data"
    mock_settings = MagicMock()
    mock_settings.epsg = 32633
    mock_settings.headers = {"Authorization": "Bearer fake"}
    mock_settings.api_url = "https://fake.com"
    mock_settings.data_collection = "sentinel-2-l2a"

    with patch('cli_tool.network.requests.post', return_value=mock_response):
        with patch('cli_tool.network.payload', return_value={}):
            result = download_tile(
                date="2025-08-02",
                chunk=[0, 0, 1000, 1000],
                evalscript="fake script",
                settings=mock_settings
            )

    assert result is not None
    assert result.status_code == 200


def test_download_and_merge_tiles_success():
    """Test successful download and merge."""
    # Mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"GeoTIFF content"

    mock_settings = MagicMock()
    mock_settings.epsg = 32633
    mock_settings.headers = {"Authorization": "Bearer fake"}
    mock_settings.api_url = "https://fake.com"
    mock_settings.data_collection = "sentinel-2-l2a"

    # Mock rasterio dataset
    mock_ds = MagicMock()
    mock_ds.read.return_value = np.ones((100, 100), dtype=np.float32)
    mock_ds.meta = {
        'driver': 'GTiff',
        'dtype': 'float32',
        'nodata': None,
        'width': 100,
        'height': 100,
        'count': 1,
        'crs': 'EPSG:32633',
        'transform': Mock()
    }

    # Mock merge output
    mock_mosaic = np.ones((1, 200, 200), dtype=np.float32)
    mock_transform = Mock()

    with patch('cli_tool.network.download_tile', return_value=mock_response):
        with patch('cli_tool.network.MemoryFile') as mock_memfile:
            mock_memfile.return_value.open.return_value = mock_ds
            with patch('cli_tool.network.merge', return_value=(mock_mosaic, mock_transform)):
                result = download_and_merge_tiles(
                    date="2025-08-02",
                    bbox_tiles=[[0, 0, 500, 500], [500, 0, 1000, 500]],
                    # epsg=32633,
                    evalscript="fake script",
                    # headers={"Authorization": "Bearer token"},
                    # api_url="https://api.example.com"
                    settings=mock_settings
                )

    assert result is not None
    mosaic, out_meta = result
    assert mosaic.shape == (1, 200, 200)
    assert out_meta['width'] == 200
    assert out_meta['height'] == 200
