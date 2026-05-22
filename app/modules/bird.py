from shiny import ui

from icons import question_circle_fill

def bird_card(species, common_name, french_name, family, image_url, canada_pop, alaska_pop, lower48_pop):
    return ui.card(
        ui.card_body(
            ui.row(
                ui.column(2, ui.tags.img(src=image_url, alt=f"{common_name} Image",class_="bird-image")),
                ui.column(4,
                    ui.h4(common_name),
                    ui.h6(french_name),
                    ui.div(ui.strong("Species "), ui.em(species)),
                    ui.div(ui.strong("Family "), family),
                ),
                ui.column(5,
                    ui.h4(
                        ui.tooltip(
                        ui.span("Population Estimates ", question_circle_fill),
                        "in Million males",
                        placement="right",
                        )
                    ),
                    ui.div(ui.strong("Canada "), f"{canada_pop}"),
                    ui.div(ui.strong("Alaska "), f"{alaska_pop}"),
                    ui.div(ui.strong("Lower 48 (US) "), f"{lower48_pop}"),
                ),
            ),
        ),
        class_="bird-card"
    )