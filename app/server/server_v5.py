from shiny import Inputs, reactive, ui, render
from shinywidgets import render_widget, output_widget
from ipywidgets import HTML
from ipyleaflet import (
    Map, basemaps,
    basemap_to_tiles, LayersControl, ScaleControl,
    FullScreenControl, WidgetControl
)
from localtileserver import TileClient, get_leaflet_tile_layer

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

def url_exists(url: str) -> bool:
    """
    Ensure url for the file exists in the server
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
    def file_url():
        species_id = birds.filter(
            pl.col("english") == input.species()
        ).item(0, "id")

        region = input.region()
        year = input.year()

        if not species_id or not region or not year:
            return None

        return get_tif_path(species_id, region, int(year))

    @render_widget
    def map_widget():
        """Generate the interactive map widget with the tile layer and legend."""
        url = file_url()

        if not url:
            return HTML("<p>No data available</p>")

        if not url_exists(url):
            return HTML("<p>Raster not found on server</p>")

        client = TileClient(url)
        center = client.center()

        positron = basemap_to_tiles(basemaps.CartoDB.Positron)
        positron.base = True
        positron.name = "Positron (minimal)"
        
        osm = basemap_to_tiles(basemaps.OpenStreetMap.Mapnik)
        osm.base = True
        osm.name = "Open Street Map (default)"
        
        esri = basemap_to_tiles(basemap=basemaps.Esri.WorldImagery)
        esri.base = True
        esri.name = "World Imagery (satellite)"

        mean_density = get_leaflet_tile_layer(client, colormap="ylgn", indexes=1, name="Mean Density")
        # mean_detection = get_leaflet_tile_layer(client, colormap="ylgn", indexes=3, name="Mean Detection")

        m = Map(layers=[esri, positron, osm],
                center=center,
        )

        band = client.dataset.read(1).astype(float)
        rmin = float(np.nanmin(band))
        rmax = float(np.nanmax(band))

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

        m.add(mean_density)
        # m.add(mean_detection)

        m.add(legend)

        m.add(FullScreenControl())
        m.add(LayersControl(collapsed=False, position='topright'))
        m.add(ScaleControl(position='bottomleft'))

        return m
    
    @render.data_frame
    def population_size():
        df = abundances.filter(
            (pl.col("english") == input.species()) #& 
            # (pl.col("year") == input.year())
        )
        print(abundances.select("id").unique(), input.species())
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
        print(df)

        return render.DataGrid(df, selection_mode="rows")