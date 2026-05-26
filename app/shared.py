import requests
import polars as pl
from io import BytesIO
import geopandas as gpd
from pathlib import Path
from bs4 import BeautifulSoup
from functools import lru_cache
from urllib.parse import urljoin

app_dir = Path(__file__).parent.parent

REMOTE_DATA_FOLDER = "dashboard/"
BASE_URL = f"http://206.12.92.143/data/{REMOTE_DATA_FOLDER}"
DATA_DIR = app_dir / "data"
V5_META_PATH = DATA_DIR / "model_v5" / "12_BAMV5-results.xlsx"
BOUNDARIES_PATH = DATA_DIR / "boundaries" / "Subregions_Mosaics_EPSG3978.shp"

def get_tif_path(species_id: str, region: str, year: int) -> str:
    """
    Construct the HTTP URL to a specific .tif file.
    """

    filename = f"{species_id}_{region}_{year}.tif"

    return urljoin(
        BASE_URL,
        f"{species_id}/{region}/{filename}"
    )

@lru_cache(maxsize=1)
def load_subregion_boundaries() -> gpd.GeoDataFrame:
    """
    Load and preprocess ecological subregion boundaries for leaflet rendering.

    Returns
    -------
    gpd.GeoDataFrame
        Simplified subregion polygons in EPSG:4326.
    """

    gdf = gpd.read_file(BOUNDARIES_PATH)

    # convert from EPSG:3978 to EPSG:4326
    gdf = gdf.to_crs(epsg=4326)

    # simplify boundaries to load faster
    gdf["geometry"] = gdf.geometry.simplify(0.01)

    return gdf

def load_species_metadata() -> pl.DataFrame:
    """
    Load species taxonomic and descriptive data from the Excel results summary file.

    Returns
    -------
    pl.DataFrame
        A Polars DataFrame containing the 'species' sheet metadata.
    """
    return pl.read_excel(V5_META_PATH, sheet_name="species")

def load_abundance_data() -> pl.DataFrame:
    """
    Load species taxonomic and descriptive data from the Excel results summary file.

    Returns
    -------
    pl.DataFrame
        A Polars DataFrame containing the 'species' sheet metadata.
    """
    return pl.read_excel(V5_META_PATH, sheet_name="abundances")

def load_region_data() -> pl.DataFrame:
    """Load region-level data from the Excel results summary file.

    Returns
    -------
    pl.DataFrame
        A Polars DataFrame containing the 'regions' sheet data.
    """

    regions = pl.read_excel(
    V5_META_PATH,
    sheet_name="regions",
    columns=["region", "type", "country", "name", "area_km2", "total_surveys", "bootstrap_surveys"]
    )

    regions = regions.with_columns(
        (pl.col("name") + " (" + pl.col("region") + ")").alias("name_adj")
    )
    
    return regions

def list_directory(url: str) -> list[str]:
    """
    Parse Apache directory listing and return entries.
    """

    response = requests.get(url, timeout=60)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    entries = []

    for link in soup.find_all("a"):
        href = link.get("href")

        if href not in [None, "../", '/data/', '?C=N;O=D', '?C=M;O=A', '?C=S;O=A', '?C=D;O=A', f'/data/{REMOTE_DATA_FOLDER}']:
            entries.append(href.rstrip("/"))
            continue

    return entries

def species_ids() -> list[str]:
    """
    Scan the data directory for all species with available model results and 
    list available species IDs from remote Apache directory.

    Returns
    -------
    list of str
        Sorted list of species IDs based on existing subdirectories in DATA_DIR.
    """
    try:
        entries = list_directory(BASE_URL)
        return sorted(entries)

    except Exception:
        return []

def available_regions(species_id: str) -> list[str]:
    """
    Identify geographic regions for a specific species and 
    list available regions from remote Apache directory.

    Parameters
    ----------
    species_id : str
        The unique identifier for the species.

    Returns
    -------
    list of str
        Sorted list of region names found within the species' directory.
    """
    species_url = urljoin(BASE_URL, f"{species_id}/")

    try:
        entries = list_directory(species_url)
        return sorted(entries)

    except Exception:
        return []

def available_years(species_id: str, region: str) -> list[int]:
    """
    Parse available model years for a specific species and region by scanning filenames.

    This function looks for .tif files following the naming convention 
    '{species}_{region}_{year}.tif' and extracts the integer year.

    Parameters
    ----------
    species_id : str
        The unique identifier for the species.
    region : str
        The geographic region identifier.

    Returns
    -------
    list of int
        Sorted list of years found for the given parameters.
    """
    region_url = urljoin(
        BASE_URL,
        f"{species_id}/{region}/"
    )

    try:
        entries = list_directory(region_url)

    except Exception:
        return []

    years = []

    prefix = f"{species_id}_{region}_"

    for filename in entries:
        if not filename.endswith(".tif"):
            continue

        stem = filename.removesuffix(".tif")

        if not stem.startswith(prefix):
            continue

        try:
            year = int(stem.removeprefix(prefix))
            years.append(year)

        except ValueError:
            continue

    return sorted(years)