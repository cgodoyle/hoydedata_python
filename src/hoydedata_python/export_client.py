import json

import geopandas as gpd
import requests

from .config import settings

URL_METADATA = settings.URL_METADATA
URL_EXPORT = settings.URL_EXPORT
URL_STATUS = settings.URL_STATUS


def check_api_status():
    """Check whether the metadata endpoint is responding without API error.

    Returns:
        `True` when the service responds without an `Error` field, otherwise
        `False`.
    """

    params = {"request": json.dumps({"Filter": "Aarstall=2015"})}

    response = requests.get(URL_METADATA, params=params)
    r_json = response.json()
    if "Error" in r_json.keys():
        return False
    return True


def get_metadata(polygon, laser_type=1, crs=25833, stoponcover=False, min_res=0.5):
    """Get Høydedata project metadata intersecting a polygon.

    Args:
        polygon: Polygon area of interest as a GeoDataFrame.
        laser_type: Project type filter (`1` laser, `2` image matching,
            `3` mobile laser, `4` green laser).
        crs: EPSG code used for input/output coordinates.
        stoponcover: Request full polygon coverage only when `True`.
        min_res: Maximum accepted project resolution (meters).

    Returns:
        Tuple `(gdf_clipped, name_recent)` where:
        - `gdf_clipped` is a filtered/clipped GeoDataFrame of project metadata.
        - `name_recent` is project-name array sorted by descending year.

        Returns `(None, None)` when no matching projects are found.
    """

    coords = polygon.geometry.get_coordinates().values.tolist()

    params = {
        "Coordinates": "".join([f"{xx:.0f},{yy:.0f};" for xx, yy in coords])[:-1],
        "InputWKID": crs,
        "OutputWKID": crs,
        "ReturnMetadata": "true",
        "ReturnGeometry": "true",
        # "Type": laser_type,
        "StopOnCover": "true" if stoponcover else "false",
    }

    response = requests.get(URL_METADATA, params={"request": json.dumps(params)})

    response.raise_for_status()

    r_json = response.json()

    if "ProjectMetadata" not in r_json.keys():
        print(coords)
        print(r_json)
        print(response.request.url)
        raise ValueError()

    gdf = gpd.GeoDataFrame.from_features(r_json["ProjectMetadata"])
    gdf.crs = crs
    gdf = gdf.query(f"TYPE == '{laser_type}'")
    if len(gdf) == 0:
        print("No projects found! Maybe try stoponcover=False?")
        return None, None

    gdf = gdf[gdf.OPPLOSNING.map(float) <= min_res]

    recent = gdf[["LAS_PROJECT_NAME", "AARSTALL", "OPPLOSNING"]].sort_values("AARSTALL", ascending=False)
    print("The sorted projects are:")
    print(recent)
    name_recent = recent.LAS_PROJECT_NAME.values

    gdf_clipped = gdf.clip(polygon)

    return gdf_clipped, name_recent


def send_export_job(
    projects_name,
    polygon,
    username,
    password,
    kartblad=2000,
    crs=25833,
    email="nn@nn.no",  # this must be filled with a default email ?
    name="test api",
):
    """Submit an export job for selected projects and polygon geometry.

    Args:
        projects_name: Project name or list of project names to export.
        polygon: Polygon used for query and clipping.
        username: Høydedata username.
        password: Høydedata password.
        kartblad: Mapsheet size (`0`, `1000`, `2000`, `5000`, `10000`).
        crs: EPSG code used for coordinate input/output.
        email: Notification email used by the service.
        name: Job label shown in service/job tracking.

    Returns:
        Response dictionary from export service. Use `JobID` with
        `get_export_job_status`.
    """
    assert type(projects_name) in [list, str], "projects_name must be a string or a list of strings"
    assert kartblad in [0, 1000, 2000, 5000, 10000], "kartblad must be 0, 1000, 2000, 5000 or 10000"

    if isinstance(projects_name, list):
        assert all(isinstance(i, str) for i in projects_name), "projects_name must be a string or a list of strings"
        projects_name = "".join([f"{xx}," for xx in projects_name])[:-1]

    coords = polygon.geometry.get_coordinates().values.tolist()
    "".join([f"{xx:.0f},{yy:.0f};" for xx, yy in coords])[:-1]

    params = {
        "Username": username,
        "Password": password,
        "CopyEmail": email,
        "Name": name,
        "CoordInput": "".join([f"{xx:.0f},{yy:.0f};" for xx, yy in coords])[:-1],
        "InputWkid": crs,
        "Format": 5,
        "Resolution": 0,
        "OutputWkid": crs,
        "Projects": projects_name,
        "ProjectProduct": 1,
        "MapsheetSize": kartblad,
        "ClipToPolygon": 1,
    }

    response = requests.get(URL_EXPORT, params={"request": json.dumps(params)})

    r_json = response.json()

    if "Error" in r_json.keys():
        print("Error:")
        print(r_json["Error"])
        print(response.request.url)
    else:
        print("export job sent successfully")

    return r_json


def get_export_job_status(job_id):
    """Get status for a previously submitted export job.

    Args:
        job_id: Export job identifier.

    Returns:
        Response dictionary. Inspect `Status`; use `Url` when ready.
    """
    params = {
        "JobID": job_id,
    }
    response = requests.get(URL_STATUS, params={"request": json.dumps(params)})

    return response.json()
