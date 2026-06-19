"""
Announcements that are be displayed only when necessary.

Generates a card that can be turned on or off.
"""

from shiny import ui

from shared.data_loading import read_md
from shared.paths import content_dir


def announcements_card(display: bool = False, file: str = "announcements.md") -> ui.card:
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
    path = content_dir() / file

    if display & path.exists() & bool(path.read_text(encoding="utf-8").strip()):
        return ui.card(
            ui.card_header("Announcements"),
            ui.markdown(read_md(file)),
            fill=False,
            class_="announcement-card",
        )
    else:
        return None
