"""
Main entry point and UI layout for the BAM Shiny Dashboard.

This script assembles the global navbar layout, links static web assets, 
and coordinates the reactive server orchestration loops.

Attributes
----------
www_dir : Path
    Path to static frontend assets (CSS, images, favicons).
app_ui : page_navbar
    The main user interface navigation and layout structure.
app : App
    The instantiated Shiny application runtime object.
"""

from pathlib import Path

from shiny import App, Inputs, Outputs, Session, ui

from components import audio, footer, website, website_contact
from server.server_v5 import server_v5
from ui.methods import methods_tab
from ui.landbirds_v4 import landbirds_v4_tab
from ui.landbirds_v5 import landbirds_v5_tab
from ui.model_access import citing_tab, vignettes_tab, tools_tab
from ui.welcome import welcome_tab

www_dir = Path(__file__).parent / "www"

app_ui = ui.page_navbar(
    ui.head_content(
        ui.include_css(str(www_dir / "styles.css")),
        ui.tags.link(rel="icon", href="img/favicon.png", type="image/x-icon"),
        audio(),
    ),
    ui.nav_spacer(),
    welcome_tab(),
    ui.nav_menu(
        "Models",
        landbirds_v5_tab(),
        landbirds_v4_tab(),
    ),
    ui.nav_menu(
        "Model Access",
        tools_tab(),
        citing_tab(),
    ),
    methods_tab(),
    ui.nav_menu(
        "Contact Us",
        website(),
        website_contact(),
    ),
    selected="Landbirds v5",
    id="tabs",
    title=ui.tags.a(
        ui.tags.img(
            src="img/BAM-Logo-WhiteText.svg",
            alt="Boreal Avian Modelling Centre Dashboard",
            height="48"
        ),
    ),
    fillable=True,
    footer=footer()
)


def server(input: Inputs, output: Outputs, session: Session) -> None:
    """
    Root server coordinator for the Shiny application.

    Delegates the reactive session execution loop downstream to the 
    Version 5 analytical backend engine.

    Parameters
    ----------
    input : Inputs
        Reactive container for user interface input nodes.
    output : Outputs
        Reactive registry handling user interface output components.
    session : Session
        The active client connection and runtime execution session.

    Returns
    -------
    None
    """
    server_v5(input, output, session)


app = App(app_ui, server, static_assets=www_dir)