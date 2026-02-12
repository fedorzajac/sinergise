import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
import numpy as np

import rasterio
from rasterio.io import MemoryFile
from rasterio.merge import merge
# from rasterio.errors import RasterioIOError

from cli_tool.calculations import (
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
    split_bbox
)
from cli_tool.network import get_s2_acquisition_dates, get_token, payload

import logging

def main(logging, args):

    with open(args.bb_file) as f:
        bb_file = json.load(f)

    logging.info(bb_file)

    # !important -> convert to raster (only bounding box for now for simplicity)
    bbox = convert_polygon_to_utm(args.bb_file)
    # generalization - calculate epsg
    epsg = calculate_epsg(args.bb_file)

    token = get_token(client_id = CLIENT_ID, client_secret = CLIENT_SECRET, url = COPERNICUS_TOKEN_URL)

    dekadals = generate_dekadal_dates(args.start, args.end)
    logging.info(dekadals)

    flyover_dates = get_s2_acquisition_dates(
        aoi_geojson_path=args.bb_file,
        cdse_search_url=CDSE_SEARCH_URL,
        token=token,
        start=args.start,
        end=args.end
    )
    logging.info(flyover_dates)

    download_dates = acquisition_dates_to_download_dates(dekadals=dekadals, available=flyover_dates)
    logging.info(download_dates)


    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "image/tiff",
    }


    merged_filenames = []

    for date in download_dates:
        logging.info(f"Downloading for {date}")
        chunks = []
        for chunk in split_bbox(bbox):
            logging.info(chunk)
            json_payload = payload(
                start_date=date,
                end_date=date,
                bounding_box=[float(f) for f in chunk], # oh my types
                epsg=epsg,
                evalscript=read_file("./evalscripts/sentinel.js")
            )  # same date for start and end

            response = requests.post(
                url=DATA_SPACE_URL, headers=headers, data=json.dumps(json_payload)
            )

            if response.status_code == 200:
            # catching the corrupted data form sentinel (not exactly corrupted - very funny easter egg!)
                try:
                    memfile = MemoryFile(response.content)
                    ds = memfile.open()   # keep open for merge()
                    ds.read(1) # to validate "file" and catch error
                except Exception as e:
                    logging.error("Error:", e)
                    continue

                chunks.append(ds)
            else:
                logging.error("Error:", response.status_code, response.text)


        # chunk check
        if not chunks:
            logging.error(f"No valid chunks for {date}, skipping")
            continue
        # --- merge all tiles ---
        mosaic, out_transform = merge(chunks)

        out_meta = chunks[0].meta.copy()
        out_meta.update({
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_transform,
            "nodata": np.nan
        })

        mosaic = mosaic.astype("float32")
        mosaic[mosaic == -99999] = np.nan # so I have normal data, that I can interpolate into dekadals...
        # mosaic = np.clip(mosaic, -1, 1)

        saved_file = add_to_filename(filename= args.output, addon= "_" + date)
        with rasterio.open(saved_file, "w", **out_meta) as f:
            f.write(mosaic)

        for ds in chunks:
            ds.close()

        logging.info(f"Picture saved {saved_file}")
        logging.info(ndvi_raster_stats(saved_file))
            # i dont need this I believe
            # # resizing
            # resized = add_to_filename(saved_file, "_10m")
        merged_filenames.append(saved_file)
            # resize_raster_res(saved_file, resized, int(args.resolution))
            # logging.info(ndvi_raster_stats(resized))

    logging.info("🍭")
    logging.info(merged_filenames)

    # get supplemental data

    supplemental_filenames = []

    for date in dekadals:
        logging.info(f"Downloading for {date}")
        chunks = []
        for chunk in split_bbox(bbox):
            logging.info(chunk)
            json_payload = payload(
                start_date=date,
                end_date=date,
                bounding_box=[float(f) for f in chunk], # oh my types
                epsg=epsg,
                evalscript=read_file("./evalscripts/clms.js"),
                data_collection="byoc-ab0e1e8e-508c-4faa-9b5b-c9c4734ef29e",
            )  # same date for start and end

            response = requests.post(
                url=DATA_SPACE_URL, headers=headers, data=json.dumps(json_payload)
            )

            if response.status_code == 200:
                # catching the corrupted data form sentinel (not exactly corrupted - very funny easter egg!)
                try:
                    memfile = MemoryFile(response.content)
                    ds = memfile.open()   # keep open for merge()
                    ds.read(1) # to validate "file" and catch error
                except Exception as e:
                    logging.error("Error:", e)
                    continue

                chunks.append(ds)
            else:
                logging.error("Error:", response.status_code, response.text)


        # chunk check
        if not chunks:
            logging.error(f"No valid chunks for {date}, skipping")
            continue
        # --- merge all tiles ---
        mosaic, out_transform = merge(chunks)

        out_meta = chunks[0].meta.copy()
        out_meta.update({
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_transform
        })

        saved_file = add_to_filename(filename=args.output, addon="_supplemental_" + date)
        with rasterio.open(saved_file, "w", **out_meta) as f:
                f.write(mosaic)

        for ds in chunks:
            ds.close()

        logging.info(f"Picture saved {saved_file}")
        logging.info(ndvi_raster_stats(saved_file))
                # resizing
        # resized = add_to_filename(filename=saved_file, addon="_10m")
        supplemental_filenames.append(saved_file)
        # resize_raster_res(src_path=saved_file, dst_path=resized, res=int(args.resolution), band=1)
        # # 2 because the index values are on the second layer/band (does not work)
        # # yes, in the end I changed the default clms.js file, so the default is on band 1

        # logging.info(ndvi_raster_stats(resized))

    logging.info("📚")
    logging.info(supplemental_filenames)

    # now I will interpolate all data to dekadals

    interpolated_files = interpolate_ndvi_to_dekadals(
        image_paths=merged_filenames,
        flyover_dates=download_dates,  # aligned flyover dates
        dekadal_dates=dekadals,
        output_template=args.output+"{}_10m.tiff",
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
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('cli.log'),
            logging.StreamHandler()
        ]
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
