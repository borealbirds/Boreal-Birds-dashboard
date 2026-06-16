"""
Data access layer for the BAM dashboard backend.

Orchestrates data flow between remote data servers, the TiTiler mapping 
gateway, and local disk-backed fallback caches for rasters and tabular files.

Main Capabilities
-----------------
* Monitors the dynamic cloud raster tiler API health status.
* Resolves HTTP URLs for remote Cloud Optimized GeoTIFFs (COGs).
* Extracts and aggregates data tables efficiently using Polars.
* Parses Apache directory listings to scan for available assets.

Notes
-----
All tabular data workflows utilize the high-performance `polars` engine.
"""
import requests
import polars as pl
from io import BytesIO
import geopandas as gpd
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import yaml
import time


app_dir = Path(__file__).parent.parent

# Live Posit Connect Cloud dynamic map tiler base domain address
PRODUCTION_TILER_BASE = "https://019e4735-507f-07a0-1ae5-b96da68b058b.share.connect.posit.cloud"

REMOTE_DATA_FOLDER = "dashboard/"
BASE_URL = f"http://206.12.92.143/data/{REMOTE_DATA_FOLDER}"
DATA_DIR = app_dir / "data"
CONTENT_DIR = Path(__file__).parent / "content"
V5_META_PATH = DATA_DIR / "model_v5" / "12_BAMV5-results.xlsx"
# change V5_META_PATH to the following after the file get uploads to DRAC
# V5_META_PATH = f"http://206.12.92.143/data/12_BAMV5-results.xlsx" 
BOUNDARIES_PATH = DATA_DIR / "boundaries" / "Subregions_Mosaics_EPSG3978.shp"
COVARIATE_MTDATA = DATA_DIR / "model_v5" / "covariate_metadata_modelevaluation - covariates_label.csv"
MARGINAL_FX_DIR = DATA_DIR / "model_v5" / "marginaleffects"

# cache to check titiler API health status
TILER_HEALTH_TTL = 30
_tiler_health_cache = {
    "timestamp": 0,
    "healthy": False
}

def tiler_is_healthy() -> bool:
    """
    Check the health status of the remote TiTiler API gateway.

    Uses a basic Time-To-Live (TTL) caching mechanism to prevent spamming
    the health endpoint on rapid UI reactive invalidations.

    Returns
    -------
    bool
        True if the tiler endpoint responds with a status code of 200 and an
        'ok' status payload, False otherwise.

    Notes
    -------
    The cache state is managed globally by the `_tiler_health_cache` dictionary
    using the window duration defined in `TILER_HEALTH_TTL`.
    """
    now = time.time()

    if now - _tiler_health_cache["timestamp"] < TILER_HEALTH_TTL:
        return _tiler_health_cache["healthy"]

    try:
        r = requests.get(
            f"{PRODUCTION_TILER_BASE}/health",
            timeout=3
        )

        healthy = (
            r.status_code == 200 and
            r.json().get("status") == "ok"
        )

    except Exception:
        healthy = False

    _tiler_health_cache["healthy"] = healthy
    _tiler_health_cache["timestamp"] = now

    return healthy

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

    filename = f"{species_id}_{region}_{year}.tif"

    return urljoin(
        BASE_URL,
        f"{species_id}/{region}/{filename}"
    )

def get_cov_fx_data(covs: list) -> pl.DataFrame:
    """
    Extract and assemble regional marginal effect datasets across target covariates.

    Reads separate flat tables across multiple parameter directories and combines
    them into a unified structural representation.

    Parameters
    ----------
    covs : list of str
        The covariate variable collection subdirectory names to extract.

    Returns
    -------
    pl.DataFrame
        A Polars DataFrame containing combined parameters for all selected variables.
    """
    
    filePath = MARGINAL_FX_DIR / covs[0] / "marginalsv5.csv"
    
    df =  pl.read_csv(filePath)

    if len(covs) > 1:
        for i in range(1,len(covs)):
            filePath_1 = MARGINAL_FX_DIR / covs[i] / "marginalsv5.csv"
            df_1 = pl.read_csv(filePath_1)
            df = df.vstack(df_1).rechunk()
    
    return df

def load_species_metadata() -> pl.DataFrame:
    """
    Load species taxonomic and descriptive data from the Excel results summary file.

    - lists the species for which results are available
        - id:                   AOU code for the species
        - scientific:           scientific name for the species
        - english:              common name for the species in English
        - french:               common name for the species in French
        - family:               family for the species

    Returns
    -------
    pl.DataFrame
        A Polars DataFrame containing the 'species' sheet metadata.
    """
    return pl.read_excel(V5_META_PATH, sheet_name="species")

def load_covariate_metadata() -> pl.DataFrame:
    """
    Load Covariate metadata and full-form names from the csv file.

    Returns
    -------
    pl.DataFrame
        A Polars DataFrame containing the Covariate metadata.
    """
    return pl.read_csv(COVARIATE_MTDATA)

