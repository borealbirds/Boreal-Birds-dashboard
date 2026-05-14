'''
A script to methodically download bird songs from the list in species_bam_xc.tsv file.
The main source is Xeno-Canto with a taxonomy check and iNaturalist fallback.
2 songs per species, download priority to <= 7s, then 10s, 15s, 20s. 
Change download settings in marked areas.
Run script and enter API from Xeno-Canto found here by signing up and 
verifying email: https://xeno-canto.org/explore/api. 
No API required for iNaturalist. 

Run:
  python download_xc_songs.py                   # fresh run
  python download_xc_songs.py --resume         # skip already-downloaded species
'''

import argparse
import csv
import json
import re
import time
import random
from pathlib import Path

import requests

# ── Settings ──────────────────────────────────────────────────────────
SPECIES_FILE             = "species_bam_xc.tsv"
OUTPUT_DIR               = Path("downloads")
SUMMARY_FILE             = Path("download_summary.txt")
NO_AUDIO_FILE            = Path("no_xc_audio.txt")
MAX_RECORDINGS           = 2              # n species for tiers <= 20s
MAX_RECORDINGS_LONG_TIER = 1             # n species for 25s-30s tiers

OUTPUT_DIR.mkdir(exist_ok=True)


# ── CLI ───────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument(
    "--resume",
    action="store_true",
    help="Skip species folders that already contain at least one .mp3 file.",
)
args = parser.parse_args()


