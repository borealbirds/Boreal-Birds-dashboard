from shiny import ui

def about_tab():

    return ui.nav_panel(
        "About",
        ui.p("Welcome to the Boreal Birds Dashboard!"),
        )