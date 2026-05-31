from shiny import ui

def vignette_panel(src, title):
    return ui.nav_panel(
        title,
        ui.tags.iframe(
            src=src,
            style="""
                width:100%;
                height:calc(100vh - 140px);
                border:none;
                display:block;
            """
        )
    )

def model_access_tab():
    return ui.nav_panel(
        "Model Access",
        ui.navset_tab(
            vignette_panel("vignettes/BAMexploreR_1_intro.html", "Intro"),
            vignette_panel("vignettes/BAMexploreR_2_access.html", "Access"),
            vignette_panel("vignettes/BAMexploreR_3_distribution.html", "Distribution"),
            vignette_panel("vignettes/BAMexploreR_4_habitat.html", "Habitat"),
        )
    )