# ── Helpers ───────────────────────────────────────────────────────────
def safe_filename(text):
    text = text.strip()
    text = re.sub(r"[^\w\s().-]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text


def scientific_to_xc_query(scientific_name):
    parts = scientific_name.split()
    if len(parts) < 2:
        return scientific_name
    return f"gen:{parts[0]} sp:{parts[1]} type:song"


def duration_to_seconds(duration):
    if not duration:
        return None
    parts = duration.strip().split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        return None
    return None


def quality_rank(q):
    return {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}.get(str(q).upper(), 99)


def species_already_downloaded(species_dir: Path) -> bool:
    """Return True if the folder exists and contains at least one .mp3."""
    return species_dir.is_dir() and any(species_dir.glob("*.mp3"))


# ── XC taxonomy lookup ────────────────────────────────────────────────
def lookup_xc_taxonomy(common_name: str, api_key: str) -> str | None:
    '''
    When gen:X sp:Y returns nothing, query XC by common English name and
    return the scientific name ("gen sp") that XC actually uses.

    XC search treats a bare word as a name match across English and
    scientific names, so querying the common name + type:song usually
    surfaces the correct IOC-taxonomy entry as the first result.
    '''
    params = {
        "query": f"en:{common_name} type:song",
        "key": api_key,
    }
    try:
        r = requests.get(
            "https://xeno-canto.org/api/3/recordings",
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        recordings = data.get("recordings", [])

        if not recordings:
            return None

        first = recordings[0]
        gen = first.get("gen", "").strip()
        sp  = first.get("sp",  "").strip()

        if gen and sp:
            corrected = f"{gen} {sp}"
            print(f"  [taxonomy] XC uses: {corrected}")
            return corrected

    except Exception as e:
        print(f"  [taxonomy lookup error] {e}")

    return None


# ── Recording selection ───────────────────────────────────────────────
def select_recordings_with_fallback(recordings, max_count=MAX_RECORDINGS):
    '''
    Select up to max_count recordings using tiered duration thresholds.

    Tiers ≤ 20s  →  up to MAX_RECORDINGS
    Tiers 25-30s →  up to MAX_RECORDINGS_LONG_TIER (only if ≤20s returned 0)
    Within each tier, sort by quality grade then duration (shortest first).
    '''
    valid = []
    for rec in recordings:
        secs = duration_to_seconds(rec.get("length"))
        if secs is None:
            continue
        rec["_duration_seconds"] = secs
        valid.append(rec)

    def sort_key(rec):
        return (quality_rank(rec.get("q")), rec.get("_duration_seconds", 9999))

    selected     = []
    selected_ids = set()
    tier_used    = []

    # ── Primary tiers (≤ 20s, up to MAX_RECORDINGS) ──────────────────
    primary_tiers = [
        (7,  "under 7s preferred"),
        (10, "under 10s fallback"),
        (15, "under 15s fallback"),
        (20, "under 20s fallback"),
    ]

    for max_secs, label in primary_tiers:
        matches = sorted(
            [r for r in valid if r["_duration_seconds"] <= max_secs
             and r.get("id") not in selected_ids],
            key=sort_key,
        )
        for rec in matches:
            if len(selected) >= max_count:
                break
            selected.append(rec)
            selected_ids.add(rec.get("id"))
            if label not in tier_used:
                tier_used.append(label)

        if len(selected) >= max_count:
            break

    if selected:
        return selected, " + ".join(tier_used)

    # ── Extended tiers (25s / 30s, cap at MAX_RECORDINGS_LONG_TIER) ──
    extended_tiers = [
        (25, "under 25s extended (1 max)"),
        (30, "under 30s extended (1 max)"),
    ]

    for max_secs, label in extended_tiers:
        matches = sorted(
            [r for r in valid if r["_duration_seconds"] <= max_secs
             and r.get("id") not in selected_ids],
            key=sort_key,
        )
        for rec in matches:
            if len(selected) >= MAX_RECORDINGS_LONG_TIER:
                break
            selected.append(rec)
            selected_ids.add(rec.get("id"))
            if label not in tier_used:
                tier_used.append(label)

        if len(selected) >= MAX_RECORDINGS_LONG_TIER:
            break

    if selected:
        return selected, " + ".join(tier_used)

    return [], "no recordings under 30s"


# ── iNaturalist fallback ──────────────────────────────────────────────
INAT_API = "https://api.inaturalist.org/v1"

def fetch_inat_recordings(scientific_name: str) -> list[dict]:
    '''
    Query iNaturalist for sound observations of a species.
    Returns a list of dicts with keys: file_url, duration_seconds, quality,
    id, source (always "iNaturalist").

    iNat doesn't expose duration in the search API, so we fetch up to 20
    observations and filter those with a sounds array.
    '''
    try:
        r = requests.get(
            f"{INAT_API}/observations",
            params={
                "taxon_name": scientific_name,
                "sounds":     "true",
                "quality_grade": "research",
                "per_page":   20,
                "order_by":   "votes",
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  [iNat API error] {e}")
        return []

    results = []
    for obs in data.get("results", []):
        for sound in obs.get("sounds", []):
            file_url = sound.get("file_url") or sound.get("file")
            if not file_url:
                continue
            results.append({
                "id":               f"inat_{obs.get('id')}_{sound.get('id')}",
                "file_url":         file_url,
                "duration_seconds": None,       # iNat doesn't expose duration here
                "quality":          "iNat-research",
                "source":           "iNaturalist",
                "obs_url":          f"https://www.inaturalist.org/observations/{obs.get('id')}",
                "recordist":        obs.get("user", {}).get("login", "unknown"),
                "date":             obs.get("observed_on", ""),
                "country":          obs.get("place_guess", ""),
            })

    return results


def download_inat_fallback(
    scientific_name: str,
    common_name: str,
    species_dir: Path,
) -> list[dict]:
    '''
    Attempt to download up to MAX_RECORDINGS_LONG_TIER recordings from
    iNaturalist for species that returned nothing from XC.
    '''
    print(f"  [iNat fallback] Querying iNaturalist for {scientific_name} …")
    candidates = fetch_inat_recordings(scientific_name)

    if not candidates:
        print("  [iNat fallback] No results.")
        return []

    print(f"  [iNat fallback] Found {len(candidates)} candidates.")
    saved = []

    for i, rec in enumerate(candidates[:MAX_RECORDINGS_LONG_TIER], start=1):
        file_url = rec["file_url"]
        rec_id   = rec["id"]
        filename = f"inat_{i}_{rec_id}.mp3"
        outpath  = species_dir / filename

        try:
            audio = requests.get(file_url, timeout=120)
            audio.raise_for_status()
            outpath.write_bytes(audio.content)

            metadata = {
                "bam_common_name":      common_name,
                "bam_scientific_name":  scientific_name,
                "source":               "iNaturalist",
                "inat_id":              rec_id,
                "recordist":            rec["recordist"],
                "country":              rec["country"],
                "date":                 rec["date"],
                "duration_seconds":     rec["duration_seconds"],
                "quality":              rec["quality"],
                "inat_url":             rec["obs_url"],
                "audio_url":            file_url,
                "local_audio_file":     filename,
                "selection_mode":       "iNaturalist fallback",
            }

            meta_path = species_dir / f"inat_{i}_{rec_id}_metadata.json"
            meta_path.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            saved.append({
                "filename":         filename,
                "duration_seconds": rec["duration_seconds"],
                "quality":          rec["quality"],
                "recording_id":     rec_id,
            })

            print(f"  [iNat] Saved {filename}")
            time.sleep(random.uniform(1.0, 2.5))

        except Exception as e:
            print(f"  [iNat download error] {e}")

    return saved


# ── Load species list ─────────────────────────────────────────────────
def load_species_rows(path):
    rows = []
    with Path(path).open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            common     = row.get("common_name", "").strip()
            scientific = row.get("scientific_name", "").strip()
            if common and scientific:
                rows.append({"common_name": common, "scientific_name": scientific})
    return rows


# ── Main ──────────────────────────────────────────────────────────────
API_KEY = input("Paste your Xeno-canto API key: ").strip()
if not API_KEY:
    raise RuntimeError("No API key provided.")
print("\nAPI key received.\n")

species_rows = load_species_rows(SPECIES_FILE)
print(f"Loaded {len(species_rows)} species.\n")

if args.resume:
    print("--resume active: skipping species with existing downloads.\n")

summary_rows               = []
species_without_recordings = []
skipped_count              = 0
taxonomy_corrections       = {}   # original → corrected scientific name


for species_info in species_rows:
    common_name     = species_info["common_name"]
    scientific_name = species_info["scientific_name"]

    folder_name  = f"{safe_filename(common_name)}_({safe_filename(scientific_name)})"
    species_dir  = OUTPUT_DIR / folder_name
    species_dir.mkdir(exist_ok=True)

    # ── Resume check ─────────────────────────────────────────────────
    if args.resume and species_already_downloaded(species_dir):
        print(f"[skip] {common_name} — already downloaded.")
        skipped_count += 1
        continue

    print(f"\n=== {common_name} ({scientific_name}) ===")

    # ── Query XC ─────────────────────────────────────────────────────
    query  = scientific_to_xc_query(scientific_name)
    params = {"query": query, "key": API_KEY}

    try:
        r = requests.get(
            "https://xeno-canto.org/api/3/recordings",
            params=params,
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"API ERROR: {e}")
        species_without_recordings.append(
            f"{common_name} ({scientific_name}) - API error"
        )
        continue

    recordings = data.get("recordings", [])

    # ── Taxonomy fallback: query by common name ───────────────────────
    if not recordings:
        print("  No results with BAM scientific name — trying taxonomy lookup …")
        corrected = lookup_xc_taxonomy(common_name, API_KEY)

        if corrected and corrected.lower() != scientific_name.lower():
            taxonomy_corrections[scientific_name] = corrected
            query  = scientific_to_xc_query(corrected)
            params = {"query": query, "key": API_KEY}

            try:
                r = requests.get(
                    "https://xeno-canto.org/api/3/recordings",
                    params=params,
                    timeout=60,
                )
                r.raise_for_status()
                data       = r.json()
                recordings = data.get("recordings", [])
                if recordings:
                    print(f"  Taxonomy fix worked ({corrected}): "
                          f"{len(recordings)} recordings found.")
                    scientific_name = corrected   # use corrected name going forward
            except Exception as e:
                print(f"  Retry error: {e}")

    # ── Select recordings ─────────────────────────────────────────────
    selected_recordings = []
    selection_mode      = ""
    source              = "XC"

    if recordings:
        selected_recordings, selection_mode = select_recordings_with_fallback(recordings)

    # ── iNaturalist fallback ──────────────────────────────────────────
    if not selected_recordings:
        inat_saved = download_inat_fallback(scientific_name, common_name, species_dir)

        if inat_saved:
            summary_rows.append({
                "common_name":    common_name,
                "scientific_name": scientific_name,
                "count":          len(inat_saved),
                "selection_mode": "iNaturalist fallback",
                "recordings":     inat_saved,
            })
        else:
            species_without_recordings.append(
                f"{common_name} ({scientific_name}) - no audio found on XC or iNaturalist"
            )
        continue

    print(
        f"Found {len(recordings)} XC recordings. "
        f"Using {selection_mode}. "
        f"Downloading {len(selected_recordings)}."
    )

    # ── Download XC audio ─────────────────────────────────────────────
    saved_recordings = []

    for i, rec in enumerate(selected_recordings, start=1):
        file_url = rec.get("file")
        if not file_url:
            continue
        if file_url.startswith("//"):
            file_url = "https:" + file_url

        rec_id     = rec.get("id", "unknown")
        quality    = rec.get("q", "unknown")
        length     = rec.get("length", "unknown")
        safe_len   = str(length).replace(":", "-")
        filename   = f"{i}_{rec_id}_q{quality}_{safe_len}.mp3"
        outpath    = species_dir / filename

        try:
            audio = requests.get(file_url, timeout=120)
            audio.raise_for_status()
            outpath.write_bytes(audio.content)

            metadata = {
                "bam_common_name":          common_name,
                "bam_scientific_name":      species_info["scientific_name"],
                "xeno_canto_scientific_name": f'{rec.get("gen")} {rec.get("sp")}',
                "taxonomy_corrected":       scientific_name != species_info["scientific_name"],
                "xeno_canto_recording_id":  rec.get("id"),
                "xeno_canto_english_name":  rec.get("en"),
                "recordist":                rec.get("rec"),
                "country":                  rec.get("cnt"),
                "location":                 rec.get("loc"),
                "date":                     rec.get("date"),
                "length":                   rec.get("length"),
                "duration_seconds":         rec.get("_duration_seconds"),
                "quality":                  rec.get("q"),
                "type":                     rec.get("type"),
                "license":                  rec.get("lic"),
                "xeno_canto_url":           f'https://xeno-canto.org/{rec.get("id")}',
                "audio_url":                file_url,
                "local_audio_file":         filename,
                "selection_mode":           selection_mode,
            }

            meta_path = species_dir / f"{i}_{rec_id}_metadata.json"
            meta_path.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            saved_recordings.append({
                "filename":         filename,
                "length":           rec.get("length"),
                "duration_seconds": rec.get("_duration_seconds"),
                "quality":          rec.get("q"),
                "recording_id":     rec.get("id"),
            })

            print(f"  Saved {filename}")
            time.sleep(random.uniform(1.0, 2.5))

        except Exception as e:
            print(f"  DOWNLOAD ERROR: {e}")

    if saved_recordings:
        summary_rows.append({
            "common_name":     common_name,
            "scientific_name": scientific_name,
            "count":           len(saved_recordings),
            "selection_mode":  selection_mode,
            "recordings":      saved_recordings,
        })
    else:
        species_without_recordings.append(
            f"{common_name} ({scientific_name}) - download failed"
        )


# ── Summary file ──────────────────────────────────────────────────────
lines = [
    "Xeno-canto Download Summary",
    "=" * 40,
    f"Species attempted:              {len(species_rows)}",
    f"Species skipped (--resume):     {skipped_count}",
    f"Species with audio downloaded:  {len(summary_rows)}",
    f"Species without audio:          {len(species_without_recordings)}",
    "",
]

if taxonomy_corrections:
    lines += [
        "Taxonomy corrections applied",
        "-" * 40,
    ]
    for original, corrected in taxonomy_corrections.items():
        lines.append(f"  {original}  →  {corrected}")
    lines.append("")

lines += ["Downloaded recordings by species", "-" * 40]

for row in summary_rows:
    lines.append(
        f"{row['common_name']} ({row['scientific_name']}) "
        f"- {row['count']} recording(s), {row['selection_mode']}"
    )
    for rec in row["recordings"]:
        dur = rec.get("duration_seconds")
        dur_str = f"{dur}s" if dur else "dur unknown"
        lines.append(
            f"  - {rec.get('length', '?')} ({dur_str}), "
            f"quality {rec['quality']}, "
            f"ID {rec['recording_id']}"
        )
    lines.append("")

lines += ["", "Species without audio", "-" * 40]
if species_without_recordings:
    for item in species_without_recordings:
        lines.append(f"- {item}")
else:
    lines.append("None")

SUMMARY_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
NO_AUDIO_FILE.write_text(
    "\n".join(
        f"- {item}" for item in species_without_recordings
    ) + "\n",
    encoding="utf-8",
)

print(f"\nDONE. Summary: {SUMMARY_FILE}  |  No-audio list: {NO_AUDIO_FILE}\n")