from shiny import ui

from shared import read_md

def _announcement_card(display: bool = False):
    """
    Conditional UI card for announcements.

    Parameters
    ----------
    display : bool
        Whether to display the announcements card. Set to True to show announcements and False to hide.
    
    Returns
    -------
    shiny.ui
    """
    if display:
        return ui.card(
            ui.card_header("Announcements"),
            ui.markdown(read_md("announcements.md")),
            fill=False,
            class_="announcement-card",
        )
    else:
        return None


def welcome_tab():
    """UI for the welcome tab, including announcements and project overview."""
    return ui.nav_panel(
        "Welcome",
        ui.layout_columns(
            _announcement_card(display=True),
            ui.card(
                ui.card_header("A Boreal Avian Modelling Project", style="font-size:1.25rem"),
                ui.markdown(read_md("welcome.md")),
                class_="welcome-card"
            ),
            col_widths=(
                -1, 10, -1, # announcement card
                -1, 10, -1, # welcome card
            ),
            row_heights=["auto", 1]
        ),
    )