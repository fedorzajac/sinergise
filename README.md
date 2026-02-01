# How to run the code

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

### Proposed Workflow

1. **Data Preparation**
   - Ensure all imagery is in valid COG format
   - Validate CRS, tiling, overviews, and metadata

2. **Metadata Extraction**
   - Extract:
     - Spatial extent (bbox)
     - CRS
     - Acquisition timestamps
     - Band information

3. **Access Configuration**
   - Grant Sentinel Hub read access to private S3 bucket
   - Use signed URLs or IAM-based access

4. **BYOC Collection Creation**
   - Define collection metadata and band schema
   - Create a BYOC collection via Sentinel Hub API

5. **COG Registration**
   - Register individual COG URLs with metadata
   - retry strategy

6. **Indexing and Availability**
   - Sentinel Hub indexes data
   - Data becomes accessible via:
     - Copernicus Browser
     - WMS
     - Process API

7. **Incremental Updates**
   - Register new COGs as they arrive
   - No reprocessing of historical data

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
