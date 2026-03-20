/* ═══════════════════════════════════════
   Unwatched episodes page logic
   ═══════════════════════════════════════ */

(function () {
    let allSeries = [];   // [{id, name, poster_url, seasons: {sn: [eps]}}]
    let activeSid = null;

    const page = document.getElementById('unwatchedPage');

    init();

    async function init() {
        try {
            const resp = await fetch('/api/unwatched');
            if (!resp.ok) throw new Error('Failed');
            allSeries = await resp.json();
        } catch (e) {
            page.innerHTML = '<div class="loader">Failed to load unwatched episodes.</div>';
            return;
        }

        if (allSeries.length === 0) {
            renderAllWatched();
            return;
        }

        activeSid = allSeries[0].id;
        render();
    }

    // ── Render ─────────────────────────────────────────────

    function render() {
        page.innerHTML = '';

        if (allSeries.length === 0) {
            renderAllWatched();
            return;
        }

        // Page heading
        const heading = document.createElement('h1');
        heading.className = 'unwatched-heading';
        heading.textContent = 'Unwatched Episodes';
        page.appendChild(heading);

        // Poster tab strip
        const tabStrip = document.createElement('div');
        tabStrip.className = 'poster-tabs';

        allSeries.forEach(s => {
            const tab = document.createElement('button');
            tab.className = 'poster-tab' + (s.id === activeSid ? ' active' : '');
            tab.dataset.sid = s.id;
            tab.title = s.name;

            if (s.poster_url) {
                const img = document.createElement('img');
                img.src = s.poster_url;
                img.alt = s.name;
                tab.appendChild(img);
            } else {
                const ph = document.createElement('div');
                ph.className = 'poster-tab-placeholder';
                ph.textContent = s.name.charAt(0);
                tab.appendChild(ph);
            }

            const totalEps = Object.values(s.seasons).reduce((sum, arr) => sum + arr.length, 0);
            const badge = document.createElement('span');
            badge.className = 'poster-tab-badge';
            badge.textContent = totalEps;
            tab.appendChild(badge);

            const label = document.createElement('span');
            label.className = 'poster-tab-name';
            label.textContent = s.name;
            tab.appendChild(label);

            tabStrip.appendChild(tab);
        });

        tabStrip.addEventListener('click', e => {
            const tab = e.target.closest('.poster-tab');
            if (!tab) return;
            activeSid = parseInt(tab.dataset.sid, 10);
            render();
        });

        page.appendChild(tabStrip);

        // Episode panel for the active series
        const active = allSeries.find(s => s.id === activeSid);
        if (!active) return;

        const content = document.createElement('div');
        content.className = 'unwatched-content';

        // Series header inside panel
        const seriesHeader = document.createElement('div');
        seriesHeader.className = 'unwatched-series-header';
        seriesHeader.innerHTML = `<h2>${escHtml(active.name)}</h2>`;
        content.appendChild(seriesHeader);

        // Season groups
        const seasonNums = Object.keys(active.seasons).map(Number).sort((a, b) => a - b);

        seasonNums.forEach(sn => {
            const eps = active.seasons[String(sn)];

            const block = document.createElement('div');
            block.className = 'season-block';

            const header = document.createElement('div');
            header.className = 'season-header';
            header.innerHTML = `
                <span class="season-title">Season ${sn}</span>
                <i class="chevron" style="font-style:normal;color:var(--text-muted);">▾</i>
            `;
            block.appendChild(header);

            const epList = document.createElement('div');
            epList.className = 'season-episodes';

            eps.forEach(ep => {
                const row = document.createElement('div');
                row.className = 'episode-row normal';
                row.dataset.epId = ep.id;
                row.innerHTML = `
                    <input type="checkbox" class="ep-check" data-id="${ep.id}">
                    <span class="ep-number">S${pad(ep.season_number)}E${pad(ep.episode_number)}</span>
                    <span class="ep-name" title="${escHtml(ep.name || '')}">${escHtml(ep.name || 'TBA')}</span>
                    ${ep.overview ? `<span class="ep-overview" title="${escHtml(ep.overview)}">${escHtml(ep.overview)}</span>` : ''}
                    <span class="ep-date">${ep.air_date || '—'}</span>
                `;
                epList.appendChild(row);
            });

            block.appendChild(epList);

            // Collapse toggle
            header.addEventListener('click', () => {
                block.classList.toggle('collapsed');
                header.querySelector('.chevron').textContent =
                    block.classList.contains('collapsed') ? '▸' : '▾';
            });

            // Mark episode as watched
            epList.addEventListener('change', async e => {
                if (!e.target.classList.contains('ep-check')) return;
                const epId = parseInt(e.target.dataset.id, 10);
                await markWatched(epId, active.id, sn);
            });

            content.appendChild(block);
        });

        page.appendChild(content);
    }

    // ── Mark as watched ────────────────────────────────────

    async function markWatched(epId, seriesId, seasonNum) {
        try {
            const resp = await fetch(`/api/episodes/${epId}/toggle`, { method: 'PUT' });
            if (!resp.ok) throw new Error();
            const data = await resp.json();

            if (data.watched) {
                // Remove episode from local state
                const series = allSeries.find(s => s.id === seriesId);
                if (series) {
                    const snKey = String(seasonNum);
                    series.seasons[snKey] = series.seasons[snKey].filter(ep => ep.id !== epId);
                    if (series.seasons[snKey].length === 0) {
                        delete series.seasons[snKey];
                    }
                    if (Object.keys(series.seasons).length === 0) {
                        allSeries = allSeries.filter(s => s.id !== seriesId);
                        if (activeSid === seriesId) {
                            activeSid = allSeries.length > 0 ? allSeries[0].id : null;
                        }
                    }
                }
                showToast('Episode marked as watched', 'success');
                render();
            } else {
                // Toggled back to unwatched — reload from server for consistency
                showToast('Episode unmarked', 'info');
                await reloadFromServer();
            }
        } catch (e) {
            showToast('Failed to toggle episode', 'error');
            // Uncheck the checkbox to revert UI
            const box = document.querySelector(`.ep-check[data-id="${epId}"]`);
            if (box) box.checked = false;
        }
    }

    async function reloadFromServer() {
        try {
            const resp = await fetch('/api/unwatched');
            if (!resp.ok) throw new Error();
            allSeries = await resp.json();
            if (activeSid !== null && !allSeries.find(s => s.id === activeSid)) {
                activeSid = allSeries.length > 0 ? allSeries[0].id : null;
            }
        } catch (e) {
            // keep current state
        }
        render();
    }

    // ── Empty state ────────────────────────────────────────

    function renderAllWatched() {
        page.innerHTML = `
            <div class="unwatched-empty">
                <div class="unwatched-empty-icon">🎉</div>
                <p>All caught up! No unwatched episodes.</p>
            </div>
        `;
    }

    // ── Helpers ────────────────────────────────────────────

    function pad(n) { return String(n).padStart(2, '0'); }

    function escHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
})();
