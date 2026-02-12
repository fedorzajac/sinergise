import json

import requests


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
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Read AOI
    with open(aoi_geojson_path) as f:
        aoi = json.load(f)

    # Search payload
    payload = {
        "collections": ["sentinel-2-l2a"],
        "datetime": f"{start}T00:00:00Z/{end}T00:00:00Z",
        "intersects": aoi,
        "limit": 100,  # max 100 results per page
    }
    print(payload)
    r = requests.post(cdse_search_url, headers=headers, data=json.dumps(payload))
    r.raise_for_status()
    results = r.json().get("features", [])

    dates = sorted([f["properties"]["datetime"][:10] for f in results])
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
            "resy": 10 # eh not possible with my free plan
            # removed in the end
        },
        "evalscript": evalscript,
    }
    return json_payload


def payload_old(
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
            "width": 512,
            "height": 512,  # we dont want specific size
            # but 10 by 10 resolution
            # "resx": 10,
            # "resy": 10 # eh not possible with my free plan
            # removed in the end
        },
        "evalscript": evalscript,
    }
    return json_payload
