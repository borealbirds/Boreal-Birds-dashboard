"""
Generate a visual HTML audit report of all downloaded bird photos.

Opens in browser — shows every photo with metadata, iNaturalist link,
and a flag checkbox so you can note bad images.

Usage (from project root):
  python src/bird_photos/verify_bird_photos.py
  → writes  src/bird_photos/photo_audit.html
  → open it in your browser
"""

import json
from pathlib import Path

_SCRIPT_DIR   = Path(__file__).parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
IMG_DIR       = _PROJECT_ROOT / "app" /"www"/ "img"
OUT_HTML      = _SCRIPT_DIR / "photo_audit.html"

SEX_SYMBOL = {"male": "♂", "female": "♀", "unknown": "?"}

rows = []
for species_dir in sorted(IMG_DIR.iterdir()):
    if not species_dir.is_dir():
        continue
    jpgs = sorted(species_dir.glob("*.jpg"))
    if not jpgs:
        rows.append({"folder": species_dir.name, "photos": [], "empty": True})
        continue

    photos = []
    for jpg in jpgs:
        meta_file = species_dir / f"{jpg.stem}_metadata.json"
        meta = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
            except Exception:
                pass
        photos.append({
            "file":        jpg.name,
            "rel_path":    f"../../../app/img/{species_dir.name}/{jpg.name}",
            "sex":         meta.get("sex", "unknown"),
            "attribution": meta.get("attribution", ""),
            "license":     meta.get("license", ""),
            "obs_url":     meta.get("obs_url", ""),
            "photo_id":    str(meta.get("photo_id", "")),
        })
    rows.append({"folder": species_dir.name, "photos": photos, "empty": False})

