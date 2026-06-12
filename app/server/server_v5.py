import io
import json
import warnings
from datetime import date
from pathlib import Path

import requests
import altair as alt
import polars as pl
import xlsxwriter

from ipywidgets import Button, HTML, Layout
from ipyleaflet import (
    basemap_to_tiles,
    basemaps,
    FullScreenControl,
    GeoJSON,
    LayersControl,
    Map,
    ScaleControl,
    TileLayer,
    WidgetControl,
)

from shiny import Inputs, Outputs, Session, reactive, render, ui, req
from shinywidgets import render_altair, render_widget

from icons import question_circle_fill
from shared import *
from modules.map import *
from modules.media import *

# alt.data_transformers.enable("vegafusion")

warnings.filterwarnings(
    "ignore",
    category=RuntimeWarning,
    module="numpy.ma.core"
)

# log in terminal
print(f"\n\n\nTitiler API Health Status: \n\tTitiler is healthy: {tiler_is_healthy()}\n\n\n")

birds = load_species_metadata()
abundances = load_abundance_data()
covariates = load_covariate_metadata()

# ── PURE HELPER FUNCTIONS (Non-reactive) ───────────────────────────

def _format_population_value(pop_df: pl.DataFrame) -> str:
    """Extract and format the population estimate string."""
    pop_raw = pop_df.item(0, 'population_estimate') if len(pop_df) > 0 else None
    if pop_raw is None:
        return "—"
    elif round(pop_raw, 2) == 0.0:
        return f"{pop_raw:.3f}"
    return f"{pop_raw:.2f}"

# ── MAIN SERVER LOGIC ──────────────────────────────────────────────

