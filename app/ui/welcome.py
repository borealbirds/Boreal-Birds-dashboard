from shiny import ui

def welcome_tab():

    return ui.nav_panel(
        "Welcome",
        ui.card(
            ui.card_header("Boreal Bird Species Results", style="font-size:1.25rem"),
            ui.p("A Boreal Avian Modelling Project"),
            ui.p("Explore population sizes, habitat associations, and distributions for status assessment, " \
            "regional planning, conservation prioritization, and recovery of species at risk."),
            ui.p("We developed a generalized analytical approach to model species density in relation to environmental covariates, using the Boreal Avian Modelling Project database of point-count surveys."),
            ui.p("Source code for the methodology is available on GitHub."),
            ui.p("Download results in Excel (xlsx) format (version May 2025)."),
            ui.p("Please note, in late March 2025, we discovered a systematic error in the offsets used in these models, and have since updated the products to correct that error. For more information, please see the QPAD-offsets-correction repository or email bamp@ualberta.ca."),
            ui.p("Stralberg, D., Sólymos, P., Docherty, T. D. S., Crosby, A. D., Van Wilgenburg, S. L., Knight, E. C., Drake, A., Boehm, M. M. A., Haché, S., Leston, L., Toms, J. D., Ball, J. R., Song, S. J., Schmiegelow, F. K. A., Cumming, S. C., Bayne, E. M., 2025. A generalized modeling framework for spatially extensive species abundance prediction and population estimation. Ecosphere, in press."),
            ui.p("Sólymos, P., D. Stralberg, and E. C. Knight. 2025. BAM Generalized National Models Documentation (Version 4.0) [Data set]. Zenodo, DOI: 10.5281/zenodo.4018335."),
            class_="welcome-card"
        ),
    )