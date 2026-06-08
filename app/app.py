from pathlib import Path

from shiny import App, Inputs, Outputs, Session, ui

from components import audio, footer, website, website_contact
from server.server_v5 import server_v5
from ui.methods import methods_tab
from ui.model_v4 import model_v4_tab
from ui.model_v5 import model_v5_tab
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
        model_v5_tab(),
        model_v4_tab(),
    ),
    ui.nav_menu(
        "Model Access",
        tools_tab(),
        vignettes_tab(),
        citing_tab(),
    ),
    methods_tab(),
    ui.nav_menu(
        "Contact Us",
        website(),
        website_contact(),
    ),
    selected="Current Model",
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


def server(input: Inputs, output: Outputs, session: Session):
    """Registers model outputs."""
    server_v5(input, output, session)


app = App(app_ui, server, static_assets=www_dir)