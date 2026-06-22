"""
UI layout components for the BAM dashboard.

Provides reusable navigation controls, footer licensing blocks, and other
future layout components.
"""

from shiny import ui


def footer() -> ui.tags:
    """
    Render the copyright disclosure and Creative Commons usage policy wrapper.

    Returns
    -------
    shiny.ui.Tag
        A bottom-anchored content div element styled with appropriate CSS rules.
    """
    return ui.div(
        ui.HTML(
            '&copy; 2026 '
            '<a href="https://borealbirds.ca/" target="_blank">Boreal Avian Modelling Project </a>'
            'under a '
            '<a href="https://creativecommons.org/licenses/by-sa/4.0/", target="_blank"> CC BY-SA 4.0 license </a>'
        ),
        class_="footer"
    )
