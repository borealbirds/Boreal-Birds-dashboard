from shiny import ui

from ui.sidebar import sidebar

def model_v4_tab():
    """Model V4 Results"""
    return ui.nav_panel(
        "Historical Model",
        ui.layout_sidebar(
            sidebar(),
            ui.card(
                ui.p("Bird Info Card"),
            ),
            ui.navset_card_underline(
                ui.nav_panel(
                    "Map",
                    ui.p("map_placeholder")
                ),
                ui.nav_panel(
                    "Land Cover",
                    ui.p("land_cover_placeholder")
                ),
                ui.nav_panel(
                    "Population Size",
                    ui.p("population_size_placeholder")
                ),
                title="Model Results",
            ),
        )
    )