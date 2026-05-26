from shiny import Inputs, reactive, ui, render
from shinywidgets import render_widget, output_widget, render_altair
from ipywidgets import HTML
from ipyleaflet import (
    Map, basemaps, TileLayer, GeoData,
    basemap_to_tiles, LayersControl, ScaleControl,
    FullScreenControl, WidgetControl, GeoJSON
)

import json
import altair as alt
import requests
import polars as pl
import geopandas as gpd
from functools import lru_cache

from shared import (
    get_tif_path,
    available_regions,
    available_years,
    load_species_metadata,
    load_abundance_data,
    load_subregion_boundaries,
    load_region_data
)
from modules.bird import bird_card

import warnings
import numpy as np

warnings.filterwarnings(
    "ignore",
    category=RuntimeWarning,
    module="numpy.ma.core"
)

birds = load_species_metadata()
abundances = load_abundance_data()
subregions = load_subregion_boundaries()
region_dict = load_region_data().rows_by_key(key="region", named=True, unique=True)


# Live Posit Connect Cloud dynamic map tiler base domain address
PRODUCTION_TILER_BASE = "https://019e4735-507f-07a0-1ae5-b96da68b058b.share.connect.posit.cloud"

# Hardcoded fallback center metrics for geographic bounding contexts
REGION_CENTERS = {
    "Alaska": [64, -149],
    "Canada": [55, -106],
    "Lower48": [47.0, -97.0]
}

