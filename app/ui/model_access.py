from shiny import ui

def model_access_tab():

    return ui.nav_panel(
        "Model Access",
        ui.card(
            ui.card_header("Access our various model products", style="font-size:1.25rem"),
            ui.p("A Boreal Avian Modelling Project"),
            class_="model-access-card"
        ),
    )