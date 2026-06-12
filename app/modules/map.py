"""
Map related helper functions
"""
import geopandas as gpd
from shared import BOUNDARIES_PATH, load_region_data
from functools import lru_cache
from shapely.geometry import shape
import json
from ipyleaflet import GeoJSON, WidgetControl
from ipywidgets import HTML, Layout

# Hardcoded fallback center metrics for geographic bounding contexts
REGION_CENTERS = {
    "Alaska": [64, -149],
    "Canada": [58, -103],
    "Lower48": [47.0, -97.0]
}

REGION_DICT = load_region_data().rows_by_key(key="region", named=True, unique=True)

def _get_map_error_html(status: str) -> HTML:
    """Return appropriate fallback HTML widgets for tiler states."""
    messages = {
        "tiler_unavailable": ("Map service starting", "The raster tiling service (Titiler API) is currently unavailable. Please try again in a few minutes."),
        "tiler_starting": ("Loading raster", "Initializing selected raster."),
        "missing": ("Raster unavailable", "The requested raster file could not be found."),
        "loading": ("Loading Raster ...", "")
    }
    title, body = messages.get(status, ("Error", "An unexpected status occurred."))
    return HTML(f"""
        <div style="padding:20px">
            <h4>{title}</h4>
            {"<p>" + body + "</p>" if body else ""}
        </div>
    """)

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
    gdf["geometry"] = gdf.geometry.simplify(0.001)

    return gdf

subregions = load_subregion_boundaries()

def get_region_gdf(region: str):
    gdf = subregions
    alaska_bcr = ["usa2", "usa41423", "usa43", "usa40", "usa5"]

    if region == "Canada":
        return gdf[gdf["bcr"].str.startswith("can")]

    if region == "Lower48":
        return gdf[
            gdf["bcr"].str.startswith("usa") &
            ~gdf["bcr"].isin(alaska_bcr)
        ]

    if region == "Alaska":
        return gdf[gdf["bcr"].isin(alaska_bcr)]

    return gdf

def build_region_layer(region_name: str):

    region_gdf = get_region_gdf(region_name)

    geojson_data = json.loads(
        region_gdf.to_json(drop_id=True)
    )

    # precompute zoom/centering for each feature
    for feature in geojson_data["features"]:

        geom = shape(feature["geometry"])
        minx, miny, maxx, maxy = geom.bounds

        # center of each bcr
        cx, cy = geom.centroid.x, geom.centroid.y

        feature["properties"]["_center"] = [cy, cx]
        feature["properties"]["_bounds"] = [[miny, minx], [maxy, maxx]]

        spanx = maxx - minx
        spany = maxy - miny
        feature["properties"]["_spanx"] = spanx
        feature["properties"]["_spany"] = spany

    layer = GeoJSON(
        data=geojson_data,
        style={
            "color": "black",
            "weight": 1.25,
            "fillColor": "white", 
            "fillOpacity": 0, 
            "opacity": 0.2,
        },
        hover_style={
            "color": "#00FFFF",
            "weight": 3,
            "fillColor": "white", 
            "fillOpacity": 0, 
            "opacity": 1, 
        },
        name="Subregion Boundaries"
    )

    # floating info card
    hover_card = HTML(
        value="""
        <div style="
            padding:8px 10px;
            background:white;
            border-radius:6px;
            box-shadow:0 1px 4px rgba(0,0,0,0.25);
            font-size:13px;
            min-width:140px;
        ">
            Hover over a subregion
        </div>
        """,
        layout=Layout(margin="0px")
    )

    hover_control = WidgetControl(
        widget=hover_card,
        position="bottomleft"
    )

    return layer, hover_card, hover_control

def zoom_from_span(span_x, span_y):
    if not span_x or not span_y:
        return 4
    # map height / map width (roughly)
    aspect = 4 / 9
    # normalize vertical span into width-equivalent span
    span_y_normalized = span_y / aspect
    span = max(span_x, span_y_normalized)

    if span > 30:
        zoom = 4.2
    elif span > 25:
        zoom = 4.5
    elif span > 23:
        zoom = 4.7
    elif span > 16:
        zoom = 5.2
    elif span > 10:
        zoom = 5.5
    elif span > 8:
        zoom = 6
    else:
        zoom = 6.5
    print("\n\nspan ", span, " zoom ", zoom)
    return zoom