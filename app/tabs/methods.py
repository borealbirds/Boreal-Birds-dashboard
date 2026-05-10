from shiny import ui
from content.methods_content import methods_sections

def methods_tab():

    methods_accordion = ui.accordion(
        *[
            ui.accordion_panel(
                section["title"],
                ui.p(section["content"])
            )
            for section in methods_sections
        ],
        open=False
    )

    return ui.nav_panel(
        "Methods",
        ui.card(
            "Our Methods",
            ui.p("Reliable information on species' population sizes, trends..."),
        ),
        methods_accordion
    )