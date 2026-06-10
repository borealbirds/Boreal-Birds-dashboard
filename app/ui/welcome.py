from pathlib import Path

from shiny import ui

from shared import read_md

def _announcement_card(display: bool = False, file: str = "announcements.md"):
    """
    Conditional UI card for announcements. Checks that the file exists and is not empty.

    Parameters
    ----------
    display : bool, optional
        Whether to display the announcements card. Set to True to show announcements and False to hide.
    file : str, optional
        Filename of the announcements markdown in the contents directory.
        
    Returns
    -------
    shiny.ui
    """
    path = Path(__file__).parent.parent / "content" / file

    if display & path.exists() & bool(path.read_text(encoding="utf-8").strip()):
        return ui.card(
            ui.card_header("Announcements"),
            ui.markdown(read_md(file)),
            fill=False,
            class_="announcement-card",
        )
    else:
        return None


def welcome_tab():
    """UI for the welcome tab, including announcements and project overview."""
    return ui.nav_panel(
        "Welcome",
        ui.div(
            {"id": "welcome-panel"},
            ui.layout_columns(
                _announcement_card(display=True),
                ui.card(
                    ui.card_header("A Boreal Avian Modelling Project"),
                    ui.markdown(read_md("welcome.md")),
                    class_="welcome-card"
                ),
                col_widths=(
                    -1, 10, -1, # announcement card
                    -1, 10, -1, # welcome card
                ),
                row_heights=["auto", 1]
            ),
        ),
    )
