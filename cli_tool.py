import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

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

parser = argparse.ArgumentParser(description="Creating NDVI")

parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
parser.add_argument("--bb_file", "-bbf", required=True, default="input.geojson")
parser.add_argument("--product", choices=["NDVI"], default="NDVI")
parser.add_argument("--output", "-o", default="output.tif", help="Output file")
parser.add_argument(
    "--resolution", "-r", default="10", help="resolution in m per pixel"
)
args = parser.parse_args()
print(args)

with open(args.bb_file) as f:
    bb_file = json.load(f)

print(bb_file)

# !important -> convert to raster (only bounding box for now for simplicity)
bbox = convert_polygon_to_utm(args.bb_file)
# generalization - calculate epsg
epsg = calculate_epsg(args.bb_file)

token = get_token(client_id = CLIENT_ID, client_secret = CLIENT_SECRET, url = COPERNICUS_TOKEN_URL)

dekadals = generate_dekadal_dates(args.start, args.end)
print(dekadals)

flyover_dates = get_s2_acquisition_dates(
    aoi_geojson_path=args.bb_file,
    cdse_search_url=CDSE_SEARCH_URL,
    token=token,
    start=args.start,
    end=args.end
)
print(flyover_dates)

download_dates = acquisition_dates_to_download_dates(dekadals=dekadals, available=flyover_dates)
print(download_dates)


headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Accept": "image/tiff",
}


resized_filenames = []

for date in download_dates:
    print(f"Downloading for {date}")
    json_payload = payload(
        start_date=date,
        end_date=date,
        bounding_box=bbox.tolist(),
        epsg=epsg,
        evalscript=read_file("./sentinel.js")
    )  # same date for start and end

    response = requests.post(
        url=DATA_SPACE_URL, headers=headers, data=json.dumps(json_payload)
    )

    if response.status_code == 200:
        saved_file = add_to_filename(args.output, "_" + date)
        with open(saved_file, "wb") as f:
            f.write(response.content)

        print(f"Picture saved {saved_file}")
        print(ndvi_raster_stats(saved_file))
        # resizing
        resized = add_to_filename(saved_file, "_10m")
        resized_filenames.append(resized)
        resize_raster_res(saved_file, resized, int(args.resolution))
        print(ndvi_raster_stats(resized))
    else:
        print("Error:", response.status_code, response.text)

# get supplemental data

resized__supplemental_filenames = []

for date in dekadals:
    print(f"Downloading for {date}")
    json_payload = payload(
        start_date=date,
        end_date=date,
        bounding_box=bbox.tolist(),
        epsg=epsg,
        evalscript=read_file("./clms.js"),
        data_collection="byoc-ab0e1e8e-508c-4faa-9b5b-c9c4734ef29e",
    )  # same date for start and end

    response = requests.post(
        url=DATA_SPACE_URL, headers=headers, data=json.dumps(json_payload)
    )

    if response.status_code == 200:
        saved_file = add_to_filename(filename=args.output, addon="_supplemental_" + date)
        with open(saved_file, "wb") as f:
            f.write(response.content)

        print(f"Picture saved {saved_file}")
        print(ndvi_raster_stats(saved_file))
        # resizing
        resized = add_to_filename(filename=saved_file, addon="_10m")
        resized__supplemental_filenames.append(resized)
        resize_raster_res(src_path=saved_file, dst_path=resized, res=int(args.resolution), band=1)
        # 2 because the index values are on the second layer/band (does not work)
        # yes, in the end I changed the default clms.js file, so the default is on band 1

        print(ndvi_raster_stats(resized))
    else:
        print("Error:", response.status_code, response.text)

print(resized__supplemental_filenames)

# now I will interpolate all data to dekadals

interpolate_ndvi_to_dekadals(
    image_paths=resized_filenames,
    flyover_dates=download_dates,  # aligned flyover dates
    dekadal_dates=dekadals,
    output_template="graz_dekadal_aligned_{}_10m.tiff",
)

# and finally filling in gaps in data from supplemental files.

files = os.listdir(".")

for date in dekadals:
    print(date)
    files_with_date = [item for item in files if date in item and "10m" in item]
    aligned = [item for item in files_with_date if "aligned" in item and "filled" not in item]
    supplemental = [item for item in files_with_date if "supplemental" in item and "filled" not in item]
    print(aligned)
    print(supplemental)
    if len(aligned) == 1 and len(supplemental) == 1:
        fill_ndvi_gaps(aligned[0], supplemental[0])
