from shiny import ui

def bird_card(species, common_name, french_name, family, image_url):
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
                    ui.h4("Population Size"),
                    ui.div(ui.strong("Canada "), ui.em("Placeholder")),
                    ui.div(ui.strong("Alaska "), ui.em("Placeholder")),
                    ui.div(ui.strong("Lower 48 (US) "), ui.em("Placeholder")),
                ),
            ),
        ),
        class_="bird-card"
    )