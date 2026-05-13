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

app_ui = ui.page_navbar(
    ui.head_content(ui.include_css(str(www_dir / "styles.css"))),
    ui.nav_spacer(),
    welcome_tab(),
    model_v5_tab(),
    model_v4_tab(),
    methods_tab(),
    model_access_tab(),
    ui.nav_control(
        ui.a(
            "Contact",
            href="https://borealbirds.ca/contact/",
            target="_blank",
            class_="contact-link"
        ),
    ),
    sidebar=sidebar(),
    selected="Current Model", # for during development phases
    id="tabs",
    title="Boreal Birds Dashboard",
    fillable=True,
)

def server(input: Inputs):

    # Register Model V5 outputs
    server_v5(input)

app = App(app_ui, server, static_assets=www_dir)