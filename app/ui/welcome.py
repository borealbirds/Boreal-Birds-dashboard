from shiny import ui

from shared import read_md

def welcome_tab():

    return ui.nav_panel(
        "Welcome",
        ui.card(
            ui.card_header("A Boreal Avian Modelling Project", style="font-size:1.25rem"),
            ui.markdown(read_md("welcome.md")),
            class_="welcome-card"
        ),
    )