def load_abundance_data() -> pl.DataFrame:
    """
    Load population density estimates from the Excel results summary file.

    - species specific population size (million males) and density estimates (males / ha) by region (density = abundance / area)
        - id:                   AOU code for the species
        - scientific:           scientific name for the species
        - english:              common name for the species in English
        - region:               modelling region
        - year:                 year of prediction, determined by year of covariate prediction layers used
        - population_estimate:  mean population estimate
        - population_lower:     5th percentile of 32 bootstrap population estimate
        - population_upper:     95th percentile of 32 bootstrap population estimate
        - density_estimate:     mean density estimate
        - density_lower:        5th percentile of 32 bootstrap density estimate
        - density_upper:        5th percentile of 32 bootstrap density estimate

    Returns
    -------
    pl.DataFrame
        A Polars DataFrame containing the 'abundances' sheet metadata.
    """
    return pl.read_excel(V5_META_PATH, sheet_name="abundances")

def load_region_data() -> pl.DataFrame:
    """
    Load region data from the Excel results summary file.
    
    - lists the individual modelling regions and the mosaiced model regions
        - region:               code for the region (country and bird conservation region number for single model regions)
        - type:                 type of model region (single model vs mosaic of multiple single models)
        - country:              country of the region
        - bcr:                  Bird conservation region (BCR) name
        - area_km2:             area of the region (km2)
        - total_surveys:        total surveys available for the modelling region (including 100km buffer)
        - bootstrap_surveys:    total surveys used for model training per bootsstrap (including 100 km buffer)

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
    Scrape and extract valid paths from DRAC server directory listing.

    Requests index endpoints and ignores structural navigation entries, 
    query filter strings, or top-level relative assets.

    Parameters
    ----------
    url : str
        The remote directory link listing resource locations.

    Returns
    -------
    list of str
        Cleaned asset filenames or subdirectory names discovered in the catalog.
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
    Scan the remote repository index to isolate available species IDs.

    Returns
    -------
    list of str
        Sorted list of species IDs based on existing subdirectories.
        Returns an empty list if remote catalog requests fail.
    """
    try:
        entries = list_directory(BASE_URL)
        return sorted(entries)

    except Exception:
        return []

def available_regions(species_id: str) -> list[str]:
    """
    Identify geographic regions for a specific species and 
    list available regions from remote directory.
    
    Falling back to local directories if the remote server is offline.

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
        if entries:
            return sorted(entries)
    except Exception as e:
        print(f"[available_regions] Remote unavailable for {species_id}: {e}")

    # Local fallback — scan data/model_v5/{species_id}/
    local_dir = DATA_DIR / "model_v5" / species_id
    if local_dir.exists():
        regions = sorted([d.name for d in local_dir.iterdir() if d.is_dir()])
        if regions:
            print(f"[available_regions] Using local data for {species_id}: {regions}")
            return regions

    print(f"[available_regions] No data found for {species_id}")
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
    region_url = urljoin(BASE_URL, f"{species_id}/{region}/")

    try:
        entries = list_directory(region_url)
        years = []
        prefix = f"{species_id}_{region}_"
        for filename in entries:
            if not filename.endswith(".tif"):
                continue
            stem = filename.removesuffix(".tif")
            if not stem.startswith(prefix):
                continue
            try:
                years.append(int(stem.removeprefix(prefix)))
            except ValueError:
                continue
        if years:
            return sorted(years)
    except Exception as e:
        print(f"[available_years] Remote unavailable for {species_id}/{region}: {e}")

    # Local fallback — scan data/model_v5/{species_id}/{region}/
    local_dir = DATA_DIR / "model_v5" / species_id / region
    if local_dir.exists():
        years = []
        prefix = f"{species_id}_{region}_"
        for tif in local_dir.glob("*.tif"):
            stem = tif.stem
            if not stem.startswith(prefix):
                continue
            try:
                years.append(int(stem.removeprefix(prefix)))
            except ValueError:
                continue
        if years:
            print(f"[available_years] Using local data for {species_id}/{region}: {sorted(years)}")
            return sorted(years)

    print(f"[available_years] No years found for {species_id}/{region}")
    return []

def read_md(filename) -> str:
    """
    Extract raw text contents out of a localized target Markdown document.

    Parameters
    ----------
    filename : str
        The name of the target file stored under `CONTENT_DIR`.

    Returns
    -------
    str
        The unparsed text content block encoded via UTF-8 rules.
    """
    path = CONTENT_DIR / filename
    return path.read_text(encoding="utf-8")

def read_yaml(filename) -> dict:
    """
    Load and parse a localized target YAML configuration layout file.

    Parameters
    ----------
    filename : str
        The name of the configuration asset stored under `CONTENT_DIR`.

    Returns
    -------
    dict
        A dictionary representation of the parsed YAML document structure.
    """
    path = CONTENT_DIR / filename
    return yaml.safe_load(path.read_text(encoding="utf-8"))