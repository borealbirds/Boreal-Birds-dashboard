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

# Remote accessed
REMOTE_DATA_URL = Path("https://cloud.borealbirds.ca/")
REMOTE_DASHBOARD_FOLDER = REMOTE_DATA_URL / "dashboard"


COG_FOLDER = "https://cloud.borealbirds.ca/dashboard/cog_species/"
PREDICTORS_FOLDER = "https://cloud.borealbirds.ca/dashboard/Predictors/"

LANDBIRD_V5_RESULTS = REMOTE_DASHBOARD_FOLDER / "BAMV5-results.xlsx"
V5_META_PATH = "https://cloud.borealbirds.ca/dashboard/BAMV5-results.xlsx"
PREDICTOR_INFLUENCE_PATH = "https://cloud.borealbirds.ca/dashboard/PredictorInfluence.csv"
SPECIES_DATA_PATH = "https://cloud.borealbirds.ca/dashboard/SpeciesData_Rounded.csv"

# old links
REMOTE_DATA_FOLDER = "dashboard/"
# BASE_URL = f"http://206.12.92.143/data/{REMOTE_DATA_FOLDER}"

DATA_DIR = app_dir / "data"
CONTENT_DIR = Path(__file__).parent / "content"


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
        COG_FOLDER,
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