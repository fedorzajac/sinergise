from calculations import (
    ndvi_raster_stats,
    interpolate_ndvi_to_dekadals,
    fill_ndvi_gaps
)
import os

# for f in os.listdir("."):
#     if f.lower().endswith(".tiff"):
#         full_path = os.path.join(".", f)
#         print(f)
#         print(ndvi_raster_stats(full_path))



# resized_filenames = [
#     'graz_3_2025-08-0210m.tiff',
#     'graz_3_2025-08-0910m.tiff',
#     'graz_3_2025-08-1210m.tiff',
#     'graz_3_2025-08-1910m.tiff',
#     'graz_3_2025-08-2210m.tiff',
#     ]
aligned_flyover_dates = ['2025-08-02', '2025-08-09', '2025-08-12', '2025-08-19', '2025-08-22']

dekadals = ['2025-08-01', '2025-08-11', '2025-08-21']

# interpolate_ndvi_to_dekadals(
#     image_paths=resized_filenames,
#     flyover_dates=aligned_flyover_dates,
#     dekadal_dates=dekadals,
#     output_template="graz_dekadal_aligned_{}_10m.tiff"
# )

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
