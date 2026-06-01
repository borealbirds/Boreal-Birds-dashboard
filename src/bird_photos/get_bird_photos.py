"""
Targeted photo fix script for Boreal Birds dashboard.

Handles:
  1. Species with no photos       → fresh download
  2. Species with wrong photos    → wipe folder and re-download
  3. CAJA folder rename           → Grey_Jay → Canada_Jay
  4. Cross-species duplicate detection (by iNat photo ID in metadata)

Usage (run from project root):
  python src/bird_photos/fix_bird_photos.py            # fix + detect dupes
  python src/bird_photos/fix_bird_photos.py --dupes-only   # only report dupes
"""

import argparse
import csv
import json
import shutil
import time
import random
from pathlib import Path
from collections import defaultdict

import requests
import openpyxl

# ── Paths (same as download_bird_photos.py) ────────────────────────────
_SCRIPT_DIR   = Path(__file__).parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
SPECIES_FILE  = _PROJECT_ROOT / "src" / "bird_songs" / "docs" / "species_bam.tsv"
EXCEL_FILE    = _PROJECT_ROOT / "src" / "bird_songs" / "docs" / "12_BAMV5-results_noabundance.xlsx"
OUTPUT_DIR    = _PROJECT_ROOT / "app" / "img"

MB = 1024 * 1024; KB = 1024
INAT_API       = "https://api.inaturalist.org/v1"
MAX_PER_SEX    = 5
SIZE_CAP       = int(1.5 * MB)
INAT_SIZES     = ["medium", "large", "original"]
TERM_SEX = 9; TERM_MALE = 10; TERM_FEMALE = 11

# ── Species to fix ─────────────────────────────────────────────────────
NO_PHOTOS = {          # species_code: common_name (as in TSV)
    "BWWA": "Blue-winged Warbler",
    "CAJA": "Canada Jay",
    "DUNL": "Dunlin",
    "RBWO": "Red-bellied Woodpecker",
    "RHWO": "Red-headed Woodpecker",
    "ROSA": "Rock Sandpiper",
    "SPGR": "Spruce Grouse",
    "WITU": "Wild Turkey",
}

WRONG_PHOTOS = {       # wipe and re-download
    "BANS": "Bank Swallow",
    "VEER": "Veery",
    "WIPT": "Willow Ptarmigan",
}

# ── Session ────────────────────────────────────────────────────────────
session = requests.Session()
session.headers.update({"User-Agent": "BorealBirds-Dashboard/1.0"})

# ── Helpers (copied from original script) ──────────────────────────────
def load_id_lookup():
    if not EXCEL_FILE.exists():
        return {}
    try:
        wb      = openpyxl.load_workbook(EXCEL_FILE, read_only=True, data_only=True)
        ws      = wb["species"]
        rows    = list(ws.iter_rows(values_only=True))
        wb.close()
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        id_idx  = headers.index("id")
        en_idx  = headers.index("english")
        sci_idx = headers.index("scientific")
        min_len = max(id_idx, en_idx, sci_idx) + 1
        result = {}
        for row in rows[1:]:
            if len(row) >= min_len and row[id_idx] and row[en_idx]:
                result[str(row[en_idx]).strip()] = {
                    "id":         str(row[id_idx]).strip(),
                    "scientific": str(row[sci_idx]).strip() if row[sci_idx] else "",
                }
        return result
    except Exception as e:
        print(f"  [warn] Could not load Excel: {e}")
        return {}

def load_scientific_from_tsv(common_name: str) -> str:
    """Look up scientific name in TSV by common name."""
    ALIASES = {"Canada Jay": "Gray Jay", "Gray Jay": "Canada Jay"}
    try:
        with SPECIES_FILE.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                name = row.get("common_name", "").strip()
                if name == common_name or name == ALIASES.get(common_name, ""):
                    return row.get("scientific_name", "").strip()
    except Exception:
        pass
    return ""

def get_annotations(obs):
    result = {}
    for ann in obs.get("annotations", []):
        attr = ann.get("controlled_attribute", {}).get("label", "")
        val  = ann.get("controlled_value", {}).get("label", "")
        if attr and val:
            result[attr] = val
    return result

