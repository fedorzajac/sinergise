import json
import os
from bisect import bisect_left
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Tuple, TypeAlias

import geopandas as gpd
import numpy as np
import rasterio
import requests
from rasterio.warp import Resampling, calculate_default_transform, reproject

BBox: TypeAlias = list[float]


def add_to_filename(filename: str, addon: str) -> str:
    p = Path(filename)
    return f"{p.stem}{addon}{p.suffix}"


def read_file(path: str) -> str:
    with open(path) as f:
        content = f.read()
    return content


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


def resize_raster_res(src_path: str, dst_path: str, res: int, band: int = 1):
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, src.crs, src.width, src.height, *src.bounds, resolution=(res, res)
        )

        profile = src.profile.copy()
        profile.update({"transform": transform, "width": width, "height": height})

        with rasterio.open(dst_path, "w", **profile) as dst:
            reproject(
                source=rasterio.band(src, band),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=src.crs,
                resampling=Resampling.bilinear,
            )


def generate_dekadal_dates(start_date: str, end_date: str) -> list[str]:
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)

    dekadals = []
    current = start.replace(day=1)  # start at first day of start month

    while current <= end:
        for day in [1, 11, 21]:
            d = current.replace(day=day)
            if start <= d <= end:
                dekadals.append(d.date().isoformat())  # I just want YYYY-MM-DD
        # move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return dekadals


def acquisition_dates_to_download_dates(
    dekadals: list[str],
    available: list[str],
) -> list[str]:
    """
    Returns minimal set of acquisition dates needed
    to interpolate NDVI for all dekadal dates.
    """

    # Parse and sort
    dekadals_d = sorted(date.fromisoformat(d) for d in dekadals)
    avail_d = sorted(set(date.fromisoformat(d) for d in available))

    needed = set()

    for d in dekadals_d:
        i = bisect_left(avail_d, d)

        # exact match
        if i < len(avail_d) and avail_d[i] == d:
            needed.add(avail_d[i])
            continue

        # before
        if i > 0:
            needed.add(avail_d[i - 1])

        # after
        if i < len(avail_d):
            needed.add(avail_d[i])

    return sorted(d.isoformat() for d in needed)


def ndvi_raster_stats(path: str):
    """
    Reads a single-band NDVI GeoTIFF and returns key statistics.
    No exceptions for you — just numbers.
    """
    with rasterio.open(path) as ds:
        arr = ds.read(1)
        height, width = arr.shape

    finite_mask = np.isfinite(arr)
    finite_vals = arr[finite_mask]
    size_mb = os.path.getsize(path) / (1024 * 1024)

    stats = {
        "shape": arr.shape,
        "dtype": str(arr.dtype),
        # "total_pixels": arr.size,
        # "valid_pixels": finite_mask.sum(),
        "valid_ratio": f"{float(finite_mask.sum() / arr.size):.2f}" if arr.size else 0,
        "values range": (
            f"{float(finite_vals.min()):.2f}:{float(finite_vals.max()):.2f}"
            if finite_vals.size
            else None
        ),
        "mean": f"{float(finite_vals.mean()):.2f}" if finite_vals.size else None,
        "size": f"{size_mb:.2f} MB",
    }
    return stats


