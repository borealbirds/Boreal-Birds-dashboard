from pathlib import Path

from ui.welcome import welcome_tab
from ui.model_v4 import model_v4_tab
from ui.model_v5 import model_v5_tab
from ui.methods import methods_tab
from ui.model_access import model_access_tab
from ui.sidebar import sidebar

from server.server_v5 import server_v5

import polars as pl
from shiny import App, Inputs, reactive, render, ui

www_dir = Path(__file__).parent / "www"

FOOTER = ui.div(
    ui.HTML(
        '&copy; 2026 '
        '<a href="https://borealbirds.ca/" target="_blank">Boreal Avian Modelling Project </a>'
        'under a '
        '<a href="https://creativecommons.org/licenses/by-sa/4.0/", target="_blank"> CC BY-SA 4.0 license </a>'
    ),
    class_="footer"
)

app_ui = ui.page_navbar(
    ui.head_content(
        ui.include_css(str(www_dir / "styles.css")),
        ui.HTML("""
<script>
window._wsInstances = {};

Shiny.addCustomMessageHandler("initWaveSurfer", async function(data) {
    for (const id of Object.keys(window._wsInstances)) {
        try { window._wsInstances[id].destroy(); } catch(e) {}
    }
    window._wsInstances = {};

    await new Promise(r => setTimeout(r, 300));

    const { default: WaveSurfer }  = await import('https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.esm.js');
    const { default: Spectrogram } = await import('https://unpkg.com/wavesurfer.js@7/dist/plugins/spectrogram.esm.js');

    for (const song of data.songs) {
        const wsEl   = document.getElementById(song.wsId);
        const specEl = document.getElementById(song.specId);
        const btn    = document.getElementById(song.btnId);
        if (!wsEl || !specEl) continue;

        const ws = WaveSurfer.create({
            container:     wsEl,
            waveColor:     'rgba(110,197,116,0.7)',
            progressColor: '#153B40',
            cursorColor:   '#ff3333',
            cursorWidth:   2,
            height:        64,
            normalize:     true,
            plugins: [
                Spectrogram.create({
                    container:    specEl,
                    labels:       true,
                    height:       128,
                    frequencyMax: 8000,
                })
            ],
        });

        ws.load(song.src);
        window._wsInstances[song.wsId] = ws;

        if (btn) {
            btn.addEventListener('click', () => ws.playPause());
            ws.on('play',   () => btn.textContent = '⏸  Pause');
            ws.on('pause',  () => btn.textContent = '▶  Play');
            ws.on('finish', () => btn.textContent = '▶  Play');
        }

        specEl.style.position = 'relative';
        const cursor = document.createElement('div');
        cursor.style.cssText = 'position:absolute;top:0;left:0;width:2px;height:100%;background:#ff3333;pointer-events:none;z-index:10;';
        specEl.appendChild(cursor);
        ws.on('timeupdate', t => {
            const dur = ws.getDuration();
            if (dur) cursor.style.left = (t / dur * 100) + '%';
        });
    }
});
</script>
"""),
    ),
    ui.nav_spacer(),
    welcome_tab(),
    ui.nav_menu(
        "Models",
        model_v5_tab(),
        model_v4_tab(),
    ),
    model_access_tab(),
    methods_tab(),
    ui.nav_menu(
        "Contact Us",
        ui.nav_control(
            ui.a(
                "Our Website",
                href="https://borealbirds.ca/contact/",
                target="_blank",
            ),
        ),
        ui.nav_control(
            ui.a(
                "Email Us",
                href="mailto:bamp@ualberta.ca",
                target="_blank",
            ),
        ),
        ui.nav_control(
            ui.a(
                "Report an Issue",
                href="https://github.com/borealbirds/LandbirdModelsV5/issues",
                target="_blank",
            ),
        ),
    ),
    selected="Current Model",
    id="tabs",
    title=ui.tags.a(
        ui.tags.img(
            src="img/BAM-Logo-WhiteText.svg",
            alt="Boreal Avian Modelling Centre Dashboard",
            height="48"
        ),
        href="#",
    ),
    fillable=True,
    footer=FOOTER
)

def server(input: Inputs, output, session):

    # Register Model V5 outputs
    server_v5(input, session)

app = App(app_ui, server, static_assets=www_dir)