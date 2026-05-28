from pathlib import Path

from ui.welcome import welcome_tab
from ui.model_v4 import model_v4_tab
from ui.model_v5 import model_v5_tab
from ui.methods import methods_tab
from ui.model_access import model_access_tab
from ui.sidebar import sidebar

from server.server_v5 import server_v5

import polars as pl
from shiny import App, Inputs, reactive, render, ui

www_dir = Path(__file__).parent / "www"

FOOTER = ui.div(
    ui.HTML(
        '&copy; 2026 '
        '<a href="https://borealbirds.ca/" target="_blank">Boreal Avian Modelling Project </a>'
        'under a '
        '<a href="https://creativecommons.org/licenses/by-sa/4.0/", target="_blank"> CC BY-SA 4.0 license </a>'
    ),
    class_="footer"
)

app_ui = ui.page_navbar(
    ui.head_content(ui.include_css(str(www_dir / "styles.css"))),
    ui.nav_spacer(),
    welcome_tab(),
    ui.nav_menu(
        "Models",
        model_v5_tab(),
        model_v4_tab(),
    ),
    model_access_tab(),
    methods_tab(),
    ui.nav_menu(
        "Contact Us",
        ui.nav_control(
            ui.a(
                "Our Website",
                href="https://borealbirds.ca/contact/",
                target="_blank",
            ),
        ),
        ui.nav_control(
            ui.a(
                "Email Us",
                href="mailto:bamp@ualberta.ca",
                target="_blank",
            ),
        ),
        ui.nav_control(
            ui.a(
                "Report an Issue",
                href="https://github.com/borealbirds/LandbirdModelsV5/issues",
                target="_blank",
            ),
        ),
    ),
    selected="Current Model",
    id="tabs",
    title=ui.tags.a(
        ui.tags.img(
            src="img/BAM-Logo-WhiteText.svg",
            alt="Boreal Avian Modelling Centre Dashboard",
            height="48"
        ),
        href="#",
    ),
    fillable=True,
    footer=FOOTER
)

def server(input: Inputs):

    # Register Model V5 outputs
    server_v5(input)

app = App(app_ui, server, static_assets=www_dir)