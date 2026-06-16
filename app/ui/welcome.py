"""
Welcome tab layout and announcement sub-components for the dashboard.

Constructs the landing interface view, pulling text content and dynamic 
updates out of localized markdown utility assets.
"""
from pathlib import Path

from shiny import ui

from shared import read_md

def _announcement_card(display: bool = False, file: str = "announcements.md") -> ui.card | None:
    """
    Render a conditional UI card containing recent project announcements.

    Verifies the toggle state, confirms file existence, and checks that 
    the text payload is not empty before rendering.

    Parameters
    ----------
    display : bool, default False
        Global toggle switch to show (True) or hide (False) the block.
    file : str, default "announcements.md"
        Target file name located within the app content directory.

    Returns
    -------
    Card or None
        A populated UI card container element, or None if conditions fail.
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


def welcome_tab() -> ui.nav_panel:
    """
    Build the primary interface landing tab panel layout view.

    Returns
    -------
    NavPanel
        The completed layout container housing cards and project briefs.
    """
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