def inat_search(scientific_name, per_page=50, sex_term_value=None):
    params = {
        "taxon_name":    scientific_name,
        "photos":        "true",
        "quality_grade": "research",
        "captive":       "false",
        "per_page":      per_page,
        "order_by":      "observed_on",
    }
    if sex_term_value is not None:
        params["term_id"]       = TERM_SEX
        params["term_value_id"] = sex_term_value
    try:
        r = session.get(f"{INAT_API}/observations", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  [iNat error] {e}")
        return []

    photos = []
    seen   = set()
    OUTLIER = {"albino","leucistic","leucism","xanthochroism","melanistic",
               "partial albino","colour morph","color morph","white morph"}
    for obs in data.get("results", []):
        ann        = get_annotations(obs)
        life_stage = ann.get("Life Stage", "")
        alive_dead = ann.get("Alive or Dead", "")
        if life_stage and life_stage != "Adult": continue
        if alive_dead and alive_dead != "Alive": continue
        desc = (obs.get("description") or "").lower()
        tags = " ".join(obs.get("tags", [])).lower()
        if any(t in desc + " " + tags for t in OUTLIER): continue
        obs_url  = f"https://www.inaturalist.org/observations/{obs.get('id')}"
        obs_date = obs.get("observed_on", "")
        user     = obs.get("user", {}).get("login", "")
        for photo in obs.get("photos", []):
            pid = photo.get("id")
            if pid in seen: continue
            seen.add(pid)
            photos.append({
                "id":          pid,
                "square_url":  photo.get("url", ""),
                "attribution": photo.get("attribution", ""),
                "license":     photo.get("license_code", ""),
                "obs_url":     obs_url,
                "obs_date":    obs_date,
                "user":        user,
            })
    return photos

def select_url(photo):
    for size in INAT_SIZES:
        url = photo["square_url"].replace("square", size)
        if not url: continue
        if size == "original":
            try:
                r = session.head(url, timeout=10, allow_redirects=True)
                length = r.headers.get("Content-Length")
                if length and int(length) >= SIZE_CAP: continue
            except Exception:
                continue
        return url, (150*KB if size == "medium" else 450*KB if size == "large" else 800*KB)
    return None

def download_species(species_code, common_name, scientific_name, wipe=False):
    safe      = common_name.replace(" ", "_")
    folder    = OUTPUT_DIR / f"{species_code}_{safe}"
    folder.mkdir(parents=True, exist_ok=True)

    if wipe:
        for f in folder.iterdir():
            f.unlink()
        print(f"  Wiped {folder.name}")

    photo_count = 0
    all_saved   = []

    for sex_label, sex_term in [("male", TERM_MALE), ("female", TERM_FEMALE)]:
        photos = inat_search(scientific_name, per_page=50, sex_term_value=sex_term)
        if not photos:
            genus = scientific_name.split()[0]
            print(f"  [{sex_label}] No results — trying genus '{genus}'...")
            photos = inat_search(genus, per_page=30, sex_term_value=sex_term)
        if not photos:
            print(f"  [{sex_label}] No annotated photos found.")
            continue

        print(f"  [{sex_label}] {len(photos)} candidates")
        saved = []
        for photo in photos:
            if len(saved) >= MAX_PER_SEX: break
            result = select_url(photo)
            if not result: continue
            url, size_bytes = result
            photo_count += 1
            filename = f"{photo_count}_{photo['id']}.jpg"
            outpath  = folder / filename
            try:
                img = session.get(url, timeout=60)
                img.raise_for_status()
                outpath.write_bytes(img.content)
                meta = {
                    "common_name": common_name, "scientific_name": scientific_name,
                    "sex": sex_label, "life_stage": "adult", "captive": False,
                    "photo_id": photo["id"], "attribution": photo.get("attribution",""),
                    "license": photo.get("license",""), "obs_url": photo.get("obs_url",""),
                    "obs_date": photo.get("obs_date",""), "recorded_by": photo.get("user",""),
                    "download_url": url, "size_kb": round(size_bytes/KB, 1), "local_file": filename,
                }
                (folder / f"{photo_count}_{photo['id']}_metadata.json").write_text(
                    json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
                saved.append(filename)
                print(f"    ✓ {filename}  ({sex_label}, {size_bytes/KB:.0f} KB)")
                time.sleep(random.uniform(0.5, 1.2))
            except Exception as e:
                print(f"    ✗ Download error: {e}")
        all_saved.extend(saved)

    if not all_saved:
        print(f"  ⚠ No photos saved for {common_name}")
    return all_saved


def fix_caja_folder():
    """Rename Grey_Jay folder to CAJA_Canada_Jay if needed."""
    grey_variants = ["CAJA_Grey_Jay", "CAJA_Gray_Jay", "Grey_Jay", "Gray_Jay"]
    target = OUTPUT_DIR / "CAJA_Canada_Jay"
    for name in grey_variants:
        src = OUTPUT_DIR / name
        if src.exists() and not target.exists():
            src.rename(target)
            print(f"  Renamed  {src.name}  →  {target.name}")
            # update metadata common_name fields
            for mf in target.glob("*_metadata.json"):
                try:
                    m = json.loads(mf.read_text())
                    m["common_name"] = "Canada Jay"
                    mf.write_text(json.dumps(m, indent=2), encoding="utf-8")
                except Exception:
                    pass
            return True
    return False


def detect_duplicates():
    """Find photos shared across species (by iNat photo_id in metadata)."""
    photo_id_map = defaultdict(list)  # photo_id → [(species_folder, filename)]
    for meta_file in OUTPUT_DIR.rglob("*_metadata.json"):
        try:
            m  = json.loads(meta_file.read_text())
            pid = str(m.get("photo_id", ""))
            if pid:
                photo_id_map[pid].append((meta_file.parent.name, meta_file.stem.rsplit("_metadata", 1)[0] + ".jpg"))
        except Exception:
            pass
    dupes = {pid: locs for pid, locs in photo_id_map.items() if len(locs) > 1}
    if dupes:
        print(f"\n⚠  {len(dupes)} duplicate photo ID(s) across species:")
        for pid, locs in dupes.items():
            print(f"  iNat photo {pid}:")
            for folder, filename in locs:
                print(f"    {folder}/{filename}")
    else:
        print("\n✓ No cross-species duplicate photo IDs found.")
    return dupes


# ── CLI ────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--dupes-only", action="store_true", help="Only run duplicate detection")
args = parser.parse_args()

id_lookup = load_id_lookup()

if not args.dupes_only:
    # 1. Fix CAJA folder name
    print("\n── Fixing CAJA folder name ───────────────────────────────")
    if fix_caja_folder():
        print("  Done.")
    else:
        print("  CAJA_Canada_Jay already exists or no Grey/Gray Jay folder found.")

    # 2. Species with no photos
    print("\n── Downloading missing species ───────────────────────────")
    for code, common in NO_PHOTOS.items():
        # skip CAJA if already handled above and folder has photos
        folder = OUTPUT_DIR / f"{code}_{common.replace(' ','_')}"
        if folder.exists() and any(folder.glob("*.jpg")):
            print(f"  [skip] {common} — already has photos")
            continue

        sci = (id_lookup.get(common, {}).get("scientific") or
               load_scientific_from_tsv(common))
        if not sci:
            print(f"  [warn] No scientific name for {common} ({code}) — skipping")
            continue

        print(f"\n=== {common} ({sci}) ===")
        download_species(code, common, sci, wipe=False)

    # 3. Wrong photos — wipe and re-download
    print("\n── Re-downloading wrong-photo species ────────────────────")
    for code, common in WRONG_PHOTOS.items():
        sci = (id_lookup.get(common, {}).get("scientific") or
               load_scientific_from_tsv(common))
        if not sci:
            print(f"  [warn] No scientific name for {common} ({code}) — skipping")
            continue
        print(f"\n=== {common} ({sci}) — WIPE + RE-DOWNLOAD ===")
        download_species(code, common, sci, wipe=True)

# 4. Duplicate detection
print("\n── Cross-species duplicate detection ─────────────────────")
detect_duplicates()

print("\n✓ Fix script complete.")