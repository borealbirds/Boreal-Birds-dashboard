from shiny import ui
from shared import load_species_metadata


def sidebar():
    species_choices = sorted(load_species_metadata().get_column("english").to_list())

    return ui.sidebar(
        ui.input_select(
            "species",
            "Species",
            choices=species_choices,
            size=10
        ),
        ui.input_select(
            "region",
            "Region",
            choices=[],
            size=3
        ),
        ui.input_slider(
            "year",
            "Year",
            min=1990,
            max=2020,
            value=2020,
            step=5,
        ),
        width=375,
    )
