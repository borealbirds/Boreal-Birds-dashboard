"""
The various chart functions used throughout the project.
"""

import altair as alt
import requests
import polars as pl
from shiny import req

from shared import load_region_data, load_species_metadata, load_covariate_metadata, load_importance_data
from utils.data import select_covariate_file

REGION_DICT = load_region_data().rows_by_key(key="region", named=True, unique=True)

birds = load_species_metadata()
covariates = load_covariate_metadata()
importance = load_importance_data()

def population_altair(data, species) -> alt.Chart:
    """
    [@render_altair] Build a scatter plot of regional population totals with x-axis in symlog scale.

    Returns
    -------
    alt.Chart
        An Altair object plotting points alongside bootstrap variation bands.
    """

    df = data

    points = alt.Chart(df).mark_point(
        filled=True,
    ).encode(
        alt.X("population_estimate:Q")
            .title("Abundance (M males)")
            .scale(type="symlog"),
        alt.Y("region_name:N")
            .title(None)
            .sort(
                field="population_estimate",
                order="descending",
            )
            .axis(labelLimit=0),
        alt.Color(
            "country_name:N",
            legend=alt.Legend(title="Country")
        ),
    ).transform_calculate(
        region_name=f"{REGION_DICT}[datum.region].name_adj",
        country_name=f"{REGION_DICT}[datum.region].country"
    )

    nearest = alt.selection_point(
        nearest=True,
        on="pointerover",
        fields=["population_estimate"],
        empty=False
    )
    when_near = alt.when(nearest)

    highlight = points.mark_point(
        size=50,
        stroke="#153B40FF",
    ).encode(
        opacity=when_near.then(alt.value(1)).otherwise(alt.value(0))
    )

    rules = alt.Chart(df).mark_rule(
        color="#153B40FF",
    ).encode(
        x="population_estimate:Q",
        opacity=alt.when(nearest)
            .then(alt.value(0.5))
            .otherwise(alt.value(0)),
        tooltip=[
            alt.Tooltip("population_estimate:Q", title="Population Estimate"),
            alt.Tooltip("population_lower:Q", title="Lower Estimate"),
            alt.Tooltip("population_upper:Q", title="Upper Estimate"),
        ]
    ).add_params(nearest)

    error_bars = points.mark_rule().encode(
        x="population_lower:Q",
        x2="population_upper:Q",
    )

    return (points + error_bars + rules + highlight).properties(
        title=alt.Title(
            f"Regional Population Estimates for the {species}",
            subtitle="Intervals represent 5th and 95th percentile of the bootstrap distribution"
        ),
        width="container", height=750
    )


def density_altair(data, species)-> alt.Chart:
    """
    [@render_altair] Build a scatter plot mapping estimated male density indexes.

    Returns
    -------
    alt.Chart
        An Altair point graph displaying regional bird densities.
    """
    df = data

    points = alt.Chart(df).mark_point(
        filled=True,
    ).encode(
        alt.X("density_estimate:Q")
            .title("Density (males/ha)"),
        alt.Y("region_name:N")
            .title(None)
            .sort(
                field="density_estimate",
                order="descending",
            )
            .axis(labelLimit=0),
        alt.Color(
            "country_name:N",
            legend=alt.Legend(title="Country")
        ),
    ).transform_calculate(
        region_name=f"{REGION_DICT}[datum.region].name_adj",
        country_name=f"{REGION_DICT}[datum.region].country"
    )

    nearest = alt.selection_point(
        nearest=True,
        on="pointerover",
        fields=["density_estimate"],
        empty=False
    )
    when_near = alt.when(nearest)

    highlight = points.mark_point(
        size=50,
        stroke="#153B40FF",
    ).encode(
        opacity=when_near.then(alt.value(1)).otherwise(alt.value(0))
    )

    rules = alt.Chart(df).mark_rule(
        color="#153B40FF",
    ).encode(
        x="density_estimate:Q",
        opacity=alt.when(nearest)
            .then(alt.value(0.5))
            .otherwise(alt.value(0)),
        tooltip=[
            alt.Tooltip("density_estimate:Q", title="Density Estimate"),
            alt.Tooltip("density_lower:Q", title="Lower Estimate"),
            alt.Tooltip("density_upper:Q", title="Upper Estimate"),
        ]
    ).add_params(nearest)

    error_bars = points.mark_rule().encode(
        x="density_lower:Q",
        x2="density_upper:Q",
    )

    return (points + error_bars + rules + highlight).properties(
        title=alt.Title(
            f"Regional Density Estimates for {species}",
            subtitle="Intervals represent 5th and 95th percentile of the bootstrap distribution"
        ),
        width="container", height=750
    )


def covariate_chart(
    covariate,
    species,
    bcr
) -> alt.Chart:

    req(covariate, species, bcr) 

    # --- preprocessing ---

    bcr_selections = list(bcr)
    cov_name = covariates.filter(pl.col("variable") == covariate).item(0, "name")
    cov_description = covariates.filter(pl.col("variable") == covariate).item(0, "definition")


    # --- lookup ---
    bird_code = (
        birds
        .filter(pl.col("english") == species)
        .item(0, "id")
    )

    bird_name = (
        birds
        .filter(pl.col("english") == species)
        .item(0, "english")
    )

    covariate_code = (
        covariate
    )

    # --- file selection ---
    file_url, mode = select_covariate_file(covariate_code)

    # --- load data ---
    fx_df = pl.read_csv(file_url).filter(
        (pl.col("species") == bird_code) &
        (pl.col("bcr").is_in(bcr_selections))
    )

    # --- discrete (errorbars) ---
    if mode == "discrete":

        bar = alt.Chart(fx_df).mark_bar().encode(
            y=alt.Y("mean:Q", title="Marginal Effect on Predictions"),
            x=alt.X("label:N", title=f"Covariate: {cov_name} ({covariate_code})"),
            color="bcr",
            xOffset="bcr"
        ).properties(
            title=alt.TitleParams(
                text=f"{cov_name} vs Model Predictions",
                subtitle=f"Marginal effects of {cov_description} on predicted population for {bird_name}",
                anchor="start" # Aligns title to the left
            )
        )

        error = alt.Chart(fx_df).mark_errorbar().encode(
            x="label:N",
            y="lwr:Q",
            y2="upr:Q",
            color="bcr",
            xOffset="bcr"
        )

        chart = (bar + error).configure_title(
            fontSize=18,
            color="black",
            subtitleFontSize=12,
            subtitleColor="gray"
        )

    # --- continuous ---
    else:

        line = alt.Chart(fx_df).mark_line().encode(
            x=alt.X("x:Q", title=f"Covariate: {cov_name} ({covariate_code})"),
            y=alt.Y("fit:Q", title="Marginal Effect on Predictions"),
            color="bcr"
        ).properties(
            title=alt.TitleParams(
                text=f"{cov_name} vs Model Predictions",
                subtitle=f"Marginal effects of {cov_description} on predicted population for {bird_name}",
                anchor="start" # Aligns title to the left
            )
        )

        band = alt.Chart(fx_df).mark_errorband().encode(
            x="x:Q",
            y="lwr:Q",
            y2="upr:Q",
            color="bcr"
        )

        chart = (band + line).configure_title(
            fontSize=18,
            color="black",
            subtitleFontSize=12,
            subtitleColor="gray"
        )

    return chart.properties(
        width="container",
        height="container",
    )
