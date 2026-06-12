"""
Landbirds Version 4 historical model placeholder view template.

Acts as a structural interface mirror for legacy metrics, providing the 
front-end layout panels for future backend server wiring sprints.
"""

from shiny import ui
from shinywidgets import output_widget
from ui.sidebar import sidebar
from icons import question_circle_fill

def landbirds_v4_tab():
    """
    Build the interface shell layout for the historical Version 4 model tab.

    Constructs a template layout matching the current application theme 
    using static placeholder text content nodes pending programmatic data hookups.

    Returns
    -------
    NavPanel
        The template layout panel object mapping future navigation structures.
    """
    return ui.nav_panel(
        "Landbirds v4 (Historical)",
        ui.layout_sidebar(
            sidebar("v4"),

            # ── Bird header placeholder ────────────────────────────────
            ui.div(
                ui.div(
                    ui.span("Select a species", class_="bird-name"),
                    ui.span("Sélectionner une espèce", class_="bird-french"),
                    class_="bird-names",
                ),
                ui.div(
                    ui.input_radio_buttons(
                        "view_toggle_v4",
                        None,
                        choices={"map": "Map", "info": "Info"},
                        selected="map",
                        inline=True,
                    ),
                    class_="toggle-wrapper",
                ),
                class_="bird-header-row",
            ),

            # ── MAP view ───────────────────────────────────────────────
            ui.panel_conditional(
                "input.view_toggle_v4 === 'map'",
                ui.navset_card_underline(
                    ui.nav_spacer(),
                    ui.nav_panel("Map",         ui.p("Historical map — coming soon.")),
                    ui.nav_panel("Land Cover",  ui.p("Land cover — coming soon.")),
                    ui.nav_panel("Population",  ui.p("Population — coming soon.")),
                    ui.nav_panel("Density",     ui.p("Density — coming soon.")),
                    ui.nav_panel("Download",    ui.p("Download — coming soon.")),
                    title=ui.tooltip(
                        ui.span("Model Results ", question_circle_fill),
                        "Population size (M males) is based on summing up predictive maps by regions.",
                        placement="right",
                        id="results_tooltip_v4",
                    ),
                ),
            ),

            # ── INFO view ──────────────────────────────────────────────
            ui.panel_conditional(
                "input.view_toggle_v4 === 'info'",
                ui.navset_card_underline(
                    ui.nav_panel("Info",   ui.p("Species info — coming soon.")),
                    ui.nav_panel("Images", ui.p("Images — coming soon.")),
                    ui.nav_panel("Songs",  ui.p("Songs — coming soon.")),
                    title="Species Info",
                ),
            ),
        )
    )