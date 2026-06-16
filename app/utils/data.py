import requests

def select_covariate_file(covariate_code: str) -> tuple[str, str]:

    base = f"https://cloud.borealbirds.ca/dashboard/Predictors/{covariate_code}"

    continuous_url = f"{base}_gampredictions.csv"
    discrete_url = f"{base}_errorbars.csv"

    try:
        r = requests.head(continuous_url, timeout=2)
        if r.status_code == 200:
            return continuous_url, "continuous"
    except Exception:
        pass

    return discrete_url, "discrete"