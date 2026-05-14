from shiny import Inputs, reactive, ui, render
from shinywidgets import render_widget
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

birds = load_species_metadata()


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
        #species_id = input.species()
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

    @render_widget
    def map_widget():
        """Generate the interactive map widget with the tile layer and legend."""
        client = tile_client()

        if client is None:
            return ui.p("No data available")

        m = Map(
            center=client.center(),
            zoom=4,
            basemap=basemaps.CartoDB.Positron,
        )

        tile_layer = get_leaflet_tile_layer(
            client, colormap="ylgn", indexes=[1]
        )

        m.add_layer(tile_layer)
        legend = HTML(value="""
        <div class="map-legend">
            <div class="map-legend-title">
                <b>Low → High</b>
            </div>

            <div class="map-legend-gradient"></div>
        </div>
        """)

        m.add_control(
            WidgetControl(
                widget=legend,
                position="bottomright",
            )
        )

        return m
