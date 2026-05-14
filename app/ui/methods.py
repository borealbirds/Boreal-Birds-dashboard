import yaml
from pathlib import Path
from shiny import ui

contents_dir = Path(__file__).parent.parent / "content"

methods_sections = yaml.safe_load(
    Path(str(contents_dir / "methods.yaml")).read_text()
)

methods_accordion = ui.accordion(
    *[
        ui.accordion_panel(
            section["section"],
            ui.p(section["content"])
        )
        for section in methods_sections
    ],
    open=False
)

def methods_tab():
    return ui.nav_panel(
        "Methods",
        ui.card(
            "Our Methods",
            ui.p("Reliable information on species' population sizes, trends..."),
        ),
        ui.card(methods_accordion)
    )