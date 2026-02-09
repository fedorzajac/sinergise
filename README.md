# How to run the code

note: forgot to mention that you need to create `.env` file inside directory root and fill it with contenct from `.env.example`

```bash
python3.13 -m venv env
source env/bin/activate
pip install -r requirements.txt
python cli_tool.py --start 2025-08-01 --end 2025-08-31 -bbf AOI_test.geojson -o graz_4.tiff
```

but that is tricky, normally it should be in dev container or docker

output fill be dekadal files with "filled"
I didnt doo clearing of files so I can check how it works.

what I learn:

I get insights on how to work with geospatial data and basic understanding of data format and evalscript, overview of resources and hot to access them.

I also ran data on 2025-06-01 to 2025-07-31, particullary "graz_dekadal_aligned_2025-07-01_10m_filled.tiff" was interesting

# AI summary of my approach
from approach.md

## Task 1 – Dekadal NDVI Synthesis Pipeline

### Goal

Design and implement a Python-based pipeline that produces a **dekadal NDVI composite** (1st, 11th, 21st of each month) from Sentinel-2 data, handling:

- Irregular satellite revisit times
- Temporal interpolation for missing dekadal dates
- Optional gap filling using a coarser supplemental dataset (CLMS NDVI 300 m)

The pipeline is designed to be automation-friendly (e.g. suitable for Airflow).

---

### Inputs

- AOI provided as GeoJSON
- Date range
- Output resolution and directory structure
- CLI-driven execution (planned)

---

### Processing Workflow

#### 1. AOI Handling
- Read AOI polygon from GeoJSON
- Convert geometry from WGS84 to appropriate **UTM CRS**
  - Detect UTM zone based on longitude
  - Split geometry if it spans multiple zones (not implemented, noted)
- Derive bounding box from projected AOI for API requests

#### 2. Sentinel-2 NDVI Acquisition
- Use Sentinel Hub Process API with **Sentinel-2 L2A**
- Compute NDVI in `evalscript`
- Enforce:
  - `float32` output
  - Value range `[-1, 1]`
- Handle API constraints:
  - `width/height ≤ 2500`
  - Resolution limits require **resampling after download**

#### 3. Dekadal Grid Generation
- Generate target dekadal dates: 1st, 11th, 21st
- Retrieve available acquisition dates (flyovers) for AOI
- Assume sufficient spatial overlap for simplicity

#### 4. Temporal Interpolation
- For each dekadal target date:
  - Find closest valid acquisitions before and after
  - Interpolate pixel-wise based on temporal distance
- Operate on locally stored rasters to avoid excessive API calls

#### 5. Supplemental Gap Filling (Bonus)
- Download **CLMS NDVI Global 300 m (10-daily)**
- Fix evalscript band selection and scaling
- Resample supplemental data to Sentinel-2 grid
- Fill remaining `NaN` pixels in interpolated Sentinel-2 NDVI

#### 6. Output
- Dekadal NDVI rasters:
  - Aligned grid
  - Consistent CRS
  - `float32` datatype
- Deterministic directory structure
- Reproducible pipeline

---

### Current State

- Sentinel-2 NDVI acquisition: complete
- Temporal interpolation: implemented
- CLMS supplemental gap filling: implemented
- Pipeline works end-to-end on downloaded data
- Pending:
  - Refactoring
  - Logging
  - Unified CLI interface
  - Basic automated tests

*Total effort so far: ~10 hours*
(mainly because I was not so familiar with python and Geo Data)


## Task 2 – BYOC Architecture Design

### Goal

Design a scalable workflow to onboard a **50 TB archive of high-resolution aerial imagery** hosted in a private AWS S3 bucket (us-west-2) into Sentinel Hub using the **BYOC (Bring Your Own COG) API**, making it accessible via Copernicus Browser.

---

### Key Insight

BYOC is **not** an ETL or data download pipeline.

It is a **data registration and indexing service** for existing **Cloud Optimized GeoTIFFs (COGs)**, enabling:

- On-demand access
- Processing via Sentinel Hub APIs
- Zero data duplication

---
## Proposed Workflow

### 1. Check data compatibility with Sentinel Hub
- tiles and bands constraints
- constraints and settings in documentation
- inspect data in QGIS

### 2. Convert data to COG with GDAL
- make sure required tools are installed (`gdal >= 3`)
- remove internal TIFF mask if needed
- retiling / conversion into smaller tiles
- GDAL example commands in documentation

### 3. Create account and bucket in Amazon S3
- region:
  - `us-west-2` for US
  - `eu-central-1` for EU
  - (bucket region requirements in documentation)
- unique bucket name
- bucket settings:
  - permissions from documentation
  - JSON policy from documentation → update bucket
- upload tiles

### 4. Create collection and add it to the dashboard
- create new collection:
  - name
  - type: **BYOC**
  - location (AWS bucket region)
  - bucket name
- save collection
- copy **Collection ID**
- Sentinel Hub only displays data from that bucket (data stays in S3)

### 5. Add tiles
- dashboard → tiles → add tile
- copy S3 path from bucket (≈ 21:21 in video)
- rename file to define default bands
- add tiles one by one (:D)
- note on naming conventions (≈ 23:45)
- if file is deleted from the bucket:
  - it must be deleted from Sentinel Hub as well
  - or re-ingested
- set / fix band naming

### 6. Request in Sentinel Hub
- set correct time range
- set EvalScript
- convert values correctly:
  - `0–255 → 0–1` (`RGB / 255`)
- set bounding box
- test request
- set NoData value mask in dashboard (≈ 30:00)
- optional:
  - cover geometry (documentation)
  - cover geometry editor

### 7. Process API request / visualization
- configuration utility → new configuration
- new layer:
  - source: BYOC
  - collection: BYOC Collection ID (from AWS) (≈ 33:38)
- copy EvalScript
- save
- EO Browser:
  - set sensing time
  - click **Visualise**

### 8. QGIS integration
- install Sentinel Hub plugin (≈ 37:00, separate webinar)
- BYOC tool available on GitHub

---

## What I Learned

### Technical
- Sentinel Hub resolution limits are enforced via `width/height`, not just meters per pixel
- Polygons often need CRS conversion to UTM before use
- Large AOIs require post-download resampling or tiling strategies
- NDVI visual appearance can be misleading; numeric validation is critical
- CLMS products require correct band selection and scaling
- Consistent use of `float32` avoids downstream processing issues

### Conceptual
- A “synthesis product” implies temporal logic, not just mosaicking
- NDVI processing is fundamentally a time-series problem
- BYOC is about **registration and access**, not storage or recomputation
- API constraints must be designed around early, not patched later

### Process
- Iterative experimentation with validation beats premature optimization
- Working on locally cached data reduces API load and debugging friction
- Preserving intermediate outputs is essential for EO pipeline development

---

## Status

- ✅ Task 1: Functionally complete (cleanup pending)
- ✅ Task 2: Architecture designed and documented
- 🔧 Next steps (if time allowed):
  - Refactor into unified pipeline
  - Add structured logging
  - Finalize CLI interface
  - Implement minimal automated tests


