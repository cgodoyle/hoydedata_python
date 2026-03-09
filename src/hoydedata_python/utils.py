import re
from typing import Union

import geopandas as gpd
from shapely.geometry import box


def clean_url(url: str) -> str:
    """
    Cleans a URL by removing duplicate slashes, except for the protocol part (e.g., "http://").

    Args:
        url (str): The URL to clean.

    Returns:
        str: The cleaned URL with duplicate slashes removed.

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
        bounds (list[float]): A list of bounds in the format [minx, miny, maxx, maxy].
        crs_in (int, optional): The EPSG code of the input CRS. Defaults to 25833.
        crs_out (int, optional): The EPSG code of the output CRS. Defaults to 4326.

    Returns:
        list[float]: A list of transformed bounds in the format [minx, miny, maxx, maxy].
    """
    bbox = gpd.GeoDataFrame(geometry=[box(*bounds)], crs=crs_in).to_crs(crs_out).total_bounds
    return bbox


def split_bbox(
    bbox: Union[gpd.GeoDataFrame, list[float], tuple[float, ...]],
    n_rows: int,
    n_cols: int,
    crs=25833,
) -> gpd.GeoDataFrame:
    """
    Split a bounding box into a grid of smaller boxes.

    Args:
        bbox (Union[gpd.GeoDataFrame, list[float], tuple[float,...]]): The bounding box to split.
        n_rows (int): Number of rows in the grid.
        n_cols (int): Number of columns in the grid.
        crs (int, optional): Coordinate reference system. Defaults to 25833.

    Returns:
        gpd.GeoDataFrame: A GeoDataFrame containing the smaller boxes.
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
        bounds (list or tuple): A list or tuple containing the bounding box coordinates in the format [minx, miny, maxx, maxy].

    Returns:
        float: The area of the bounding box in square kilometers.
    """
    xmin, ymin, xmax, ymax = bounds
    return ((xmax - xmin) / 1000) * ((ymax - ymin) / 1000)
