# a quick scrript to pull the species names from the list at URL

import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re

URL = "https://borealbirds.github.io/species/"

html = requests.get(URL, timeout=30).text
soup = BeautifulSoup(html, "html.parser")

rows = []

for h2 in soup.find_all("h2"):
    common_name = h2.get_text(strip=True)

    ### skip accidental non-species headings if any appear later
    if not common_name or common_name.lower() in {"species"}:
        continue

    detail = h2.find_next_sibling(string=True)
    if not detail:
        p = h2.find_next_sibling()
        detail = p.get_text(" ", strip=True) if p else ""

    detail = re.sub(r"\s+", " ", str(detail)).strip()

    ### French name · Scientific name · Family FamilyName
    parts = [p.strip() for p in detail.split("·")]
    scientific_name = parts[1] if len(parts) >= 2 else ""

    rows.append((common_name, scientific_name))

Path("species_common_names.txt").write_text(
    "\n".join(common for common, sci in rows) + "\n",
    encoding="utf-8"
)

Path("species_scientific_names.txt").write_text(
    "\n".join(sci for common, sci in rows if sci) + "\n",
    encoding="utf-8"
)

Path("species_bam_xc.tsv").write_text(
    "common_name\tscientific_name\n"
    + "\n".join(f"{common}\t{sci}" for common, sci in rows)
    + "\n",
    encoding="utf-8"
)

print(f"Saved {len(rows)} species.")
print("Created:")
print("- species_common_names.txt")
print("- species_scientific_names.txt")
print("- species_bam_xc.tsv")

