from shiny import ui


def website():
    """Link to the BAM website's contact page."""
    return ui.nav_control(
            ui.a(
                "Our Website",
                href="https://borealbirds.ca/contact/",
                target="_blank",
            ),
        )


def email():
    """Open an external email to the BAM team."""
    return ui.nav_control(
        ui.a(
            "Email Us",
            href="mailto:bamp@ualberta.ca",
            target="_blank",
            ),
        )


def report_issue():
    """Link to the GitHub issues page for reporting issues."""
    return ui.nav_control(
            ui.a(
                "Report an Issue",
                href="https://github.com/UBC-MDS/Boreal-Birds/issues",
                target="_blank",
            ),
        )


def footer():
    """Footer with copyright and license information."""
    return ui.div(
        ui.HTML(
            '&copy; 2026 '
            '<a href="https://borealbirds.ca/" target="_blank">Boreal Avian Modelling Project </a>'
            'under a '
            '<a href="https://creativecommons.org/licenses/by-sa/4.0/", target="_blank"> CC BY-SA 4.0 license </a>'
        ),
        class_="footer"
    )


def audio():
    """Audio player for bird sounds and spectrograms."""
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
