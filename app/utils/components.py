"""
UI layout components and global utilities for the BAM dashboard.

Provides reusable navigation controls, footer licensing blocks, and front-end 
JavaScript hooks for dynamic audio playback.

Main Capabilities
-----------------
* Injects external links and navigation items into the top navbar menus.
* Renders the application copyright and CC BY-SA 4.0 data license footer.
* Binds client-side audio pipelines dynamically using WaveSurfer.js.
"""

from shiny import ui


def website() -> ui.NavSetArg:
    """
    Generate a dynamic navigation item linking to the core BAM project web portal.

    Returns
    -------
    shiny.ui.NavSetArg
        A navigation controller containing an external anchor element configuration.
    """
    return ui.nav_control(
            ui.a(
                "Our Website",
                href="https://borealbirds.ca/",
                target="_blank",
            ),
        )


def website_contact() -> ui.NavSetArg:
    """
    Generate a navigation layout button mapping to the official team directory page.

    Returns
    -------
    shiny.ui.NavSetArg
        A web component mapping directly to external communication infrastructure.
    """
    return ui.nav_control(
        ui.a(
            "Email Us",
            href="https://borealbirds.ca/contact/",
            target="_blank",
            ),
        )

def email() -> ui.NavSetArg:
    """
    Generate an interface interaction gateway linking to default mail applications.

    Returns
    -------
    shiny.ui.NavSetArg
        An operational interface anchor using mailto address routing actions.
    """
    return ui.nav_control(
        ui.a(
            "Email Us",
            href="mailto:bamp@ualberta.ca",
            target="_blank",
            ),
        )


def report_issue() -> ui.NavSetArg:
    """
    Generate an issue-tracking shortcut pointing to repository management layers.

    Returns
    -------
    shiny.ui.NavSetArg
        A link asset to log defects, structural feature requests, or application bugs.
    """
    return ui.nav_control(
            ui.a(
                "Report an Issue",
                href="https://github.com/UBC-MDS/Boreal-Birds/issues",
                target="_blank",
            ),
        )


def footer() -> ui.Tag:
    """
    Render the copyright disclosure and Creative Commons usage policy wrapper.

    Returns
    -------
    shiny.ui.Tag
        A bottom-anchored content div element styled with appropriate CSS rules.
    """
    return ui.div(
        ui.HTML(
            '&copy; 2026 '
            '<a href="https://borealbirds.ca/" target="_blank">Boreal Avian Modelling Project </a>'
            'under a '
            '<a href="https://creativecommons.org/licenses/by-sa/4.0/", target="_blank"> CC BY-SA 4.0 license </a>'
        ),
        class_="footer"
    )


def audio() -> ui.Tag:
    """
    Inject JavaScript pipelines for WaveSurfer audio and spectrogram rendering.

    Registers a custom Shiny message handler to initialize and synchronize 
    multi-instance audio players and visual timelines on the client side.

    Returns
    -------
    Tag
        An HTML script block containing client-side audio runtime logic.

    Notes
    -----
    Active WaveSurfer tracking instances are loaded via CDN and maintained 
    globally in the browser window scope under `window._wsInstances`.
    """
    return ui.HTML(
        """
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
        """
    )
