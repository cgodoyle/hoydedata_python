import asyncio
import logging
import pathlib
from typing import Union

import httpx
import numpy as np
import rasterio
import requests
from rasterio import MemoryFile
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from . import raster_processing, utils
from .config import settings
from .logging import get_module_logger
from .path_utils import ensure_output_directory, validate_and_convert_path

logger = get_module_logger(__name__)

ELEVATION_SERVICE_MAX_SIZE = settings.ELEVATION_SERVICE_MAX_SIZE
crs_default: int = settings.DEFAULT_CRS


def api_retry(
    max_attempts=settings.API_RETRY_ATTEMPTS,
    wait_min=settings.API_RETRY_MIN_WAIT,
    wait_max=settings.API_RETRY_MAX_WAIT,
):
    """Simple retry decorator for API calls"""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
        retry=retry_if_exception_type(
            (
                ConnectionError,
                TimeoutError,
                httpx.ConnectTimeout,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.PoolTimeout,
                httpx.ConnectError,
                httpx.RemoteProtocolError,
            )
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


def _get_query_url():
    return f"{settings.API_URL}/{settings.API_LAYER}/ImageServer/exportImage"


def check_elevation_service_status(timeout_seconds: int = 20) -> bool:
    """
    Check the availability of an ArcGIS elevation service.

    Args:
        service: The elevation data service instance
        timeout_seconds: Timeout for the request in seconds

    Returns:
        bool: True if service is available, False otherwise
    """
    try:
        service_url = _get_query_url().replace("exportImage", "info")
        response = requests.get(service_url, timeout=timeout_seconds)
        response.raise_for_status()
        is_available = True
    except requests.RequestException as e:
        logger.error(f"Error checking service {_get_query_url()}: {e}")
        is_available = False

    status_icon = "✅" if is_available else "❌"
    logger.info(f"Service {_get_query_url()}: {status_icon}")
    return is_available


@api_retry()
async def _make_http_request(
    url: str,
    params: dict,
    timeout_seconds: int,
) -> httpx.Response:
    """
    Helper function that handles HTTP requests with retry logic.

    Args:
        url: The URL to request
        params: URL parameters
        timeout_seconds: Request timeout in seconds

    Returns:
        The HTTP response object

    Raises:
        Various HTTP and connection errors
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=timeout_seconds)
        response.raise_for_status()  # Esto lanzará excepción si status >= 400

    return response


async def fetch_elevation_data(
    bounds: tuple,
    resolution_meters: float = 5,
) -> bytes:
    """
    Fetch digital elevation model data from the høydedata API.

    Args:
        bounds: Bounding box coordinates (xmin, ymin, xmax, ymax)
        resolution_meters: Resolution of the raster in meters

    Returns:
        Raw TIFF data as bytes
    """
    xmin, ymin, xmax, ymax = bounds

    width = int((xmax - xmin) / resolution_meters)
    height = int((ymax - ymin) / resolution_meters)

    params = {
        "bbox": f"{xmin},{ymin},{xmax},{ymax}",
        "size": f"{width},{height}",
        "bboxSR": f"{settings.DEFAULT_CRS}",
        "imageSR": f"{settings.DEFAULT_CRS}",
        "time": "",
        "format": "tiff",
        "pixelType": "F32",
        "noData": "",  # Empty to avoid issues with some requests
        "noDataInterpretation": "esriNoDataMatchAny",
        "interpolation": "RSP_BilinearInterpolation",
        "compression": "",
        "compressionQuality": "",
        "bandIds": "",
        "mosaicRule": "",
        "renderingRule": "",
        "f": "image",
    }
    response = await _make_http_request(_get_query_url(), params, timeout_seconds=settings.API_TIMEOUT)

    return response.content


def convert_tiff_bytes_to_raster(tiff_bytes: bytes) -> tuple[np.ndarray, dict]:
    """
    Convert TIFF bytes to a raster array and profile.

    Args:
        tiff_bytes: Raw TIFF data as bytes

    Returns:
        Tuple containing:
        - elevation_array: numpy array with elevation values
        - raster_profile: rasterio profile dictionary
    """
    try:
        with MemoryFile(tiff_bytes) as memfile:
            with memfile.open() as dataset:
                elevation_array = dataset.read(1)
                raster_profile = dataset.profile

    except rasterio.errors.RasterioIOError as e:
        raise e

    return elevation_array, raster_profile


async def fetch_and_save_elevation_tile(
    output_filename: Union[str, pathlib.Path],
    bounds: tuple,
    resolution_meters: float = 5,
) -> None:
    """
    Fetch elevation data and save it as a TIFF file.

    Args:
        output_filename: Path where the TIFF file will be saved (string or Path)
        bounds: Bounding box coordinates (xmin, ymin, xmax, ymax)
        resolution_meters: Resolution in meters
    """
    # Validate and convert path
    output_path = validate_and_convert_path(output_filename)

    # Ensure output directory exists
    ensure_output_directory(output_path)

    tiff_bytes = await fetch_elevation_data(bounds, resolution_meters)
    elevation_array, raster_profile = convert_tiff_bytes_to_raster(tiff_bytes)

    with rasterio.open(output_path, "w+", **raster_profile) as dst:
        dst.write(elevation_array, 1)


def _check_request_size_limits(
    bounds: tuple,
    resolution_meters: float,
) -> bool:
    """
    Check if the request size is within service limits.

    Args:
        bounds: Bounding box coordinates (xmin, ymin, xmax, ymax)
        resolution_meters: Resolution in meters

    Returns:
        True if within limits, False if too large
    """
    xmin, ymin, xmax, ymax = bounds
    width_pixels = (xmax - xmin) / resolution_meters
    height_pixels = (ymax - ymin) / resolution_meters

    return width_pixels <= ELEVATION_SERVICE_MAX_SIZE and height_pixels <= ELEVATION_SERVICE_MAX_SIZE


@api_retry()
async def download_elevation_model(
    bounds: tuple,
    resolution_meters: float,
    output_path: Union[str, pathlib.Path],
) -> None:
    """
    Download a digital elevation model (DEM) raster file from the Norwegian Mapping Authority (Kartverket) API.

    Args:
        bounds: The bounding box coordinates (xmin, ymin, xmax, ymax) of the area of interest
        resolution_meters: The resolution of the DEM in meters
        output_path: The output file path for the downloaded DEM (string or Path)

    Returns:
        None: The downloaded DEM is saved to the specified file
    """
    xmin, ymin, xmax, ymax = bounds

    # Validate and convert path
    validated_output_path = validate_and_convert_path(output_path)

    # Determine output directory and file
    output_dir = ensure_output_directory(validated_output_path)

    logger.info(f"Downloading DEM to {validated_output_path} with resolution {resolution_meters}m for bounds {bounds}")

    if validated_output_path.suffix == ".tif":
        dem_file = validated_output_path
    else:
        dem_file = output_dir / f"dem_ndh_{resolution_meters}m.tif"

    if _check_request_size_limits(bounds, resolution_meters):
        logger.info("Downloading DEM...")
        await fetch_and_save_elevation_tile(dem_file, bounds, resolution_meters)
    else:
        logger.warning("Extent is too large, downloading tiles and merging...")
        max_tile_size = ELEVATION_SERVICE_MAX_SIZE * resolution_meters
        x_tiles = np.ceil((xmax - xmin) / max_tile_size).astype(int)
        y_tiles = np.ceil((ymax - ymin) / max_tile_size).astype(int)
        tile_grid = utils.split_bbox(bounds, y_tiles, x_tiles)

        # Control concurrency to avoid overwhelming the server
        max_concurrent_requests = 3
        semaphore = asyncio.Semaphore(max_concurrent_requests)

        async def download_tile_with_concurrency_control(filename, tile_bounds, resolution):
            """Download single tile with concurrency control"""
            async with semaphore:
                try:
                    await fetch_and_save_elevation_tile(filename, tile_bounds, resolution)
                    logger.info(f"✅ Downloaded: {filename.name}")
                    return filename
                except Exception as e:
                    logger.error(f"❌ Failed to download {filename.name}: {e}")
                    return None

        # Create download tasks with concurrency control
        download_tasks = [
            download_tile_with_concurrency_control(
                output_dir / f"dem_ndh_{resolution_meters}m_tile_{tile.id}.tif",  # ty:ignore[unresolved-attribute]
                tile.geometry.bounds,  # ty:ignore[unresolved-attribute]
                resolution_meters,
            )
            for tile in tile_grid.itertuples()
        ]

        # Execute all tasks asynchronously with progress tracking
        completed_tiles = []
        total_tiles = len(download_tasks)

        for i, completed_task in enumerate(asyncio.as_completed(download_tasks)):
            result = await completed_task
            if result:  # Successfully downloaded
                completed_tiles.append(result)

            # Progress tracking
            logger.info(f"Progress: {i + 1}/{total_tiles} tiles processed")

        # Verify that at least some tiles were downloaded
        if not completed_tiles:
            raise RuntimeError("Failed to download any tiles")

        if len(completed_tiles) < total_tiles:
            logger.warning(f"Only {len(completed_tiles)}/{total_tiles} tiles downloaded successfully")

        tile_file_list = [
            output_dir / f"dem_ndh_{resolution_meters}m_tile_{tile.id}.tif"  # ty:ignore[unresolved-attribute]
            for tile in tile_grid.itertuples()
        ]

        raster_processing.merge_rasters(tile_file_list, dem_file)
        for tile_file in tile_file_list:
            if tile_file.exists():
                tile_file.unlink()
    logger.info(f"Done! Results saved at {dem_file}")


def extract_elevation_values_for_points(point_array: np.ndarray, elevation_array, raster_profile) -> np.ndarray:

    if point_array.shape == (2,):
        points_xy = np.expand_dims(point_array, 0)
    else:
        points_xy = point_array.copy()

    transform = raster_profile["transform"]
    height, width = elevation_array.shape

    # Convert coordinates to pixel indices
    pixel_indices = np.array([rasterio.transform.rowcol(transform, point[0], point[1]) for point in points_xy])
    pixel_indices = np.array(
        [xx for xx in pixel_indices if (xx[0] >= 0 and xx[0] < height) and (xx[1] >= 0 and xx[1] < width)]
    )
    if len(pixel_indices) == 0:
        return np.array([])
    elevation_values = np.array([elevation_array[idx[0], idx[1]] for idx in pixel_indices])

    return elevation_values


async def download_and_extract_elevation_values_for_points(
    point_array: np.ndarray, resolution_meters: int = 5
) -> np.ndarray:
    """
    Extract elevation values for given x,y coordinates.

    Args:
        point_array: numpy array with x,y coordinates
        resolution_meters: Resolution for elevation data in meters

    Returns:
        numpy array with elevation values (z coordinates)
    """
    if point_array.shape == (2,):
        points_xy = np.expand_dims(point_array, 0)
    else:
        points_xy = point_array.copy()

    xmin, ymin = points_xy.min(axis=0) - 10  # small buffer
    xmax, ymax = points_xy.max(axis=0) + 10  # small buffer

    tiff_bytes = await fetch_elevation_data((xmin, ymin, xmax, ymax), resolution_meters=resolution_meters)
    elevation_array, raster_profile = convert_tiff_bytes_to_raster(tiff_bytes)
    transform = raster_profile["transform"]

    # Convert coordinates to pixel indices
    pixel_indices = np.array([rasterio.transform.rowcol(transform, point[0], point[1]) for point in points_xy])
    elevation_values = np.array([elevation_array[idx[0], idx[1]] for idx in pixel_indices])

    return elevation_values
