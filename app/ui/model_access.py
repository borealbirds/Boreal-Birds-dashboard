from shiny import ui

def vignette_panel(title, src, width="100%", height="100%"):
    return ui.nav_panel(
        title,
        ui.tags.iframe(
            src=src,
            width=width,
            height=height,
            style="border:none; display:block;"
        )
    )

def model_access_tab():
    return ui.nav_panel(
        "Model Access",
        ui.layout_columns(
            ui.navset_card_underline(
                ui.nav_spacer(),
                vignette_panel("Introduction", "vignettes/BAMexploreR_1_intro.html"),
                vignette_panel("Access", "vignettes/BAMexploreR_2_access.html"),
                vignette_panel("Distribution", "vignettes/BAMexploreR_3_distribution.html"),
                vignette_panel("Habitat", "vignettes/BAMexploreR_4_habitat.html"),
                ),
            col_widths=(-1, 10, -1),
            ),
        )