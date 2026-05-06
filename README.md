
# hoydedata-python

Python client for downloading and processing elevation data from Norwegian Høydedata services.

## What this library does

- Download DEM rasters for a bounding box from Kartverket's ArcGIS elevation service.
- Automatically split large requests into tiles, merge results, and clean temporary files.
- Extract elevation values for one or many XY points.
- Query metadata and submit export jobs through the laser services endpoints.

## Install

Requirements:

- Python `3.12+`
- `uv` (recommended for this repository workflow)

Install directly from GitHub:

```bash
pip install "git+https://github.com/cgodoyle/hoydedata_python.git"
```

Or with `uv pip`:

```bash
uv pip install "git+https://github.com/cgodoyle/hoydedata_python.git"
```

For local development:

```bash
git clone https://github.com/cgodoyle/hoydedata_python.git

cd hoydedata_python

uv sync --dev
```

Create local environment file:

```bash
cp .env.example .env
```

## Quick start

`hoydedata_python` uses a `src/` layout, so run examples with `uv run` from repository root.

```python
import asyncio

from hoydedata_python import download_elevation_model


async def main() -> None:
    # EPSG:25833 bounds: (xmin, ymin, xmax, ymax)
    bounds = (251091.9498, 7032567.1219, 265107.0872, 7042621.2324)
    await download_elevation_model(
        bounds=bounds,
        resolution_meters=10,
        output_path="./output",  # directory -> writes dem_ndh_10m.tif inside
    )


asyncio.run(main())
```

Run the bundled script:

```bash
uv run python scripts/download_bounds.py
```

## Export client example

Simple flow using `get_metadata` and `send_export_job`:

```python
import geopandas as gpd
from shapely.geometry import box

from hoydedata_python.export_client import get_metadata, send_export_job

# Example polygon in EPSG:25833
polygon = gpd.GeoDataFrame(geometry=[box(251000, 7032000, 252000, 7033000)], crs=25833)

gdf, project_names = get_metadata(polygon=polygon, laser_type=1, crs=25833)

if project_names is not None and len(project_names) > 0:
    response = send_export_job(
        projects_name=project_names[0],  # can also be a list[str]
        polygon=polygon,
        username="YOUR_USERNAME",
        password="YOUR_PASSWORD",
        email="you@example.com",
        name="example-export-job",
    )
    print(response)
```

Notes:

- `send_export_job` requires valid Høydedata credentials.
- `laser_type` in `get_metadata`: `1` laser, `2` image matching, `3` mobile laser, `4` green laser.
- `kartblad` in `send_export_job` must be one of `0`, `1000`, `2000`, `5000`, `10000` (default `2000`).
- Typical workflow: `get_metadata` -> choose project(s) -> `send_export_job` -> read `JobID` from response -> poll `get_export_job_status(JobID)` until `Status` is complete -> download from `Url`.
- Use `get_export_job_status(JobID)` to poll export progress.
- Official API docs (more detail): https://hoydedata.no/LaserInnsyn2/dok/webtjenester.pdf

Minimal polling example:

```python
import time

from hoydedata_python.export_client import get_export_job_status

job_id = response.get("JobID")
if job_id is not None:
    while True:
        status = get_export_job_status(job_id)
        print(status)

        if "Url" in status and status["Url"]:
            print("Download URL:", status["Url"])
            break

        if "Error" in status:
            print("Export error:", status["Error"])
            break

        time.sleep(10)
```

## Public API

Main exports from `hoydedata_python`:

- `download_elevation_model(bounds, resolution_meters, output_path)`
- `download_and_extract_elevation_values_for_points(point_array, resolution_meters=5)`

Additional modules:

- `hoydedata_python.dem_client`: DEM fetch/download/extract flow.
- `hoydedata_python.export_client`: metadata/export job flow.
- `hoydedata_python.raster_processing`: raster merge and clipping utilities.

## Configuration

Settings are loaded with `pydantic-settings` from environment variables and optional `.env` at repo root.

Important:

- Environment variable prefix is `HØYDEDATA_` (with `Ø`).
- Example: `HØYDEDATA_LOG_LEVEL=DEBUG`
- Keep local values in `.env` (gitignored); commit only `.env.example`.

Selected settings (defaults in code):

- `HØYDEDATA_API_URL`
- `HØYDEDATA_API_LAYER`
- `HØYDEDATA_API_TIMEOUT`
- `HØYDEDATA_API_RETRY_ATTEMPTS`
- `HØYDEDATA_ELEVATION_SERVICE_MAX_SIZE`

## Development checks

```bash
uv run ruff check .
uv run ty check
```

Smoke tests (opt-in):

```bash
uv run pytest
uv run pytest --run-smoke -m smoke
```

Real DEM integration test (opt-in, calls external service):

```bash
uv run pytest --run-integration -m integration
```

## Notes and gotchas

- If `output_path` ends in `.tif`, it is treated as a file path.
- Otherwise, `output_path` is treated as a directory and output is named `dem_ndh_{resolution_meters}m.tif`.
- Large requests are auto-tiled when a side exceeds `ELEVATION_SERVICE_MAX_SIZE` pixels.

## License

MIT. See `LICENSE`.