def server_v5(input: Inputs, output: Outputs, session: Session):
    """
    Main server logic for the Model V5 tab, managing reactive data flow 
    and spatial visualization.
    """

    # ── CENTRALIZED REACTIVE CALCS (Data Layers) ───────────────────

    @reactive.calc
    def current_bird_meta() -> pl.DataFrame:
        """Returns the single row metadata slice for the selected species."""
        return birds.filter(pl.col("english") == input.species_v5())

    @reactive.calc
    def population_data() -> pl.DataFrame:
        """Returns regional abundance data filtered by species."""
        return abundances.filter(pl.col("english") == input.species_v5())

    @reactive.calc
    def current_population_slice() -> pl.DataFrame:
        """Returns specific population row matching current input parameters."""
        return abundances.filter(
            (pl.col("english") == input.species_v5()) &
            (pl.col("region")  == input.region_v5()) &
            (pl.col("year")    == str(input.year_v5()))
        )

    @reactive.calc
    def file_url() -> str | None:
        """Construct the remote URL string path for the selected raster."""
        bird = current_bird_meta()
        species_id = bird.item(0, "id") if len(bird) > 0 else None
        region = input.region_v5()
        year = input.year_v5()

        if not species_id or not region or not year:
            return None
        return get_tif_path(species_id, region, int(year))

    @reactive.calc
    def raster_info() -> dict:
        """Query min/max data statistics remotely using the TiTiler metadata API."""
        url = file_url()
        if url is None:
            return {"status": "loading"}
        if not url or not url_exists(url):
            return {"status": "missing"}
        if not tiler_is_healthy():
            return {"status": "tiler_unavailable"}

        try:
            encoded_cog = requests.utils.quote(url, safe="")
            stats_url = f"{PRODUCTION_TILER_BASE}/cog/statistics?url={encoded_cog}"
            res = requests.get(stats_url, timeout=5)
            res.raise_for_status()

            stats = res.json()
            band_key = next(iter(stats), None)
            if not band_key:
                return {"status": "error"}

            band = stats[band_key]
            return {
                "status": "ready",
                "min": float(band.get("min", 0)),
                "max": float(band.get("max", 1))
            }
        except Exception as e:
            print(f"Statistics request failed: {e}")
            return {"status": "tiler_starting"}


    # ── REACTIVE EFFECTS (UI Synchronization) ──────────────────────

    @reactive.effect
    def _set_map_default():
        """Force MAP view on session init."""
        ui.update_radio_buttons("view_toggle", selected="map")

    @reactive.effect
    def _update_regions():
        """Update the region dropdown choices dynamically based on species availability."""
        bird = current_bird_meta()
        species_id = bird.item(0, "id") if len(bird) > 0 else None

        if not species_id:
            ui.update_select("region_v5", choices=[], selected=None)
            return

        regions = available_regions(species_id)
        selected_default = "Canada" if regions and "Canada" in regions else (regions[0] if regions else None)
        ui.update_select("region_v5", choices=regions, selected=selected_default)

    @reactive.effect
    def _update_year_range():
        """Update the slider range and default value based on available temporal data."""
        bird = current_bird_meta()
        species_id = bird.item(0, "id") if len(bird) > 0 else None
        region = input.region_v5()

        if not species_id or not region:
            return

        years = available_years(species_id, region)
        if not years:
            return

        ui.update_slider("year_v5", min=min(years), max=max(years), value=max(years))


    # ── RENDERED UI ELEMENTS ───────────────────────────────────────

    @render.ui
    def selected_bird():
        bird = current_bird_meta()
        pop_df = current_population_slice()
        pop_value = _format_population_value(pop_df)
        region = input.region_v5()

        return ui.div(
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

    @render.ui
    def sidebar_bird_image_v5():
        bird = current_bird_meta()
        if len(bird) == 0:
            return ui.span()
            
        img_info = get_sidebar_image_path(bird.item(0, "id"), bird.item(0, "english"))
        if img_info:
            src_path, folder_name = img_info
            return ui.tags.img(
                src=src_path,
                class_="bird-image-sidebar",
                alt=bird.item(0, "english"),
                onerror="this.style.display='none'",
            )
        return ui.span()


    # ── SPATIAL VISUALIZATION (Map Engine) ─────────────────────────
    
    REGION_LAYERS = {
        "Canada": build_region_layer("Canada"),
        "Lower48": build_region_layer("Lower48"),
        "Alaska": build_region_layer("Alaska"),
    }

    @render_widget
    def map_widget():
        """Generate the interactive map widget leveraging the remote cloud tiler engine."""
        info = raster_info()
        if info["status"] != "ready":
            return get_map_error_html(info["status"])

        url = file_url()
        encoded_cog = requests.utils.quote(url, safe="")
        region = input.region_v5()
        
        # Basemaps Setup
        positron = basemap_to_tiles(basemaps.CartoDB.Positron)
        positron.base, positron.name = True, "Positron (minimal)"

        osm = basemap_to_tiles(basemaps.OpenStreetMap.Mapnik)
        osm.base, osm.name = True, "Open Street Map (default)"
        
        esri = basemap_to_tiles(basemap=basemaps.Esri.WorldImagery)
        esri.base, esri.name = True, "World Imagery (satellite)"

        # initialize map
        map_center = REGION_CENTERS.get(region, [60.0, -110.0])
        m = Map(layers=[esri, positron, osm], center=map_center, zoom=4, scroll_wheel_zoom=True)

        # generate legend using stats from titiler
        rmin, rmax = info["min"], info["max"]
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

        mean_density = TileLayer(url=tile_string, name="Mean Density")
        m.add(mean_density)
        m.add(legend)

        if region in REGION_LAYERS:
            region_layer, hover_card, hover_control = REGION_LAYERS[region]
            default_center = REGION_CENTERS.get(region, [60, -110])
            default_zoom = 4

            # hover
            def update_hover(event=None, feature=None, **kwargs):

                props = feature.get("properties", {})
                bcr = props.get("bcr", "Unknown")

                hover_card.value = f"""
                <div style="
                    padding:8px 10px;
                    background:white;
                    border-radius:6px;
                    box-shadow:0 1px 4px rgba(0,0,0,0.25);
                    font-size:13px;
                    min-width:160px;
                ">
                    <div>
                        {REGION_DICT[bcr]['name_adj']}
                    </div>
                </div>
                """

            # click on region to zoom
            def zoom_to_bcr(event=None, feature=None, **kwargs):
                props = feature.get("properties", {})
                center = props.get("_center")
                spanx, spany = props.get("_spanx"), props.get("_spany")

                if center and spanx and spany:
                    m.center = center
                    m.zoom = zoom_from_span(spanx, spany)

            region_layer.on_hover(update_hover)
            region_layer.on_click(zoom_to_bcr)

            # reset zoom button
            reset_btn = Button(
                description="Reset Zoom",
                layout=Layout(width="120px")
            )

            def reset_zoom(btn):
                m.center = default_center
                m.zoom = default_zoom

            reset_btn.on_click(reset_zoom)
            reset_control = WidgetControl(
                widget=reset_btn,
                position="bottomleft"
            )

            # add to map
            m.add(region_layer)
            m.add(hover_control)

        # controls
        m.add(FullScreenControl())
        m.add(LayersControl(collapsed=False, position="topright"))
        m.add(reset_control)
        m.add(ScaleControl(position="bottomleft"))

        return m


    # ── TABULAR DATA ───────────────────────────────────────────────────

    @render.data_frame
    def population_size():
        region = input.region_v5()
        year = int(input.year_v5())

        if not region:
            return render.DataGrid(pl.DataFrame(), selection_mode="rows")


        df = population_data().filter(pl.col("year") == str(year))
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

        df = df.with_columns(
            (pl.col("region") == region).alias("selected_region")
        ).sort("population_estimate", "selected_region", descending=[True, True])

        region_row_number = df.select(pl.arg_where(pl.col("region") == region)).to_series().to_list()

        selected_style = [
            {
                "rows": region_row_number,
                "style": {
                    "background-color": "#A9DC67FF",
                    "height": "50px",
                },
            }
        ]

        return render.DataGrid(df.select(pl.exclude("selected_region")), selection_mode="rows", styles=selected_style)

    # ── INFO TAB ───────────────────────────────────────────────────────

    @render.ui
    def species_info():
        bird = current_bird_meta()
        species_id = bird.item(0, "id")
        scientific = bird.item(0, "scientific")
        french = bird.item(0, "french")
        family = bird.item(0, "family")

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
            ui.div(
                ui.span("More Information", class_="info-label"),
                ui.div(
                    ui.tags.a("eBird ↗",       href=f"https://ebird.org/search?q={scientific.replace(' ', '+')}", target="_blank", class_="info-link"),
                    ui.tags.a("Xeno-Canto ↗",  href=f"https://xeno-canto.org/species/{scientific.replace(' ', '-')}", target="_blank", class_="info-link"),
                    ui.tags.a("Wikipedia ↗",   href=f"https://en.wikipedia.org/wiki/{scientific.replace(' ', '_')}", target="_blank", class_="info-link"),
                ),
                class_="info-row info-row-links",
            ),
            class_="species-info-card",
        )

    # ── IMAGES TAB ─────────────────────────────────────────────────────

    @render.ui
    def species_images():
        bird = current_bird_meta()
        species_id = bird.item(0, "id")
        common_name = bird.item(0, "english")
        french_name = bird.item(0, "french")
        try:
            scientific_name = bird.item(0, "scientific")
        except Exception:
            scientific_name = ""
        folder_name = f"{species_id}_{common_name.replace(' ', '_')}"
        img_dir = Path(__file__).parent.parent / "www" / "img" / folder_name

        if not img_dir.exists():
            return ui.p("No images available for this species.", class_="text-muted p-3")

        photos = []
        for jpg in sorted(img_dir.glob("*.jpg")):
            meta_path = img_dir / f"{jpg.stem}_metadata.json"
            sex, attribution, obs_url, license = "unknown", "", "", ""
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                    sex = meta.get("sex", "unknown")
                    attribution = meta.get("attribution", "")
                    obs_url = meta.get("obs_url", "")
                    license = meta.get("license", "")
                except Exception:
                    pass
            photos.append({
                "file": jpg.name, 
                "sex": sex, 
                "attribution": attribution, 
                "obs_url": obs_url, 
                "license": license
            })

        if not photos:
            return ui.p("No images found.", class_="text-muted p-3")

        SEX_SYMBOL = {"male": "♂", "female": "♀", "unknown": "?"}

        def photo_grid(items, with_badges=False):
            if not items:
                return ui.p("No photos in this category.", class_="text-muted p-2")
            return ui.div(
                *[
                    ui.div(
                        ui.tags.img(
                            src=f"img/{folder_name}/{p['file']}",
                            class_="species-photo",
                            loading="lazy",
                            onclick="openSpeciesLightbox(this)",
                            data_sex=p["sex"],
                            data_attribution=p.get("attribution",""),
                            data_obs_url=p.get("obs_url",""),
                            data_license=p.get("license",""),
                            data_common=common_name,
                            data_french=french_name,
                            data_scientific=scientific_name,
                        ),
                        ui.span(
                            SEX_SYMBOL.get(p["sex"], "?"),
                            class_=f"sex-badge sex-{p['sex']}"
                        ) if with_badges else ui.span(),
                        class_="photo-cell",
                    ) for p in items
                ],
                class_="photo-grid",
            )

        male_photos = [p for p in photos if p["sex"] == "male"]
        female_photos = [p for p in photos if p["sex"] == "female"]

        return ui.div(
            lightbox_script(),
            ui.HTML("""
                <label class="tag-toggle-floating">
                    <input type="checkbox"
                        onchange="this.closest('.images-tab-wrapper').classList.toggle('show-sex-tags', this.checked)">
                    ♂♀ labels
                </label>
            """),
            ui.navset_tab(
                ui.nav_panel(f"All ({len(photos)})",          photo_grid(photos, with_badges=True)),
                ui.nav_panel(f"Male ({len(male_photos)})",    photo_grid(male_photos)),
                ui.nav_panel(f"Female ({len(female_photos)})", photo_grid(female_photos)),
            ),
            class_="images-tab-wrapper species-images-container",
        )

    # ── SONGS TAB ──────────────────────────────────────────────────────

    @render.ui
    def species_songs():
        bird = current_bird_meta()
        species_id = bird.item(0, "id")
        common_name = bird.item(0, "english")
        scientific_name = bird.item(0, "scientific") if "scientific" in bird.columns else ""
        
        folder_name = f"{species_id}_{common_name.replace(' ', '_')}"
        audio_dir = Path(__file__).parent.parent / "www" / "audio" / folder_name

        if not audio_dir.exists():
            return ui.p("No sounds available for this species.", class_="text-muted p-3")

        audio_files = sorted(audio_dir.glob("*.mp3"))[:5]
        if not audio_files:
            return ui.p("No audio files found.", class_="text-muted p-3")

        # Load metadata keyed by song index (first segment of filename)
        meta_map = {}
        for mf in audio_dir.glob("*_metadata.json"):
            try:
                meta_map[mf.name.split("_")[0]] = json.loads(mf.read_text())
            except Exception:
                pass

        songs = [
            {
                "wsId": f"ws-{species_id}-{i}",
                "specId": f"spec-{species_id}-{i}",
                "metaId": f"meta-{species_id}-{i}",
                "btnId": f"btn-{species_id}-{i}",
                "src": f"/audio/{folder_name}/{f.name}",
                "label": f"Sound {i}",
                "commonName": common_name,
                "scientificName": scientific_name,
                "recordist": (m := meta_map.get(str(i), {})).get("recordist", ""),
                "country": m.get("country", ""),
                "date": m.get("date", ""),
                "quality": m.get("quality", ""),
                "license": m.get("license", ""),
                "xc_url": m.get("xeno_canto_url", "") or m.get("obs_url", ""),
            } for i, f in enumerate(audio_files, 1)
        ]

        song_blocks = [
            ui.div(
                ui.div(
                    ui.span(s["label"], class_="song-label"),
                    ui.tags.button("▶  Play", id=s["btnId"], class_="play-btn"),
                    class_="song-controls",
                ),
                ui.div(
                    ui.HTML('<div class="ws-loading">Loading waveform…</div>'),
                    id=s["wsId"],
                    class_="waveform-container",
                ),
                ui.div(id=s["specId"], class_="spectrogram-container"),
                ui.div(id=s["metaId"], class_="sound-meta"),
                class_="song-block",
            ) for s in songs
        ]

        sounds_json = json.dumps(songs)

        return ui.div(
            *song_blocks,
            sound_script(sounds_json),
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
                .scale(type="symlog"),
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
            region_name=f"{REGION_DICT}[datum.region].name_adj",
            country_name=f"{REGION_DICT}[datum.region].country"
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
            width="container", height=750
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
            region_name=f"{REGION_DICT}[datum.region].name_adj",
            country_name=f"{REGION_DICT}[datum.region].country"
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
            width="container", height=750
        )


    # ── COVARIATE FILTER & MARGINAL EFFECTS ───────────────────────────

    @render.ui
    def marginal_fx_filter():
        cov_choices = sorted(covariates.get_column("name").unique().to_list())
        # cov_choices.append("year")
        res_choices = covariates.get_column("prediction_resolution").unique().to_list()

        return ui.layout_columns(
            ui.input_select(
                id="covariate_filter",
                label="Select Covariate",
                choices=cov_choices
            ),
            ui.input_select(
                id="resolution_filter",
                label="Select Resolution",
                choices=res_choices
            ),
            col_widths=(12, 12)
        )

    @render_altair
    def marginal_fx_chart():
        req(
            input.covariate_filter(), 
            input.resolution_filter(), 
            input.species_v5()
        )
        
        bird = current_bird_meta()
        bird_code = bird.item(0, "id") if len(bird) > 0 else ""

        cov_vars = covariates.filter(
            (pl.col("name") == input.covariate_filter()) & 
            (pl.col("prediction_resolution") == input.resolution_filter())
        ).get_column("variable").to_list()

        fx_df = get_cov_fx_data(cov_vars).filter(pl.col("species") == bird_code)
        viz_df = fx_df.with_columns(pl.col("x").round(2)).group_by(["bcr", "x"]).agg(pl.col("y").mean().alias("mean_y"))

        points = alt.Chart(viz_df).mark_point().encode(
            alt.X("x:N")
                .title(f"Covariate: {input.covariate_filter()}")
                .bin(maxbins=20),
            alt.Y("mean_y:Q")
                .title("Marginal Effect on Density")
                .axis(labelLimit=0),
            alt.Color(
                "bcr:N",
                legend=alt.Legend(title="BCR")
            ),
        )

        # trendline = points.transform_regression(
        #     'x', 'y'
        # ).mark_line(size=3)

        return (points)


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
        abundances = pl.read_excel(model_results, sheet_name="abundances").filter(
            (pl.col("english") == input.species_v5()) & (pl.col("year") == str(input.year_v5()))
        )

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

    @render.ui
    def download_filtered_btn():
        species = input.species_v5()

        return ui.download_button(
            "downloadFiltered",
            f"Download {species} Results"
        )