from pathlib import Path

from tabs.about import about_tab
from tabs.model_v4 import model_v4_tab
from tabs.model_v5 import model_v5_tab
from tabs.methods import methods_tab
from server.server_v5 import server_v5

from sidebar import sidebar

import polars as pl
from shiny import App, Inputs, reactive, render, ui

from content.methods_content import methods_sections

www_dir = Path(__file__).parent / "www"

app_ui = ui.page_navbar(
    ui.head_content(ui.include_css(str(www_dir / "styles.css"))),
    ui.nav_spacer(),
    model_v5_tab(),
    model_v4_tab(),
    methods_tab(),
    about_tab(),
    sidebar=sidebar(),
    id="tabs",
    title="Boreal Birds Dashboard",
    fillable=True,
)

def server(input: Inputs):

    # Register Model V5 outputs
    server_v5(input)

img_dir = Path(__file__).parent / "img"

app = App(app_ui, server, static_assets=www_dir)