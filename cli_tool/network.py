import json
import os

import requests
import logging

import numpy as np
import rasterio
import requests
from dotenv import load_dotenv
from rasterio.io import MemoryFile
from rasterio.merge import merge
from cli_tool.settings import Settings


def get_token(
    client_id: str | None,
    client_secret: str | None,
    url="https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
) -> str | None:
    # raise error if parameter missing or request fail
    # retry/refresh
    if not client_id or not client_secret:
        raise ValueError("client_id and client_secret are required")

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    try:
        r = requests.post(url, data=data)
        r.raise_for_status()
        response_data = r.json()
        return response_data["access_token"]
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to get auth token: {e}")
    except KeyError:
        raise RuntimeError("Invalid response: missing access_token in API response")


def get_s2_acquisition_dates(aoi_geojson_path, cdse_search_url, token, start, end):

    if not os.path.exists(aoi_geojson_path):
        raise FileNotFoundError(f"AOI file not found: {aoi_geojson_path}")
    if not isinstance(start, str) or not isinstance(end, str):
        raise ValueError("start and end must be ISO date strings (YYYY-MM-DD)")
    if not token:
        raise ValueError("Missing authentication token")

    # Trying to read AOI
    try:
        with open(aoi_geojson_path) as f:
            aoi = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid GeoJSON file: {e}")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Search payload
    payload = {
        "collections": ["sentinel-2-l2a"],
        "datetime": f"{start}T00:00:00Z/{end}T00:00:00Z",
        "intersects": aoi,
        "limit": 100,  # max 100 results per page
    }

    try:
        r = requests.post(
            cdse_search_url, headers=headers, data=json.dumps(payload), timeout=30
        )
        r.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"CDSE API request failed: {e}")

    features = r.json().get("features", [])

    dates = sorted(set(f["properties"]["datetime"][:10] for f in features))

    return dates


from datetime import datetime, timedelta


def payload(
    start_date: str,
    end_date: str,
    bounding_box: list,
    evalscript: str,
    epsg: int,
    data_collection: str = "sentinel-2-l2a",
) -> dict:
    json_payload = {
        "input": {
            "bounds": {
                # "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}, # this is for lon/lat
                "properties": {
                    "crs": f"http://www.opengis.net/def/crs/EPSG/0/{epsg}"
                },  # and this is for metric
                "bbox": bounding_box,
            },
            "data": [
                {
                    "type": data_collection,
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{start_date}T00:00:00Z",
                            "to": f"{end_date}T23:59:59Z",  # end date included
                        }
                    },
                }
            ],
        },
        "output": {
            # "width": 512,
            # "height": 512,  # we dont want specific size
            # but 10 by 10 resolution
            "resx": 10,
            "resy": 10,  # eh not possible with my free plan
            # removed in the end
        },
        "evalscript": evalscript,
    }
    return json_payload


def download_tile(
    date: str,
    chunk: list,
    # epsg: int,
    evalscript: str,
    # headers: dict,
    # api_url: str,
    # data_collection: str = "sentinel-2-l2a"
    settings: Settings
):
    """Download single tile from API."""
    from cli_tool.network import payload

    json_payload = payload(
        start_date=date,
        end_date=date,
        bounding_box=[float(f) for f in chunk],
        epsg=settings.epsg,
        evalscript=evalscript,
        data_collection=settings.data_collection
    )

    response = requests.post(
        url=settings.api_url,
        headers=settings.headers,
        data=json.dumps(json_payload)
    )

    if response.status_code != 200:
        logging.error(f"Error: {response.status_code} - {response.text}")
        return None

    return response


def download_and_merge_tiles(
    date: str,
    bbox_tiles: list,
    # epsg: int,
    evalscript: str,
    # headers: dict,
    # api_url: str,
    # data_collection: str = "sentinel-2-l2a"
    settings: Settings
):
    """Download all tiles and merge into single raster."""
    logger = logging.getLogger(__name__)
    logger.info(f"Downloading for {date}")

    chunks = []

    for chunk in bbox_tiles:
        logger.info(f"Processing tile: {chunk}")

        response = download_tile(
            date=date,
            chunk=chunk,
            evalscript=evalscript,
            # epsg=settings.epsg,
            # headers=settings.headers,
            # api_url=settings.api_url,
            # data_collection=settings.data_collection
            settings=settings
        )

        if response is None:
            continue

        # Validate raster data
        try:
            memfile = MemoryFile(response.content)
            ds = memfile.open()
            ds.read(1)  # validate file
            chunks.append(ds)
        except Exception as e:
            logger.error(f"Invalid raster data: {e}")
            continue

    # Check if we have any valid chunks
    if not chunks:
        logger.error(f"No valid chunks for {date}")
        return None

    # Merge all tiles
    mosaic, out_transform = merge(chunks)

    # Create metadata
    out_meta = chunks[0].meta.copy()
    out_meta.update({
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_transform,
        "nodata": np.nan,
    })

    # Clean up: replace sentinel's -99999 with NaN
    mosaic = mosaic.astype("float32")
    mosaic[mosaic == -99999] = np.nan

    # Close all datasets
    for ds in chunks:
        ds.close()

    return mosaic, out_meta