# ── HTML ───────────────────────────────────────────────────────────────
species_cards = ""
for row in rows:
    folder     = row["folder"]
    code       = folder.split("_")[0]
    label      = folder.replace("_", " ", 1).replace("_", " ")

    if row["empty"]:
        species_cards += f"""
        <div class="species-card empty" id="{folder}">
          <div class="species-header">
            <span class="code">{code}</span>
            <span class="name">{label}</span>
            <span class="badge red">NO PHOTOS</span>
          </div>
        </div>"""
        continue

    photo_html = ""
    for p in row["photos"]:
        sex_sym  = SEX_SYMBOL.get(p["sex"], "?")
        obs_link = f'<a href="{p["obs_url"]}" target="_blank">iNat ↗</a>' if p["obs_url"] else ""
        photo_html += f"""
          <div class="photo-card" data-photo-id="{p['photo_id']}">
            <img src="{p['rel_path']}" loading="lazy" onclick="zoomImg(this)">
            <div class="photo-meta">
              <span class="sex-sym">{sex_sym}</span>
              <span class="attr">{p['attribution'][:60] if p['attribution'] else '—'}</span>
              {obs_link}
            </div>
            <label class="flag-label">
              <input type="checkbox" class="flag-box" data-species="{folder}" data-file="{p['file']}">
              🚩 Flag
            </label>
          </div>"""

    count = len(row["photos"])
    species_cards += f"""
        <div class="species-card" id="{folder}">
          <div class="species-header">
            <span class="code">{code}</span>
            <span class="name">{label}</span>
            <span class="badge">{count} photo{'s' if count != 1 else ''}</span>
          </div>
          <div class="photo-grid">{photo_html}</div>
        </div>"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Bird Photo Audit</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #f4f5f6; margin: 0; padding: 1rem 2rem; }}
  h1   {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
  p.sub{{ color: #666; margin-bottom: 1.5rem; font-size: 0.85rem; }}
  .controls {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; align-items: center; }}
  input[type=text] {{ padding: 0.4rem 0.75rem; border: 1px solid #ccc; border-radius: 6px; font-size: 0.85rem; width: 260px; }}
  button {{ padding: 0.4rem 0.9rem; border: none; border-radius: 6px; cursor: pointer; font-size: 0.82rem; background: #153B40; color: white; }}
  button.sec {{ background: #eee; color: #333; }}

  .species-card {{ background: white; border-radius: 10px; margin-bottom: 1.25rem;
                   box-shadow: 0 2px 8px rgba(0,0,0,0.07); overflow: hidden; }}
  .species-card.empty {{ opacity: 0.55; }}
  .species-header {{ display: flex; align-items: center; gap: 0.75rem; padding: 0.6rem 1rem;
                     background: #153B40; color: white; }}
  .code {{ font-weight: 800; font-size: 0.9rem; background: rgba(255,255,255,0.15);
           padding: 0.1rem 0.45rem; border-radius: 4px; }}
  .name {{ flex: 1; font-size: 0.95rem; }}
  .badge {{ font-size: 0.75rem; background: rgba(255,255,255,0.2); padding: 0.1rem 0.5rem;
            border-radius: 20px; }}
  .badge.red {{ background: #c0392b; }}

  .photo-grid {{ display: flex; flex-wrap: wrap; gap: 0.75rem; padding: 0.75rem 1rem 1rem; }}
  .photo-card {{ width: 160px; border: 1px solid #eee; border-radius: 7px; overflow: hidden;
                 background: #fafafa; }}
  .photo-card img {{ width: 160px; height: 140px; object-fit: cover; display: block; cursor: zoom-in; }}
  .photo-meta {{ padding: 0.3rem 0.5rem; font-size: 0.67rem; color: #555;
                 display: flex; flex-direction: column; gap: 0.15rem; }}
  .sex-sym {{ font-size: 0.95rem; font-weight: 700; }}
  .attr {{ color: #888; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .flag-label {{ display: flex; align-items: center; gap: 0.3rem; font-size: 0.72rem;
                 padding: 0.2rem 0.5rem 0.4rem; cursor: pointer; color: #888; }}
  .flag-label:has(.flag-box:checked) {{ background: #fff3cd; color: #c0392b; font-weight: 600; }}

  #zoom-overlay {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,0.85);
                   z-index:9999; align-items:center; justify-content:center; }}
  #zoom-overlay.on {{ display:flex; }}
  #zoom-overlay img {{ max-width:90vw; max-height:90vh; border-radius:6px; cursor:zoom-out; }}

  #flag-report {{ display: none; background: #fff3cd; border: 1px solid #f0ad4e;
                  border-radius: 8px; padding: 1rem; margin-top: 1rem; font-size: 0.82rem; }}
  #flag-report h3 {{ margin: 0 0 0.5rem; font-size: 0.9rem; }}
  #flag-report li {{ margin-bottom: 0.2rem; }}
</style>
</head>
<body>
<h1>🦅 Bird Photo Audit</h1>
<p class="sub">{len(rows)} species · Click any photo to zoom · Use 🚩 to flag bad images · Export flagged list below</p>

<div class="controls">
  <input type="text" id="search" placeholder="Filter by species name or code…" oninput="filterSpecies(this.value)">
  <button onclick="showFlagged()">📋 Export flagged</button>
  <button class="sec" onclick="showEmpty()">⚠ Show missing only</button>
  <button class="sec" onclick="showAll()">Show all</button>
</div>

{species_cards}

<div id="flag-report"><h3>Flagged photos</h3><ul id="flag-list"></ul></div>

<div id="zoom-overlay" onclick="this.classList.remove('on')">
  <img id="zoom-img">
</div>

<script>
function filterSpecies(q) {{
  q = q.toLowerCase();
  document.querySelectorAll('.species-card').forEach(card => {{
    card.style.display = card.id.toLowerCase().includes(q) ? '' : 'none';
  }});
}}

function showEmpty() {{
  document.querySelectorAll('.species-card').forEach(c => {{
    c.style.display = c.classList.contains('empty') ? '' : 'none';
  }});
}}

function showAll() {{
  document.querySelectorAll('.species-card').forEach(c => c.style.display = '');
  document.getElementById('search').value = '';
}}

function zoomImg(el) {{
  document.getElementById('zoom-img').src = el.src;
  document.getElementById('zoom-overlay').classList.add('on');
}}

function showFlagged() {{
  const ul   = document.getElementById('flag-list');
  const rep  = document.getElementById('flag-report');
  const boxes = document.querySelectorAll('.flag-box:checked');
  ul.innerHTML = '';
  boxes.forEach(b => {{
    const li = document.createElement('li');
    li.textContent = b.dataset.species + '  /  ' + b.dataset.file;
    ul.appendChild(li);
  }});
  rep.style.display = boxes.length ? 'block' : 'none';
  if (boxes.length) rep.scrollIntoView({{ behavior: 'smooth' }});
}}
</script>
</body>
</html>"""

OUT_HTML.write_text(html, encoding="utf-8")
print(f"✓ Audit report written → {OUT_HTML}")
print("  Open it in your browser.")