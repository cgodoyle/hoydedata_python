import json

import geopandas as gpd
import requests

from .config import settings

URL_METADATA = settings.URL_METADATA
URL_EXPORT = settings.URL_EXPORT
URL_STATUS = settings.URL_STATUS


def check_api_status():

    params = {"request": json.dumps({"Filter": "Aarstall=2015"})}

    response = requests.get(URL_METADATA, params=params)
    r_json = response.json()
    if "Error" in r_json.keys():
        return False
    return True


def get_metadata(polygon, laser_type=1, crs=25833, stoponcover=False, min_res=0.5):
    """
    Get the metadata for the Høydedata projects inside a polygon
    check https://hoydedata.no/LaserInnsyn2/dok/webtjenester.pdf for more info

    Parameters
    ----------
    polygon : geopandas.GeoDataFrame
        Polygon to get the metadata from
    laser_type : int, optional
        Type of laser data (1=Laser, 2=Bildematching, 3=Mobil Laser, 4=Grønn laser), by default 1
    crs : int, optional
        Coordinate reference system, by default 25833
    stoponcover : bool, optional
        Select only projects that cover the whole polygon, by default False
    min_res : float, optional
        Minimum resolution of the projects, by default 0.5

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with the metadata and geometries of the projects
    list
        List with the names of the two most recent projects
        TODO: return the two most recent projects from different years
        TODO: slå sammen prosjekter som er fra samme årstall og sjekk om de dekker polygonen

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
    """
    Send a job to export the data from the projects inside a polygon
    check https://hoydedata.no/LaserInnsyn2/dok/webtjenester.pdf for more info

    Parameters
    ----------
    projects_name : str or list
        Name of the projects to export
    polygon : geopandas.GeoDataFrame
        Polygon to query the data and clip the results to
    kartblad : int, optional
        Size of the map sheet (0, 1000, 2000, 5000, 10000), by default 2000 (kartblad 1:2000)
    crs : int, optional
        Coordinate reference system, by default 25833
    email : str, optional
        Email to send the notification
    name : str, optional
        Name of the job, by default "test api"

    Returns
    -------
    dict
        Dictionary with the response from the server. Use JobID to check the status of the job

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
    """
    Get the status of a job

    Parameters
    ----------
    job_id : int
        ID of the job to check

    Returns
    -------
    dict
        Dictionary with the response from the server. Use Status to check the status of the job and Url to download the data

    """
    params = {
        "JobID": job_id,
    }
    response = requests.get(URL_STATUS, params={"request": json.dumps(params)})

    return response.json()
