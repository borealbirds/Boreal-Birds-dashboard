from shiny import ui

from shared import read_md, read_yaml

methods_sections = read_yaml("methods/methods-sections.yaml")

methods_accordion = ui.accordion(
    *[
        ui.accordion_panel(
            section["section"],
            ui.markdown(read_md(section["file"]))
        )
        for section in methods_sections
    ],
    open=None # opens the first section by default
)

def methods_tab():
    return ui.nav_panel(
        "Methods",
        ui.layout_columns(
            ui.card(
                ui.card_header("Our Methods - An Overview"),
                ui.markdown(read_md("methods/methods-intro.md")),
            ),
            ui.card(
                methods_accordion,
                class_="methods-accordion",
            ),
            col_widths=(5, 7),
        ),
    )