from shiny import Inputs, reactive, ui, render
from shinywidgets import render_widget, output_widget
from ipywidgets import HTML
from ipyleaflet import Map, basemaps, WidgetControl
from localtileserver import TileClient, get_leaflet_tile_layer

import polars as pl

from shared import (
    get_tif_path,
    available_regions,
    available_years,
    load_species_metadata,
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

BASEMAPS = {
    "positron": basemaps.CartoDB.Positron,
    "osm": basemaps.OpenStreetMap.Mapnik,
    "imagery": basemaps.Esri.WorldImagery,
}


def server_v5(input: Inputs):
    """
    Main server logic for the Model V5 tab, managing reactive data flow 
    and spatial visualization.
    """

    @render.ui
    def selected_bird():
        bird = birds.filter(pl.col("english") == input.species())
        return bird_card(
            species=bird.item(0, "scientific"),
            common_name=bird.item(0, "english"),
            french_name=bird.item(0, "french"),
            family=bird.item(0, "family"),
            image_url=f"img/{bird.item(0, "id")}.jpg"
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
    def tile_client():
        """Initialize and return a TileClient for the specific raster file selected."""

        species_id = birds.filter(pl.col("english") == input.species()).item(0, "id")
        region = input.region()
        year = input.year()

        if not species_id or not region or not year:
            return None

        path = get_tif_path(
            species_id,
            region,
            int(year),
        )

        if not path.exists():
            return None

        return TileClient(str(path))
    
    @reactive.calc
    def legend_widget():
        """Generate reactive numerical legend for map"""
        client = tile_client()

        if client is None:
            return HTML("<div>No data</div>")

        band = client.dataset.read(1).astype(float)

        rmin = float(np.nanmin(band))
        rmax = float(np.nanmax(band))

        return HTML(f"""
        <div class="map-legend">
            <div class="map-legend-title">
                <b>{rmin:.4f} → {rmax:.4f}</b>
            </div>
            <div class="map-legend-gradient"></div>
        </div>
        """)

    @render.ui
    def map_container():
        """Map container to handle cases where no data is avaliable"""
        client = tile_client()

        if client is None:
            return ui.p("No data available")

        return output_widget("map_widget")

    @render_widget
    def map_widget():
        """Generate the interactive map widget with the tile layer and legend."""
        client = tile_client()

        if client is None:
            return HTML("<p>No data available</p>")

        basemap_key = input.basemap()
        basemap = BASEMAPS.get(basemap_key, basemaps.CartoDB.Positron)

        m = Map(
            center=client.center(),
            zoom=4,
            basemap=basemap,
        )

        tile_layer = get_leaflet_tile_layer(
            client,
            colormap="ylgn",
            indexes=[1]
        )

        m.add_layer(tile_layer)
        m.add_control(
            WidgetControl(
                widget=legend_widget(),
                position="bottomright",
            )
        )

        return m