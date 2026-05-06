import re

import geopandas as gpd
from shapely.geometry import box


def clean_url(url: str) -> str:
    """Remove duplicate slashes from a URL while preserving protocol.

    Args:
        url: URL to normalize.

    Returns:
        URL string with duplicate path slashes removed.
    """
    cleaned_url = re.sub(r"(?<!:)/{2,}", "/", url)
    return cleaned_url


def transform_bounds(
    bounds: list[float],
    crs_in: int = 25833,
    crs_out: int = 4386,
) -> list[float]:
    """
    Transforms bounds from one CRS to another.

    Args:
        bounds: Bounds as `[minx, miny, maxx, maxy]`.
        crs_in: EPSG code of input CRS.
        crs_out: EPSG code of output CRS.

    Returns:
        Transformed bounds `[minx, miny, maxx, maxy]`.
    """
    bbox = gpd.GeoDataFrame(geometry=[box(*bounds)], crs=crs_in).to_crs(crs_out).total_bounds
    return bbox


def split_bbox(
    bbox: gpd.GeoDataFrame | list[float] | tuple[float, ...],
    n_rows: int,
    n_cols: int,
    crs=25833,
) -> gpd.GeoDataFrame:
    """
    Split a bounding box into a grid of smaller boxes.

    Args:
        bbox: Bounding box as GeoDataFrame or bounds tuple/list.
        n_rows: Number of grid rows.
        n_cols: Number of grid columns.
        crs: Coordinate reference system (EPSG).

    Returns:
        GeoDataFrame containing all generated sub-boxes and `id`.
    """
    if isinstance(bbox, (list, tuple)):
        minx, miny, maxx, maxy = bbox
    elif isinstance(bbox, gpd.GeoDataFrame):
        minx, miny, maxx, maxy = bbox.total_bounds
        if bbox.crs.to_epsg() != crs:
            bbox = bbox.to_crs(crs)
    else:
        raise TypeError("Invalid bbox type")
    n_rows = int(n_rows)
    n_cols = int(n_cols)
    width = (maxx - minx) / n_cols
    height = (maxy - miny) / n_rows
    sub_boxes = []
    for i in range(n_cols):
        for j in range(n_rows):
            sub_minx = minx + i * width
            sub_miny = miny + j * height
            sub_maxx = sub_minx + width
            sub_maxy = sub_miny + height
            sub_boxes.append(box(sub_minx, sub_miny, sub_maxx, sub_maxy))
    subgrid = gpd.GeoDataFrame(geometry=sub_boxes, crs=crs)
    subgrid["id"] = range(1, len(subgrid) + 1)
    return subgrid


def bounds_area(bounds: list[float] | tuple[float, ...]) -> float:
    """
    Calculate the area of a bounding box in square kilometers.

    Args:
        bounds: Bounding box coordinates `[minx, miny, maxx, maxy]`.

    Returns:
        Area in square kilometers.
    """
    xmin, ymin, xmax, ymax = bounds
    return ((xmax - xmin) / 1000) * ((ymax - ymin) / 1000)