def interpolate_ndvi_to_dekadals(
    image_paths: list[str],
    flyover_dates: list[str],  # ISO strings: "YYYY-MM-DD"
    dekadal_dates: list[str],  # ISO strings
    output_template: str,  # e.g. "graz_{}_10m.tiff" where {} will be dekadal date
):
    """
    image_paths : paths to downloaded NDVI rasters (float32, same shape & CRS)
    flyover_dates : corresponding dates for each raster
    dekadal_dates: target dates to interpolate NDVI to
    output_template: filename template for output rasters

    Returns: list of output file paths
    """
    # --- Step 1: load all rasters into array ---
    imgs = []
    date_objs = []
    for path, date_str in zip(image_paths, flyover_dates):
        with rasterio.open(path) as src:
            imgs.append(src.read(1))
            profile = src.profile.copy()  # all have same profile
        date_objs.append(datetime.fromisoformat(date_str).date())

    imgs = np.stack(imgs, axis=0)  # shape: (n_images, height, width)

    # --- Step 2: prepare output paths ---
    output_files = []

    # --- Step 3: interpolate for each dekadal date ---
    for dek_date_str in dekadal_dates:
        dek_date = datetime.fromisoformat(dek_date_str).date()

        # Find images immediately before and after
        before_idx = None
        after_idx = None
        for i, d in enumerate(date_objs):
            if d <= dek_date:
                before_idx = i
            if d >= dek_date and after_idx is None:
                after_idx = i

        if before_idx is None:
            before_idx = after_idx
        if after_idx is None:
            after_idx = before_idx

        if before_idx == after_idx:
            # Exact date or no surrounding images: take it as is
            interp_img = imgs[before_idx]
        else:
            # Linear interpolation
            d_before = date_objs[before_idx]
            d_after = date_objs[after_idx]
            total_days = (d_after - d_before).days
            weight = (dek_date - d_before).days / total_days if total_days > 0 else 0
            img_before = imgs[before_idx]
            img_after = imgs[after_idx]
            interp_img = img_before * (1 - weight) + img_after * weight

            # Keep NaNs from both sides
            nan_mask = np.isnan(img_before) & np.isnan(img_after)
            interp_img[nan_mask] = np.nan

        # --- Step 4: write output ---
        out_path = output_template.format(dek_date_str)
        print(out_path)
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(interp_img.astype(np.float32), 1)

        output_files.append(out_path)
        print(f"Interpolated NDVI saved for {dek_date_str} -> {out_path}")

    return output_files


def fill_ndvi_gaps(
    main_path: str,
    supplemental_path: str,
) -> bool:
    # also there are a lot of ways approaching return value, in my past experience it is probably better to return true/false
    # of cource it depends. at least when there is just print statement
    # but true false are handy in pipelines especialy if you dont want to pipeline to fail. but sometimes you want.
    """
    Fill NaNs in main NDVI raster using supplemental NDVI raster.
    """
    if not rasters_are_compatible(main_path, supplemental_path):
        print("not compatible")
        return False

    with rasterio.open(main_path) as src_main:
        main = src_main.read(1)
        profile = src_main.profile.copy()

    with rasterio.open(supplemental_path) as src_sup:
        sup = src_sup.read(1)

    # --- Core logic ---
    filled = np.where(np.isnan(main), sup, main)

    # Preserve NaN where both are NaN
    both_nan = np.isnan(main) & np.isnan(sup)
    filled[both_nan] = np.nan

    new_filename = add_to_filename(main_path, "_filled")
    with rasterio.open(new_filename, "w", **profile) as dst:
        dst.write(filled.astype(np.float32), 1)

    print(f"Gap-filled NDVI saved -> {new_filename}")
    return True


# sanity check before filling gaps


def rasters_are_compatible(a_path: str, b_path: str) -> bool:
    with rasterio.open(a_path) as a, rasterio.open(b_path) as b:

        if a.shape != b.shape:
            # raise ValueError("Main and supplemental rasters must have the same shape")
            # hmm this is a little bit tricky where to return errors because:
            # you return one by one but you solve one at a time
            # so I just return false and "log" the error and no filling happens or instead of logging I raise value error
            print("shape mismatch")
            print(a.shape)
            print(b.shape)

        if a.crs != b.crs:
            print("Coordinates reference system mismatched!")
            print(a.crs)
            print(b.crs)

        if a.width != b.width or a.height != b.height:
            print("size mismatch!")
            print(a.width + a.height)
            print(b.width + b.height)

        if not np.allclose(a.transform, b.transform):
            print("transform mismatch")
            print(a.transform)
            print(b.transform)

        if a.dtypes[0] != b.dtypes[0]:
            print("type mismatch")
            print(a.dtypes[0])
            print(b.dtypes[0])

        return (
            a.crs == b.crs
            and a.transform == b.transform
            and a.width == b.width
            and a.height == b.height
            and a.dtypes[0] == b.dtypes[0] == "float32"
            and np.allclose(a.transform, b.transform)
        )
