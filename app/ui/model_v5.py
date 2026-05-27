from shiny import ui
from shinywidgets import output_widget
from ui.sidebar import sidebar
from icons import question_circle_fill

def model_v5_tab():
    """
    This function constructs a navigation panel containing a bird information 
    header and a multi-tabbed card interface. The card interface allows users 
    to toggle between a spatial map with band selection, land cover analytics, 
    and population size estimates.

    Current Model tab — compact bird header with MAP/INFO toggle.
    MAP view: interactive map, land cover, population, density, download.
    INFO view: species info, photo gallery, songs.

    Returns
    -------
    shiny.ui
    """
    return ui.nav_panel(
        "Current Model",
        ui.layout_sidebar(
            sidebar("v5"),

            # ── Compact bird header + MAP/INFO toggle ──────────────────
            # ui.card(
                ui.layout_columns(
                    ui.output_ui("selected_bird"),
                    ui.div(
                        ui.input_radio_buttons(
                            "view_toggle",
                            None,
                            choices={"map": "Map", "info": "Info"},
                            selected="map",
                            inline=True,
                        ),
                        class_="toggle-wrapper",
                    ),
                    col_widths=(8, -1 , 3),
                    class_="bird-header-row",
                ),
            # ),

            # ── MAP view ───────────────────────────────────────────────
            ui.panel_conditional(
                "input.view_toggle === 'map'",
                ui.navset_card_underline(
                    ui.nav_spacer(),
                    ui.nav_panel(
                        "Map",
                        output_widget("map_widget"),
                    ),
                    ui.nav_panel(
                        "Land Cover",
                        ui.p("land_cover_placeholder"),
                    ),
                    ui.nav_panel(
                        "Population",
                        ui.card(output_widget("population_chart"), full_screen=True),
                    ),
                    ui.nav_panel(
                        "Density",
                        ui.card(output_widget("density_chart"), full_screen=True),
                    ),
                    ui.nav_panel(
                        "Download",
                        ui.output_data_frame("population_size"),
                    ),
                    title=ui.tooltip(
                        ui.span("Model Results ", question_circle_fill),
                        "Population size (M males) is based on summing up predictive maps by regions.",
                        placement="right",
                        id="results_tooltip",
                        class_="results_tooltip",
                    ),
                ),
            ),

            # ── INFO view ──────────────────────────────────────────────
            ui.panel_conditional(
                "input.view_toggle === 'info'",
                ui.navset_card_underline(
                    ui.nav_panel("Info",   ui.output_ui("species_info")),
                    ui.nav_panel("Images", ui.output_ui("species_images")),
                    ui.nav_panel("Songs",  ui.output_ui("species_songs")),
                    title="Species Info",
                ),
            ),
        )
    )