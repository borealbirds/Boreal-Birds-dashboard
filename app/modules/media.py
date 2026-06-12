"""
Image/Sound related helper functions and javascripts
"""
from shiny import ui
from pathlib import Path

def _get_sidebar_image_path(species_id: str, common_name: str) -> tuple[str, str] | None:
    """Return the relative web asset path and filename for a species sidebar image if it exists."""
    folder_name = f"{species_id}_{common_name.replace(' ', '_')}"
    img_dir = Path(__file__).parent.parent / "www" / "img" / folder_name
    if img_dir.exists():
        jpgs = sorted(img_dir.glob("*.jpg"))
        if jpgs:
            return f"img/{folder_name}/{jpgs[0].name}", folder_name
    return None

def lightbox_script():
    return ui.HTML("""
<script>
if (!document.getElementById('species-lightbox')) {
    document.body.insertAdjacentHTML('beforeend', `
        <div id="species-lightbox" class="lb-overlay" onclick="if(event.target===this)closeLb()">
            <button class="lb-close" onclick="closeLb()">✕</button>
            <button class="lb-arrow lb-prev" onclick="lbNav(-1)">&#8249;</button>
            <div class="lb-content">
                <img id="lb-img" class="lb-main-img">
                <div id="lb-counter" class="lb-counter"></div>
                <div id="lb-meta" class="lb-meta"></div>
            </div>
            <button class="lb-arrow lb-next" onclick="lbNav(1)">&#8250;</button>
        </div>
    `);
    document.addEventListener('keydown', e => {
        const lb = document.getElementById('species-lightbox');
        if (lb && lb.style.display !== 'none') {
            if (e.key === 'ArrowLeft')  lbNav(-1);
            if (e.key === 'ArrowRight') lbNav(1);
            if (e.key === 'Escape')     closeLb();
        }
    });
}

window.openSpeciesLightbox = function(el) {
    const grid = el.closest('.photo-grid');
    const imgs = Array.from(grid.querySelectorAll('.species-photo'));
    window._lbPhotos = imgs.map(i => ({
        src:         i.src,
        sex:         i.dataset.sex || '',
        attribution: i.dataset.attribution || '',
        obsUrl:      i.dataset.obsUrl || '',
        license:     i.dataset.license || '',
        common:      i.dataset.common || '',
        french:      i.dataset.french || '',
        scientific:  i.dataset.scientific || '',
    }));
    window._lbIdx = imgs.indexOf(el);
    updateLb();
    document.getElementById('species-lightbox').style.display = 'flex';
};

window.lbNav = function(dir) {
    window._lbIdx = (window._lbIdx + dir + window._lbPhotos.length) % window._lbPhotos.length;
    updateLb();
};

window.closeLb = function() {
    document.getElementById('species-lightbox').style.display = 'none';
};

function updateLb() {
    const p   = window._lbPhotos[window._lbIdx];
    const SEX = { male: '♂ Male', female: '♀ Female', unknown: '' };
    document.getElementById('lb-img').src     = p.src;
    document.getElementById('lb-counter').textContent =
        (window._lbIdx + 1) + ' – ' + window._lbPhotos.length;

    const sexTag  = SEX[p.sex] || '';
    const license = p.license  ? ' · ' + p.license : '';
    const link    = p.obsUrl   ? '<a href="' + p.obsUrl + '" target="_blank" class="lb-link">iNaturalist ↗</a>' : '';
    document.getElementById('lb-meta').innerHTML =
        '<div class="lb-species-row">' +
            (p.common     ? '<span class="lb-common">'     + p.common     + '</span>' : '') +
            (p.scientific ? '<em  class="lb-scientific">'  + p.scientific + '</em>'   : '') +
            (sexTag       ? '<span class="lb-sex-label">'  + sexTag       + '</span>' : '') +
        '</div>' +
        '<div class="lb-attr-row">' +
            (p.attribution ? '© ' + p.attribution + license : '') +
            (link          ? '&nbsp;&nbsp;' + link : '') +
        '</div>';
}
</script>
""")