def url_exists(url: str) -> bool:
    """
    Ensure url for the file exists in the data host server
    """
    try:
        r = requests.head(url, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

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

    # for feature in geojson_data["features"]:

    #     props = feature["properties"]

    #     feature["properties"]["tooltip"] = (
    #         "<div style='font-size:13px;'>"
    #         f"<b>Country:</b> {props.get('country', 'Unknown')}<br>"
    #         f"<b>BCR:</b> {props.get('bcr', 'Unknown')}"
    #         "</div>"
    #     )

    layer = GeoJSON(
        data=geojson_data,
        style={
            "color": "white",
            "weight": 1.5,
            "fillColor": "white",
            "fillOpacity": 0.05,
            "opacity": 0.7,
        },
        hover_style={
            "color": "#00FFFF",
            "weight": 3,
            "fillColor": "#00FFFF",
            "fillOpacity": 0.20,
        },
        name=f"Subregion Boundaries"
    )

    return layer

def server_v5(input: Inputs):
    """
    Main server logic for the Model V5 tab, managing reactive data flow 
    and spatial visualization.
    """

    @render.ui
    def selected_bird():
        bird = birds.filter(pl.col("english") == input.species_v5())

        pop_dict = (
            population_data()
            .filter(pl.col("region").is_in(["Canada", "Alaska", "Lower48"]))
            .select(["region", "population_estimate"])
            .rows_by_key(key="region", named=True, unique=True)
        )

        canada = pop_dict.get("Canada", {}).get("population_estimate", "No Model Estimates")
        alaska = pop_dict.get("Alaska", {}).get("population_estimate", "No Model Estimates")
        lower48 = pop_dict.get("Lower48", {}).get("population_estimate", "No Model Estimates")

        return bird_card(
            species=bird.item(0, "scientific"),
            common_name=bird.item(0, "english"),
            french_name=bird.item(0, "french"),
            family=bird.item(0, "family"),
            image_url=f"img/{bird.item(0, "id")}.jpg",
            canada_pop=canada,
            alaska_pop=alaska,
            lower48_pop=lower48
        )

    @reactive.effect
    def _update_regions():
        """Update the region dropdown choices dynamically based on species availability."""
        species_id = birds.filter(pl.col("english") == input.species_v5()).item(0, "id")

        if not species_id:
            ui.update_select("region_v5", choices=[], selected=None)
            return

        regions = available_regions(species_id)

        ui.update_select(
            "region_v5",
            choices=regions,
            selected=regions[0] if regions else None,
        )

    @reactive.effect
    def _update_year_range():
        """Update the slider range and default value based on available temporal data."""
        species_id = birds.filter(pl.col("english") == input.species_v5()).item(0, "id")
        region = input.region_v5()

        if not species_id or not region:
            return

        years = available_years(species_id, region)

        if not years:
            return

        ui.update_slider(
            "year_v5",
            min=min(years),
            max=max(years),
            value=max(years),
        )
    
    @reactive.calc
    def file_url():
        """Construct the remote URL string path for the selected raster."""
        species_id = birds.filter(
            pl.col("english") == input.species_v5()
        ).item(0, "id")

        region = input.region_v5()
        year = input.year_v5()

        if not species_id or not region or not year:
            return None

        return get_tif_path(species_id, region, int(year))

    @reactive.calc
    def raster_statistics():
        """Query min/max data statistics remotely using the TiTiler metadata API."""
        url = file_url()
        if not url or not url_exists(url):
            return {"min": 0.0, "max": 1.0}
            
        try:
            encoded_cog = requests.utils.quote(url, safe="")
            # Query the statistics endpoint exposed by the tiler
            stats_url = f"{PRODUCTION_TILER_BASE}/cog/statistics?url={encoded_cog}"
            res = requests.get(stats_url, timeout=5).json()
            
            band_key = list(res.keys())[0] if res else None
            if band_key:
                band_stats = res[band_key]
                return {
                    "min": float(band_stats.get("min", 0.0)),
                    "max": float(band_stats.get("max", 1.0))
                }
            return {"min": 0.0, "max": 1.0}
        except Exception as e:
            print(f"Error fetching TiTiler statistics: {e}")
            return {"min": 0.0, "max": 1.0}

    REGION_LAYERS = {
        "Canada": build_region_layer("Canada"),
        "Lower48": build_region_layer("Lower48"),
        "Alaska": build_region_layer("Alaska"),
    }

    @render_widget
    def map_widget():
        """Generate the interactive map widget leveraging the remote cloud tiler engine."""
        url = file_url()

        if not url:
            return HTML("<p>Loading / No data available</p>")

        if not url_exists(url):
            return HTML("<p>Raster not found on data server</p>")

        encoded_cog = requests.utils.quote(url, safe="")
        
        # center on the selected region
        map_center = REGION_CENTERS.get(input.region_v5(), [60.0, -110.0])

        # Basemaps
        positron = basemap_to_tiles(basemaps.CartoDB.Positron)
        positron.base = True
        positron.name = "Positron (minimal)"
        
        osm = basemap_to_tiles(basemaps.OpenStreetMap.Mapnik)
        osm.base = True
        osm.name = "Open Street Map (default)"
        
        esri = basemap_to_tiles(basemap=basemaps.Esri.WorldImagery)
        esri.base = True
        esri.name = "World Imagery (satellite)"

        # Initialize core map interface
        m = Map(layers=[esri, positron, osm], center=map_center, zoom=4)

        # generate legend utilizing remote data calculations
        stats = raster_statistics()
        rmin = stats["min"]
        rmax = stats["max"]

        legend = WidgetControl(
            widget=HTML(f"""
            <div class="map-legend">
                <div class="map-legend-title">
                    <b>{rmin:.4f} → {rmax:.4f}</b>
                </div>
                <div class="map-legend-gradient"></div>
            </div>
            """),
            position="bottomright"
        )

        # request tiles from the titiler API gateway
        tile_string = (
            f"{PRODUCTION_TILER_BASE}"
            f"/cog/tiles/{{z}}/{{x}}/{{y}}.png"
            f"?url={encoded_cog}"
            f"&colormap_name=ylgn"
            f"&rescale={rmin},{rmax}"
        )
        
        mean_density = TileLayer(
            url=tile_string,
            name="Mean Density",
        )

        m.add(mean_density)
        m.add(legend)

        region = input.region_v5()

        if region == "Canada":
            m.add(REGION_LAYERS["Canada"])

        elif region == "Lower48":
            m.add(REGION_LAYERS["Lower48"])

        elif region == "Alaska":
            m.add(REGION_LAYERS["Alaska"])

        # controls
        m.add(FullScreenControl())
        m.add(LayersControl(collapsed=False, position="topright"))
        m.add(ScaleControl(position="bottomleft"))

        return m
    
    @reactive.calc
    def population_data():
        return abundances.filter(
            (pl.col("english") == input.species_v5())
        )

    @render.data_frame
    def population_size():
        df = population_data()

        df = df.select([
            "year",
            "region", 
            "population_estimate", 
            "population_lower", 
            "population_upper", 
            "density_estimate", 
            "density_lower", 
            "density_upper"
        ])

        return render.DataGrid(df, selection_mode="rows")

    @render_altair
    def population_chart():

        df = population_data()

        points = alt.Chart(df).mark_point(
            filled=True,
        ).encode(
            alt.X("population_estimate:Q")
                .title("Abundance (M males)")
                .scale(type="log"),
            alt.Y("region_name:N")
                .title(None)
                .sort(
                    field="population_estimate",
                    order="descending",
                )
                .axis(labelLimit=0),
            alt.Color(
                "country_name:N",
                legend=alt.Legend(title="Country")
            ),
        ).transform_calculate(
            region_name=f"{region_dict}[datum.region].name_adj",
            country_name=f"{region_dict}[datum.region].country"
        )

        nearest = alt.selection_point(
            nearest=True,
            on="pointerover",
            fields=["population_estimate"],
            empty=False
        )
        when_near = alt.when(nearest)

        highlight = points.mark_point(
            size=50,
            stroke="#153B40FF",
        ).encode(
            opacity=when_near.then(alt.value(1)).otherwise(alt.value(0))
        )

        rules = alt.Chart(df).mark_rule(
            color="#153B40FF",
        ).encode(
            x="population_estimate:Q",
            opacity=alt.when(nearest)
                .then(alt.value(0.5))
                .otherwise(alt.value(0)),
            tooltip=[
                alt.Tooltip("population_estimate:Q", title="Population Estimate"),
                alt.Tooltip("population_lower:Q", title="Lower Estimate"),
                alt.Tooltip("population_upper:Q", title="Upper Estimate"),
        ]
        ).add_params(nearest)

        error_bars = points.mark_rule().encode(
            x="population_lower:Q",
            x2="population_upper:Q",
        )

        return (points + error_bars + rules + highlight).properties(
            title=alt.Title(
                f"Regional Population Estimates for the {input.species_v5()}",
                subtitle="Intervals represent 5th and 95th percentile of the bootstrap distribution"
            ),
            width="container",
            height=750
        )

    @render_altair
    def density_chart():

        df = population_data()

        points = alt.Chart(df).mark_point(
            filled=True,
        ).encode(
            alt.X("density_estimate:Q")
                .title("Density (males/ha)"),
            alt.Y("region_name:N")
                .title(None)
                .sort(
                    field="density_estimate",
                    order="descending",
                )
                .axis(labelLimit=0),
            alt.Color(
                "country_name:N",
                legend=alt.Legend(title="Country")
            ),
        ).transform_calculate(
            region_name=f"{region_dict}[datum.region].name_adj",
            country_name=f"{region_dict}[datum.region].country"
        )

        nearest = alt.selection_point(
            nearest=True,
            on="pointerover",
            fields=["density_estimate"],
            empty=False
        )
        when_near = alt.when(nearest)

        highlight = points.mark_point(
            size=50,
            stroke="#153B40FF",
        ).encode(
            opacity=when_near.then(alt.value(1)).otherwise(alt.value(0))
        )

        rules = alt.Chart(df).mark_rule(
            color="#153B40FF",
        ).encode(
            x="density_estimate:Q",
            opacity=alt.when(nearest)
                .then(alt.value(0.5))
                .otherwise(alt.value(0)),
            tooltip=[
                alt.Tooltip("density_estimate:Q", title="Density Estimate"),
                alt.Tooltip("density_lower:Q", title="Lower Estimate"),
                alt.Tooltip("density_upper:Q", title="Upper Estimate"),
        ]
        ).add_params(nearest)

        error_bars = points.mark_rule().encode(
            x="density_lower:Q",
            x2="density_upper:Q",
        )

        return (points + error_bars + rules + highlight).properties(
            title=alt.Title(
                f"Regional Density Estimates for {input.species_v5()}",
                subtitle="Intervals represent 5th and 95th percentile of the bootstrap distribution"
            ),
            width="container",
            height=750
        )