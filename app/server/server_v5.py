from shiny import Inputs, reactive, ui, render
from shinywidgets import render_widget, output_widget, render_altair
from ipywidgets import HTML
from ipyleaflet import (
    Map, basemaps, TileLayer, GeoData,
    basemap_to_tiles, LayersControl, ScaleControl,
    FullScreenControl, WidgetControl, GeoJSON
)
from datetime import date
import json
import altair as alt
import requests
import polars as pl
from pathlib import Path
import geopandas as gpd
from functools import lru_cache

from icons import question_circle_fill
import xlsxwriter
import io

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
    "Canada": [58, -103],
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
        from pathlib import Path
        bird   = birds.filter(pl.col("english") == input.species_v5())
        region = input.region_v5() or ""
        year   = int(input.year_v5())

        # Find first available photo in species folder
        species_id   = bird.item(0, "id")
        common_name  = bird.item(0, "english")
        folder_name  = f"{species_id}_{common_name.replace(' ', '_')}"
        img_dir      = Path(__file__).parent.parent / "www" / "img" / folder_name
        img_src      = None
        if img_dir.exists():
            jpgs = sorted(img_dir.glob("*.jpg"))
            if jpgs:
                img_src = f"img/{folder_name}/{jpgs[0].name}"

        # Population estimate for the selected region + year only
        pop_df = abundances.filter(
            (pl.col("english") == input.species_v5()) &
            (pl.col("region")  == region) &
            (pl.col("year") == str(year))
        )
        pop_raw   = pop_df.item(0, 'population_estimate') if len(pop_df) > 0 else None
        if pop_raw is None:
            pop_value = "—"
        elif round(pop_raw, 2) == 0.0:
            pop_value = f"{pop_raw:.3f}"
        else:
            pop_value = f"{pop_raw:.2f}"

        return ui.div(
            ui.tags.img(
                src=img_src,
                class_="bird-image-sm",
                alt=common_name,
                onerror="this.style.display='none'",
            ) if img_src else ui.span(),
            ui.div(
                ui.span(bird.item(0, "english"), class_="bird-name"),
                ui.span(bird.item(0, "french"),  class_="bird-french"),
                class_="bird-names",
            ),
            ui.div(
                ui.span("Population Estimate ", class_="bird-pop-label"),
                ui.span(region, class_="bird-region-label"),
                ui.span(f" {pop_value}", class_="bird-pop-value"),
                ui.tooltip(
                    question_circle_fill,
                    "Population estimate (millions) for the selected region and year",
                    placement="right",
                ),
                class_="bird-pop",
            ),
            class_="bird-header-content",
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
            selected=(
                "Canada" if regions and "Canada" in regions else (
                    regions[0] if regions else None
                )
            ),
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
        year = int(input.year_v5())

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
        m = Map(layers=[esri, positron, osm], center=map_center, zoom=4, scroll_wheel_zoom=True)

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
        region = input.region_v5()
        year   = int(input.year_v5())

        if not region:
            return render.DataGrid(pl.DataFrame(), selection_mode="rows")

        df = abundances.filter(
            (pl.col("english") == input.species_v5()) &
            (pl.col("region")  == region) &
            (pl.col("year")    == str(year))
        )

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

    # ── INFO TAB ───────────────────────────────────────────────────────

    @render.ui
    def species_info():
        bird        = birds.filter(pl.col("english") == input.species_v5())
        species_id  = bird.item(0, "id")
        scientific  = bird.item(0, "scientific")
        french      = bird.item(0, "french")
        family      = bird.item(0, "family")

        ebird_url = f"https://ebird.org/species/{species_id.lower()}"
        bow_url   = f"https://birdsoftheworld.org/bow/species/{species_id.lower()}"

        def info_row(label, value, italic=False):
            return ui.div(
                ui.span(label, class_="info-label"),
                ui.span(ui.tags.em(value) if italic else value, class_="info-value"),
                class_="info-row",
            )

        return ui.div(
            info_row("Scientific Name", scientific, italic=True),
            info_row("French Name",     french),
            info_row("Family",          family),
            info_row("Species Code",    species_id),
            class_="species-info-card",
        )

    # ── IMAGES TAB ─────────────────────────────────────────────────────

    @render.ui
    def species_images():
        return ui.div(
            ui.navset_tab(
                ui.nav_panel("All",    ui.p("Images coming soon.", class_="text-muted p-3")),
                ui.nav_panel("Male",   ui.p("Male images coming soon.", class_="text-muted p-3")),
                ui.nav_panel("Female", ui.p("Female images coming soon.", class_="text-muted p-3")),
            ),
            class_="species-images-container",
        )

    # ── SONGS TAB ──────────────────────────────────────────────────────

    @render.ui
    def species_songs():
        return ui.div(
            ui.div(ui.span("Song 1", class_="song-label"), class_="song-row"),
            ui.div(ui.span("Song 2", class_="song-label"), class_="song-row"),
            class_="songs-container",
        )
    
    # ── Chart details ───────────────────────────────────────────────────────
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
    
    @render.download(filename=lambda: f"{date.today().isoformat()}_BAMV5-results.xlsx")
    def downloadAll():

        return str(Path(__file__).parent.parent.parent / "data" / "model_v5" / "12_BAMV5-results.xlsx")

    @render.download(filename=lambda: f"{date.today().isoformat()}_{input.species_v5()}_model-results.xlsx")
    def downloadFiltered():

        model_results = str(Path(__file__).parent.parent.parent / "data" / "model_v5" / "12_BAMV5-results.xlsx")
        metadata = pl.read_excel(model_results, sheet_name="metadata")
        species = pl.read_excel(model_results, sheet_name="species").filter(pl.col("english") == input.species_v5())
        regions = pl.read_excel(model_results, sheet_name="regions")
        variables = pl.read_excel(model_results, sheet_name="variables")
        importance = pl.read_excel(model_results, sheet_name="importance").filter(pl.col("english") == input.species_v5())
        validation = pl.read_excel(model_results, sheet_name="validation").filter(pl.col("english") == input.species_v5())
        abundances = pl.read_excel(model_results, sheet_name="abundances").filter(pl.col("english") == input.species_v5())

        with io.BytesIO() as buffer:
            workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
            metadata.write_excel(workbook=workbook, worksheet="metadata", autofilter=False, autofit=True)
            species.write_excel(workbook=workbook, worksheet="species", autofilter=False, autofit=True)
            regions.write_excel(workbook=workbook, worksheet="regions", autofilter=False, autofit=True)
            variables.write_excel(workbook=workbook, worksheet="variables", autofilter=False, autofit=False)
            importance.write_excel(workbook=workbook, worksheet="importance", autofilter=False, autofit=True)
            validation.write_excel(workbook=workbook, worksheet="validation", autofilter=False, autofit=True)
            abundances.write_excel(workbook=workbook, worksheet="abundances", autofilter=False, autofit=True)
            workbook.close()
            yield buffer.getvalue()