def sound_script(sounds_json):
    return ui.HTML(f"""
<script>
(async function() {{
    try {{
        await new Promise(r => setTimeout(r, 200));
        const {{ default: WaveSurfer }}  = await import('https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.esm.js');
        const {{ default: Spectrogram }} = await import('https://unpkg.com/wavesurfer.js@7/dist/plugins/spectrogram.esm.js');

        // ── Song modal (injected once) ─────────────────────────────────
        if (!document.getElementById('song-modal')) {{
            document.body.insertAdjacentHTML('beforeend', `
                <div id="song-modal" class="song-modal-overlay" onclick="if(event.target===this)closeSongModal()">
                    <div class="song-modal-inner">
                        <button class="song-modal-close" onclick="closeSongModal()">✕</button>
                        <span id="sm-title" class="sm-title"></span>
                        <div id="sm-waveform"    class="sm-waveform"></div>
                        <div id="sm-spectrogram" class="sm-spectrogram"></div>
                        <div class="sm-controls">
                            <button id="sm-play-btn" class="play-btn" onclick="if(window._smWs)window._smWs.playPause()">▶  Play</button>
                            <label class="sm-cmap-label">Theme
                                <select id="sm-cmap" class="sm-cmap-select" onchange="if(window._smSetTheme)window._smSetTheme()">
                                    <option value="Grayscale" selected>Grayscale</option>
                                    <option value="Viridis">Viridis</option>
                                    <option value="Magma">Magma</option>
                                </select>
                            </label>
                            <label class="sm-cmap-label">
                                <input type="checkbox" id="sm-invert" class="sm-invert-checkbox" onchange="if(window._smSetTheme)window._smSetTheme()"> Invert
                            </label>
                        </div>
                        <div id="sm-meta" class="sm-meta"></div>
                    </div>
                </div>
            `);
            document.addEventListener('keydown', e => {{ if (e.key==='Escape') closeSongModal(); }});
        }}

        window._smWs = null;

        // ── Spectrogram colour themes ──────────────────────────────────
        // Anchor stops (matplotlib-sampled, RGB 0-1) linearly interpolated to 256 [r,g,b,a] entries.
        function _smBuildCmap(anchors) {{
            const N = 256, S = anchors.length - 1, out = [];
            for (let i = 0; i < N; i++) {{
                const t = i / (N - 1) * S;
                const lo = Math.floor(t), hi = Math.min(lo + 1, S), f = t - lo;
                const a = anchors[lo], b = anchors[hi];
                out.push([a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f, a[2]+(b[2]-a[2])*f, 1]);
            }}
            return out;
        }}
        window._smColorMaps = {{
            Grayscale: 'gray',
            Viridis: _smBuildCmap([[0.2670,0.0049,0.3294],[0.2823,0.0950,0.4173],[0.2788,0.1755,0.4834],[0.2590,0.2515,0.5247],[0.2297,0.3224,0.5457],[0.1994,0.3876,0.5546],[0.1727,0.4488,0.5579],[0.1490,0.5081,0.5573],[0.1276,0.5669,0.5506],[0.1206,0.6258,0.5335],[0.1579,0.6838,0.5017],[0.2461,0.7389,0.4520],[0.3692,0.7889,0.3829],[0.5160,0.8312,0.2943],[0.6785,0.8637,0.1895],[0.8456,0.8873,0.0997],[0.9932,0.9062,0.1439]]),
            Magma:   _smBuildCmap([[0.0015,0.0005,0.0139],[0.0396,0.0311,0.1335],[0.1131,0.0655,0.2768],[0.2117,0.0620,0.4186],[0.3167,0.0717,0.4854],[0.4147,0.1104,0.5047],[0.5128,0.1482,0.5076],[0.6136,0.1818,0.4985],[0.7164,0.2150,0.4753],[0.8169,0.2559,0.4365],[0.9043,0.3196,0.3881],[0.9609,0.4183,0.3596],[0.9867,0.5356,0.3822],[0.9961,0.6537,0.4462],[0.9969,0.7696,0.5349],[0.9924,0.8843,0.6401],[0.9871,0.9914,0.7495]]),
        }};
        function _smInverted() {{
            const cb = document.getElementById('sm-invert');
            return !!(cb && cb.checked);
        }}
        function _smCurrentCmap() {{
            const sel = document.getElementById('sm-cmap');
            const name = sel ? sel.value : 'Grayscale';
            const cm = (window._smColorMaps && window._smColorMaps[name]) || 'gray';
            if (_smInverted()) {{
                if (cm === 'gray') return 'igray';
                if (Array.isArray(cm)) return cm.slice().reverse();
            }}
            return cm;
        }}
        function _smLabelColor() {{
            const sel = document.getElementById('sm-cmap');
            const name = sel ? sel.value : 'Grayscale';
            let bgLight = (name === 'Grayscale');   // grayscale background is light; viridis/magma dark
            if (_smInverted()) bgLight = !bgLight;
            return bgLight ? '#000' : '#fff';
        }}
        window._smSetTheme = function() {{ if (window._smCurrentSong) _initSMWs(window._smCurrentSong); }};

        window.openSongModal = async function(song) {{
            window._smCurrentSong = song;
            document.getElementById('sm-title').textContent = song.label + (song.commonName ? '  ·  ' + song.commonName + (song.scientificName ? ' (' + song.scientificName + ')' : '') : '');
            document.getElementById('song-modal').style.display = 'flex';
            // Force synchronous layout so WaveSurfer gets real container dimensions
            void document.getElementById('sm-spectrogram').offsetWidth;
            await _initSMWs(song);
            _renderSMMeta(song);
        }};

        window.closeSongModal = function() {{
            document.getElementById('song-modal').style.display = 'none';
            if (window._smWs) {{ try {{ window._smWs.pause(); }} catch(e) {{}} }}
        }};

        async function _initSMWs(song) {{
            if (window._smWs) {{ try {{ window._smWs.destroy(); }} catch(e) {{}} window._smWs = null; }}
            const smW = document.getElementById('sm-waveform');
            const smS = document.getElementById('sm-spectrogram');
            const btn = document.getElementById('sm-play-btn');
            if (btn) btn.textContent = '▶  Play';
            smW.innerHTML = '';
            smS.innerHTML = '';
            const ws = WaveSurfer.create({{
                container: smW, sampleRate: 44100, waveColor: 'rgba(59,82,139,0.8)',
                progressColor: '#153B40', cursorColor: '#ff4444', cursorWidth: 2,
                height: 56, normalize: true,
                plugins: [Spectrogram.create({{
                    container: smS, labels: true, height: 300,
                    frequencyMax: 20000, frequencyMin: 0, fftSamples: 2048,
                    scale: 'mel', windowFunc: 'hann', gainDB: 20, rangeDB: 80, colorMap: _smCurrentCmap(), labelsColor: _smLabelColor(),
                }})],
            }});
            ws.load(song.src);
            window._smWs = ws;
            ws.on('play',   () => {{ if(btn) btn.textContent='⏸  Pause'; }});
            ws.on('pause',  () => {{ if(btn) btn.textContent='▶  Play'; }});
            ws.on('finish', () => {{ if(btn) btn.textContent='▶  Play'; }});
            smS.style.position = 'relative';
            const cur = document.createElement('div');
            cur.style.cssText = 'position:absolute;top:0;left:0;width:2px;height:100%;background:rgba(255,68,68,0.85);pointer-events:none;z-index:10;';
            smS.appendChild(cur);
            ws.on('timeupdate', t => {{ const d=ws.getDuration(); if(d) cur.style.left=(t/d*100)+'%'; }});
        }}

        function _renderSMMeta(song) {{
            const parts = [];
            if (song.recordist) parts.push('<span class="sm-meta-item"><b>Recordist</b> '+song.recordist+'</span>');
            if (song.country)   parts.push('<span class="sm-meta-item"><b>Location</b> ' +song.country  +'</span>');
            if (song.date)      parts.push('<span class="sm-meta-item"><b>Date</b> '     +song.date     +'</span>');
            if (song.quality)   parts.push('<span class="sm-meta-item"><b>Quality</b> '  +song.quality  +'</span>');
            if (song.license)   parts.push('<span class="sm-meta-item"><b>License</b> '  +song.license  +'</span>');
            if (song.xc_url)    parts.push('<a href="'+song.xc_url+'" target="_blank" class="sm-meta-link">Xeno-Canto ↗</a>');
            document.getElementById('sm-meta').innerHTML = parts.join('');
        }}

        // ── Inline sound blocks ───────────────────────────────────────
        const songs = {sounds_json};
        for (const song of songs) {{
            const wsEl   = document.getElementById(song.wsId);
            const specEl = document.getElementById(song.specId);
            const metaEl = document.getElementById(song.metaId);
            const btn    = document.getElementById(song.btnId);
            if (!wsEl || !specEl) continue;
            if (wsEl._ws) {{ try {{ wsEl._ws.destroy(); }} catch(e) {{}} }}

            const ws = WaveSurfer.create({{
                container: wsEl, sampleRate: 44100, waveColor: 'rgba(59,82,139,0.8)',
                progressColor: '#153B40', cursorColor: '#ff4444', cursorWidth: 2,
                height: 56, normalize: true,
                plugins: [Spectrogram.create({{
                    container: specEl, labels: true, height: 200,
                    frequencyMax: 20000, frequencyMin: 0, fftSamples: 2048,
                    scale: 'mel', windowFunc: 'hann', gainDB: 20, rangeDB: 80, colorMap: 'gray', labelsColor: '#000',
                }})],
            }});
            ws.load(song.src);
            wsEl._ws = ws;

            ws.on('decode', () => wsEl.querySelector('.ws-loading')?.remove());

            if (btn) {{
                btn.addEventListener('click', () => ws.playPause());
                ws.on('play',   () => btn.textContent = '⏸  Pause');
                ws.on('pause',  () => btn.textContent = '▶  Play');
                ws.on('finish', () => btn.textContent = '▶  Play');
            }}

            specEl.style.position = 'relative';
            const cursor = document.createElement('div');
            cursor.style.cssText = 'position:absolute;top:0;left:0;width:2px;height:100%;background:rgba(255,68,68,0.85);pointer-events:none;z-index:10;';
            specEl.appendChild(cursor);
            ws.on('timeupdate', t => {{ const d=ws.getDuration(); if(d) cursor.style.left=(t/d*100)+'%'; }});

            specEl.style.cursor = 'pointer';
            specEl.title = 'Click for full spectrogram';
            specEl.addEventListener('click', () => openSongModal(song));
        }}
    }} catch(e) {{ console.error('WaveSurfer init error:', e); }}
}})();
</script>""")