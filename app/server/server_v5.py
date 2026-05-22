from shiny import Inputs, reactive, ui, render
from shinywidgets import render_widget, output_widget, render_altair
from ipywidgets import HTML
from ipyleaflet import (
    Map, basemaps, TileLayer,
    basemap_to_tiles, LayersControl, ScaleControl,
    FullScreenControl, WidgetControl
)
import altair as alt
import polars as pl
import requests

from shared import (
    get_tif_path,
    available_regions,
    available_years,
    load_species_metadata,
    load_abundance_data
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

def server_v5(input: Inputs):
    """
    Main server logic for the Model V5 tab, managing reactive data flow 
    and spatial visualization.
    """

    @render.ui
    def selected_bird():
        bird = birds.filter(pl.col("english") == input.species())

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
        species_id = birds.filter(pl.col("english") == input.species()).item(0, "id")

        if not species_id:
            ui.update_select("region", choices=[], selected=None)
            return

        regions = available_regions(species_id)

        ui.update_select(
            "region",
            choices=regions,
            selected=regions[0] if regions else None,
        )

    @reactive.effect
    def _update_year_range():
        """Update the slider range and default value based on available temporal data."""
        species_id = birds.filter(pl.col("english") == input.species()).item(0, "id")
        region = input.region()

        if not species_id or not region:
            return

        years = available_years(species_id, region)

        if not years:
            return

        ui.update_slider(
            "year",
            min=min(years),
            max=max(years),
            value=max(years),
        )
    
    @reactive.calc
    def file_url():
        """Construct the remote URL string path for the selected raster."""
        species_id = birds.filter(
            pl.col("english") == input.species()
        ).item(0, "id")

        region = input.region()
        year = input.year()

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
        except Exception:
            print(f"Error fetching TiTiler statistics: {e}")
            return {"min": 0.0, "max": 1.0}

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
        map_center = REGION_CENTERS.get(input.region(), [60.0, -110.0])

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
        tile_string = f"{PRODUCTION_TILER_BASE}/cog/tiles/{{z}}/{{x}}/{{y}}.png?url={encoded_cog}&colormap_name=ylgn&rescale={rmin},{rmax}"
        
        mean_density = TileLayer(
            url=tile_string,
            name="Mean Density",
            # opacity=0.75
        )

        m.add(mean_density)
        m.add(legend)

        # controls
        m.add(FullScreenControl())
        m.add(LayersControl(collapsed=False, position='topright'))
        m.add(ScaleControl(position='bottomleft'))

        return m
    
    @reactive.calc
    def population_data():
        return abundances.filter(
            (pl.col("english") == input.species())
        )

    @render.data_frame
    def population_size():
        df = population_data()

        df = df.select([
            'year',
            'region', 
            'population_estimate', 
            'population_lower', 
            'population_upper', 
            'density_estimate', 
            'density_lower', 
            'density_upper'
        ])

        return render.DataGrid(df, selection_mode="rows")

    @render_altair
    def population_chart():

        df = population_data()

        points = alt.Chart(df).mark_point(
            filled=True,
            color='green'
        ).encode(
            alt.X('population_estimate').title('Abundance (M males)').scale(type="log"),
            alt.Y('region').title("").sort(
                field='population_estimate',
                order='descending'
            ),
            tooltip=alt.Tooltip([
                "population_estimate",
                "population_lower",
                "population_upper",
            ])
        ).properties(
            width="container",
            height=500
        )

        error_bars = points.mark_rule().encode(
            x='population_lower',
            x2='population_upper',
        )

        return (points + error_bars).properties(
            title=alt.Title(
                f"Regional Population Estimates for {input.species()}",
                subtitle="Intervals represent 5th and 95th percentile of the bootstrap distribution"
            )
        )

    @render_altair
    def density_chart():

        df = population_data()

        points = alt.Chart(df).mark_point(
            filled=True,
            color='green'
        ).encode(
            alt.X('density_estimate').title('Density (males/ha)'),
            alt.Y('region').title("").sort(
                field='density_estimate',
                order='descending'
            ),
            tooltip=alt.Tooltip([
                "density_estimate",
                "density_lower",
                "density_upper"
            ])
        ).properties(
            width="container",
            height=500
        )

        error_bars = points.mark_rule().encode(
            x='density_lower',
            x2='density_upper',
        )

        return (points + error_bars).properties(
            title=alt.Title(
                f"Regional Density Estimates for {input.species()}",
                subtitle="Intervals represent 5th and 95th percentile of the bootstrap distribution"
            )
        )