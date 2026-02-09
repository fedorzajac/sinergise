import requests
from dotenv import load_dotenv
from typing import TypeAlias
import rasterio
from rasterio.io import MemoryFile
from rasterio.merge import merge
from rasterio.errors import RasterioIOError
import os
import geopandas as gpd
from datetime import date
import json

from calculations import (
    acquisition_dates_to_download_dates,
    add_to_filename,
    convert_polygon_to_utm,
    generate_dekadal_dates,
    interpolate_ndvi_to_dekadals,
    ndvi_raster_stats,
    read_file,
    resize_raster_res,
    fill_ndvi_gaps,
    calculate_epsg,
)
from network import get_s2_acquisition_dates, get_token, payload

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID") or ""
CLIENT_SECRET = os.getenv("CLIENT_SECRET") or ""
COPERNICUS_TOKEN_URL = os.getenv("COPERNICUS_TOKEN_URL") or ""
DATA_SPACE_URL = os.getenv("DATA_SPACE_URL") or ""
CDSE_SEARCH_URL = os.getenv("CDSE_SEARCH_URL") or ""

BBox: TypeAlias = list[float]

# lets just shadow the payload function for now so we change width and height to 1024
# also this could be done recursively everytime the api returns the too large area error
# but lets keep it simple :)
# ah wait, now I dont have to deal with w and h... because I have smaller bounding boxes....
# and I can have it recursively..... hmmm
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
            # "width": 1024,
            # "height": 1024,  # we dont want specific size
            # but 10 by 10 resolution
            "resx": 10,
            "resy": 10 # eh not possible with my free plan
            # removed in the end
        },
        "evalscript": evalscript,
    }
    return json_payload


# using only bounding box
# rasterized polygon later.
# returns meters from equator and meridian?
# [ 520647.58484602 5201547.78622006  546889.23529065 5217998.04777367]
def convert_polygon_to_utm(file_path: str) -> BBox:
    gdf = gpd.read_file(file_path)
    utm_crs = gdf.estimate_utm_crs()
    gdf = gdf.to_crs(utm_crs)
    print(gdf.total_bounds)
    return gdf.total_bounds  # returning ndarray

def split_bbox(bbox: BBox):
    minx, miny, maxx, maxy = bbox
    midx = (minx + maxx) / 2
    midy = (miny + maxy) / 2

    return [
        [float(minx), float(miny), float(midx), float(midy)], # bottom-left
        [float(midx), float(miny), float(maxx), float(midy)], # bottom-right
        [float(minx), float(midy), float(midx), float(maxy)], # top-left
        [float(midx), float(midy), float(maxx), float(maxy)], # top-right
    ]


def test_splitting_graz():
    source = "./AOI_test.geojson"
    bounds = convert_polygon_to_utm(source)
    print(bounds)
    splitted = split_bbox(bounds)
    print(splitted)
    expected_for_graz = [
        [520647.58484601777, 5201547.786220064, 533768.4100683336, 5209772.9169968655],
        [533768.4100683336, 5201547.786220064, 546889.2352906496, 5209772.9169968655],
        [520647.58484601777, 5209772.9169968655, 533768.4100683336, 5217998.047773667],
        [533768.4100683336, 5209772.9169968655, 546889.2352906496, 5217998.047773667]
    ]
    # not very pleased of the decimal format and also it may cause trouble on different architecture probably,
    # so the test should be probably be done a little more inteligent
    assert splitted == expected_for_graz


def test_data_download_graz():

    token = get_token(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, url=COPERNICUS_TOKEN_URL)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "image/tiff",
    }

    source = "./AOI_test.geojson"
    bounds = convert_polygon_to_utm(source)
    tiles = split_bbox(bounds)   # or split_bbox_for_resolution(...)

    datasets = []   # rasterio datasets kept open

    for tile in tiles:
        payload_json = payload(
            start_date=date.fromisoformat('2025-08-02'),
            end_date=date.fromisoformat('2025-08-02'),
            bounding_box=[float(x) for x in tile],
            epsg=calculate_epsg("./AOI_test.geojson"),
            evalscript=read_file("./sentinel.js")
        )

        # --- download tile ---
        response = requests.post(
            url=DATA_SPACE_URL,
            headers=headers,
            data=json.dumps(payload_json)
        )
        response.raise_for_status()

        try:
            memfile = MemoryFile(response.content)
            ds = memfile.open()   # keep open for merge()
            ds.read(1) # to validate "file" and catch error
        except Exception as e:
            print("Error:", e)
            continue

        datasets.append(ds)

    # --- merge all tiles ---
    mosaic, out_transform = merge(datasets)

    # --- build output metadata ---
    out_meta = datasets[0].meta.copy()
    out_meta.update({
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_transform
    })

    # --- save final mosaic ---
    with rasterio.open("final.tif", "w", **out_meta) as dst:
        dst.write(mosaic)

    # --- close datasets ---
    for ds in datasets:
        ds.close()
