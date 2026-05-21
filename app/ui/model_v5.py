from shiny import ui
from shinywidgets import output_widget

from ui.sidebar import sidebar

def model_v5_tab():
    """
    Generate the UI layout for the Model V5 results tab.

    This function constructs a navigation panel containing a bird information 
    header and a multi-tabbed card interface. The card interface allows users 
    to toggle between a spatial map with band selection, land cover analytics, 
    and population size estimates.

    Returns
    -------
    shiny.ui
    """
    return ui.nav_panel(
        "Current Model",
        ui.layout_sidebar(
            sidebar("v5"),
            ui.output_ui(id="selected_bird"),
            ui.navset_card_underline(
                ui.nav_panel(
                    "Map",
                    output_widget("map_widget"),
                ),
                ui.nav_panel(
                    "Land Cover",
                    ui.p("land_cover_placeholder"),
                ),
                ui.nav_panel(
                    "Population Size",
                    ui.output_data_frame("population_size"), 
                ),
                title="Model Results",
            ),
        )
    )