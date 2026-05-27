from shiny import ui
from shared import load_species_metadata


def sidebar(model_version: str):
    """ model version: v4 or v5 """
    species_choices = sorted(load_species_metadata().get_column("english").to_list())

    return ui.sidebar(
        ui.input_select(
            f"species_{model_version}",
            "Species",
            choices=species_choices,
            size=10
        ),
        ui.input_select(
            f"region_{model_version}",
            "Region",
            choices=[],
            size=3
        ),
        ui.input_slider(
            f"year_{model_version}",
            "Year",
            min=1990,
            max=2020,
            value=2020,
            step=5,
            ticks=True,
            sep=''
        ),
        width=375,
    )
