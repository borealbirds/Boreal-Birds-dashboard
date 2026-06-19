"""
Paths to files and folders located in the app directory and remote server.
"""

from pathlib import Path

import requests

# Paths to folders and files located within the app structure
def app_dir():
    return Path(__file__).parent.parent


def content_dir():
    return app_dir() / "content"


def www_dir():
    return app_dir() / "www"


# Live Posit Connect Cloud dynamic map tiler base domain address
def production_tiler_base():
    return "https://019e4735-507f-07a0-1ae5-b96da68b058b.share.connect.posit.cloud"


# Paths to folders and files located on DRAC
def _remote_url():
    return "https://cloud.borealbirds.ca/"


def dashboard_folder_url():
    return f"{_remote_url()}/dashboard/"


def cog_folder():
    return f"{dashboard_folder_url()}cog_species/"


def predictors_folder():
    return f"{dashboard_folder_url()}Predictors/"


def landbird_v5_results():
    return f"{dashboard_folder_url()}BAMV5-results.xlsx"


def predictor_influence():
    return f"{dashboard_folder_url()}PredictorInfluence.csv"


def species_data_path():
    return f"{dashboard_folder_url()}SpeciesData_Rounded.csv"


def boundaries_path():
    return f"{dashboard_folder_url()}gisdata/Subregions_Mosaics_EPSG4326.shp"


def covariate_metadata():
    return f"{dashboard_folder_url()}covariate_metadata_modelevaluation.csv"


def get_tif_path(species_id: str, region: str, year: int) -> str:
    """
    Construct the remote HTTP target URL path to a Cloud Optimized GeoTIFF from filter inputs.

    Parameters
    ----------
    species_id : str
        The unique alpha-numeric lookup identifier code for the species.
    region : str
        The regional sub-boundary identifier string (e.g., 'Canada', 'Alaska').
    year : int
        The target modeling year parameter.

    Returns
    -------
    str
        The absolute concatenated URL address location pointing to the raster file.
    """

    return f"{cog_folder()}{species_id}/{region}/{species_id}_{region}_{year}.tif"


# assistants
def url_exists(url: str) -> bool:
    """
    Verify the availability of a specific asset URL on the DRAC server.

    Performs a lightweight HEAD request to verify file existence without
    downloading the payload.

    Parameters
    ----------
    url : str
        The full URL string to evaluate.

    Returns
    -------
    bool
        True if the server responds with status code 200, False otherwise.
    """
    try:
        r = requests.head(url, timeout=10)
        return r.status_code == 200
    except Exception:
        return False