import argparse
import json
import logging
import os
from pathlib import Path

import numpy as np
import rasterio
import requests
from dotenv import load_dotenv
from rasterio.io import MemoryFile
from rasterio.merge import merge

from cli_tool.calculations import (acquisition_dates_to_download_dates,
                                   add_to_filename, calculate_epsg,
                                   convert_polygon_to_utm, fill_ndvi_gaps,
                                   generate_dekadal_dates,
                                   interpolate_ndvi_to_dekadals,
                                   ndvi_raster_stats, read_file,
                                   resize_raster_res, split_bbox)
from cli_tool.network import (
    get_s2_acquisition_dates, get_token, payload,
    download_and_merge_tiles
    )

from settings import Settings

# from rasterio.errors import RasterioIOError




def main(logging, args):

    with open(args.bb_file) as f:
        bb_file = json.load(f)

    logging.info(bb_file)

    settings = Settings(bb_file=bb_file, api_url=DATA_SPACE_URL)


    # !important -> convert to raster (only bounding box for now for simplicity)
    bbox = convert_polygon_to_utm(args.bb_file)
    # generalization - calculate epsg
    epsg = calculate_epsg(args.bb_file)

    token = get_token(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET, url=COPERNICUS_TOKEN_URL
    )

    dekadals = generate_dekadal_dates(args.start, args.end)
    logging.info(dekadals)

    flyover_dates = get_s2_acquisition_dates(
        aoi_geojson_path=args.bb_file,
        cdse_search_url=CDSE_SEARCH_URL,
        token=token,
        start=args.start,
        end=args.end,
    )
    logging.info(flyover_dates)

    download_dates = acquisition_dates_to_download_dates(
        dekadals=dekadals, available=flyover_dates
    )
    logging.info(download_dates)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "image/tiff",
    }

    merged_filenames = []

    for date in download_dates:
        result = download_and_merge_tiles(
            date=date,
            bbox_tiles=split_bbox(bbox),
            epsg=epsg,
            evalscript=read_file("./evalscripts/sentinel.js"),
            headers=headers,
            api_url=DATA_SPACE_URL
        )

        if result is None:
            continue

        mosaic, out_meta = result

        # Replace -99999 with NaN (already done in function, but keep for clarity)
        # mosaic[mosaic == -99999] = np.nan  # Already handled in function

        saved_file = add_to_filename(filename=args.output, addon="_" + date)
        with rasterio.open(saved_file, "w", **out_meta) as f:
            f.write(mosaic)

        logging.info(f"Picture saved {saved_file}")
        logging.info(ndvi_raster_stats(saved_file))
        merged_filenames.append(saved_file)


    logging.info("🍭")
    logging.info(merged_filenames)

    # get supplemental data

    supplemental_filenames = []

    for date in dekadals:
        result = download_and_merge_tiles(
            date=date,
            bbox_tiles=split_bbox(bbox),
            epsg=epsg,
            evalscript=read_file("./evalscripts/clms.js"),
            headers=headers,
            api_url=DATA_SPACE_URL,
            data_collection="byoc-ab0e1e8e-508c-4faa-9b5b-c9c4734ef29e"  # <-- ROZDIEL!
        )

        if result is None:
            continue

        mosaic, out_meta = result

        saved_file = add_to_filename(filename=args.output, addon="_supplemental_" + date)
        with rasterio.open(saved_file, "w", **out_meta) as f:
            f.write(mosaic)

        logging.info(f"Picture saved {saved_file}")
        logging.info(ndvi_raster_stats(saved_file))
        supplemental_filenames.append(saved_file)

    logging.info("📚")
    logging.info(supplemental_filenames)

    # now I will interpolate all data to dekadals

    interpolated_files = interpolate_ndvi_to_dekadals(
        image_paths=merged_filenames,
        flyover_dates=download_dates,  # aligned flyover dates
        dekadal_dates=dekadals,
        output_template=args.output + "{}_10m.tiff",
    )

    logging.info("⏱️")
    logging.info(interpolated_files)
    # and finally filling in gaps in data from supplemental files.

    for date in dekadals:
        logging.info(date)
        # files_with_date = [item for item in interpolated_files if date in item and "10m" in item]
        interpolated = [item for item in interpolated_files if date in item]
        supplemental = [item for item in supplemental_filenames if date in item]
        logging.info(interpolated)
        logging.info(supplemental)
        if len(interpolated) == 1 and len(supplemental) == 1:
            fill_ndvi_gaps(interpolated[0], supplemental[0])


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler("cli.log"), logging.StreamHandler()],
    )

    logger = logging.getLogger(__name__)

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
    logging.info(args)

    main(logging, args)
