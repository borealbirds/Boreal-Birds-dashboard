from shiny import ui

def model_v5_tab():

    return ui.nav_panel(
        "Model V5",
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