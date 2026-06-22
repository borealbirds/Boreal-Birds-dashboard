"""
Media utility assets and client-side JavaScript injection pipelines.

Resolves local storage paths for bird imagery and injects HTML/JavaScript 
engines for interactive photo lightboxes and audio spectrograms.
"""

from shiny import ui
from pathlib import Path


def get_sidebar_image_path(species_id: str, common_name: str) -> tuple[str, str]:
    """
    Resolve the web asset path and directory name for a species sidebar image.

    Parameters
    ----------
    species_id : str
        The unique species alpha-numeric identifier code.
    common_name : str
        The English common name of the bird species.

    Returns
    -------
    tuple of (str, str) or None
        A tuple of (relative_web_url, folder_name) if an image exists, else None.
    """
    folder_name = f"{species_id}_{common_name.replace(' ', '_')}"
    img_dir = Path(__file__).parent.parent / "www" / "img" / folder_name
    if img_dir.exists():
        jpgs = sorted(img_dir.glob("*.jpg"))
        if jpgs:
            return f"img/{folder_name}/{jpgs[0].name}", folder_name
    return None


def lightbox_script()-> ui.HTML:
    """
    Generate the HTML and JavaScript script block for the image gallery lightbox.

    Returns
    -------
    HTML
        A raw HTML tag containing the client-side modal and gallery navigation logic.
    """
    return ui.HTML(
        """
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
        """
    )
