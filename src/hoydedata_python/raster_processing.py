from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.profiles import Profile
from rasterio.windows import from_bounds, transform
from shapely.geometry import box


def save_raster(
    arr: np.ndarray,
    profile: Profile,
    filename: str,
) -> None:
    """Save a 2D array as a single-band raster.

    Args:
        arr: Raster values to write.
        profile: Rasterio profile used to create output dataset.
        filename: Destination raster path.
    """
    with rasterio.open(filename, "w", **profile) as dst:
        dst.write(arr, 1)


def merge_rasters(
    raster_list: list,
    save_path: str | Path,
) -> None:
    """Merge multiple rasters into one output raster.

    Args:
        raster_list: Paths to rasters to merge.
        save_path: Destination path for merged raster.
    """

    mosaic, transform = merge(raster_list)

    with rasterio.open(raster_list[0]) as src:
        meta = src.meta.copy()  # I don't know why it doesn't work with profile but it does with meta.
    meta.update(
        {
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": transform,
        }
    )
    with rasterio.open(save_path, "w", **meta) as m:
        m.write(mosaic)


def clip_raster_to_extents(
    raster_path: str,
    extents: list | tuple | np.ndarray | gpd.GeoDataFrame,
    output_path: str | Path,
    crs: int = 25833,
) -> None:
    """
    Clip a raster to the given extents and save the result.

    Args:
        raster_path: Path to input raster.
        extents: Clip extents as bounds (`minx, miny, maxx, maxy`) or
            GeoDataFrame geometry.
        output_path: Destination for clipped raster.
        crs: CRS used when `extents` is bounds-like input.
    """
    if isinstance(extents, (list, tuple, np.ndarray)):
        extents = gpd.GeoDataFrame(geometry=[box(*extents)], crs=crs)

    bounds = extents.total_bounds

    with rasterio.open(raster_path) as src:
        window = from_bounds(*bounds, transform=src.transform)
        clipped_data = src.read(window=window)

        # Update transform for the clipped area
        clipped_transform = transform(window, src.transform)

        # Update profile
        profile = src.profile.copy()
        profile.update(
            {"height": clipped_data.shape[1], "width": clipped_data.shape[2], "transform": clipped_transform}
        )

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(clipped_data)
