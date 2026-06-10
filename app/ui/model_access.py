from shiny import ui

from shared import read_md


def _vignette_panel(title, src):
    """
    Create a navigation panel with an embedded iframe for a vignette.

    Parameters
    ----------
    title: str
        Title of the vignette navigation panel.
    src: str
        File path of the vignette to be embedded in the iframe.

    Returns
    -------
    shiny.ui
        A Shiny UI component containing a navigation panel with an embedded iframe of the vignette.
    """
    return ui.nav_panel(
        title,
        ui.tags.iframe(
            src=src,
            style="""
                width: 100%;
                height: 60vh;
                border: none;
                display: block;
            """
        ),
    )


def vignettes_tab():
    """UI for the vignettes tab, featuring vignettes for the BAMexploreR package."""
    return ui.nav_panel(
        "Vignettes",
        ui.layout_columns(
            ui.navset_card_underline(
                ui.nav_spacer(),
                _vignette_panel("Introduction", "vignettes/BAMexploreR_1_intro.html"),
                _vignette_panel("Access", "vignettes/BAMexploreR_2_access.html"),
                _vignette_panel("Distribution", "vignettes/BAMexploreR_3_distribution.html"),
                _vignette_panel("Habitat", "vignettes/BAMexploreR_4_habitat.html"),
                title="Vignettes",
                ),
            col_widths=(-1, 10, -1),
        ),
    )


def tools_tab():
    """UI for the tools tab, providing resources for exploring BAM products."""
    return ui.nav_panel(
        "Tools",
        ui.layout_columns(
            ui.card(
                ui.card_header("Explore BAM Products"),
                ui.navset_tab(
                    ui.nav_panel("All", ui.markdown(read_md("tools.md"))),
                    ui.nav_menu(
                        "R Package Vignettes",
                        _vignette_panel("Introduction", "vignettes/BAMexploreR_1_intro.html"),
                        _vignette_panel("Access", "vignettes/BAMexploreR_2_access.html"),
                        _vignette_panel("Distribution", "vignettes/BAMexploreR_3_distribution.html"),
                        _vignette_panel("Habitat", "vignettes/BAMexploreR_4_habitat.html"),
                    ),
                    id="tools_navset"
                ),
                class_="tools-card"
            ),
            col_widths=(-1, 10, -1),
        ),
    )


def citing_tab():
    """UI for the citing tab; how to cite BAM model results."""
    return ui.nav_panel(
        "Citing Results",
        ui.layout_columns(
            ui.card(
                ui.card_header("How to Cite BAM Model Results"),
                ui.markdown(read_md("citing.md")),
                fill=False,
                class_="citing-card"
            ),
            col_widths=(-1, 10, -1),
        ),
    )
