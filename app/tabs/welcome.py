from shiny import ui

def welcome_tab():

    return ui.nav_panel(
        "Welcome",
        ui.p("Welcome to the Boreal Birds Dashboard!"),
        )