/* ═══════════════════════════════════════
   Series detail page logic
   ═══════════════════════════════════════ */

(function () {
    const container = document.getElementById('seriesDetailContainer');
    const seriesId = container.dataset.seriesId;

    loadDetail();

    function activeSeasonNum() {
        const btn = container.querySelector('.season-tab-btn.active');
        return btn ? btn.dataset.season : null;
    }

    async function loadDetail(keepSeason) {
        container.innerHTML = '<div class="loader">Loading…</div>';
        try {
            const resp = await fetch(`/api/series/${seriesId}`);
            if (!resp.ok) { container.innerHTML = '<div class="loader">Series not found</div>'; return; }
            const data = await resp.json();
            renderDetail(data, keepSeason);
        } catch (err) {
            container.innerHTML = '<div class="loader">Failed to load series</div>';
        }
    }

    function renderDetail(s, keepSeason) {
        container.innerHTML = '';

        // ── Header ──
        const header = document.createElement('div');
        header.className = 'detail-header';

        const posterUrl = s.poster_url || '';
        header.innerHTML = `
            ${posterUrl
                ? `<img class="detail-poster" src="${posterUrl}" alt="${escHtml(s.name)}">`
                : '<div class="detail-poster placeholder-img" style="width:150px;height:225px;">No Image</div>'
            }
            <div class="detail-info">
                <h1>${escHtml(s.name)}</h1>
                <div class="detail-badges">
                    ${statusBadge(s)}
                    <span class="badge" style="background:#e7f5ff;color:#1c7ed6;">
                        ${s.number_of_seasons} season${s.number_of_seasons !== 1 ? 's' : ''}
                    </span>
                </div>
                <p class="detail-overview" style="margin-top:.5rem">${escHtml(s.overview || '')}</p>
            </div>
        `;
        container.appendChild(header);

        // ── Actions ──
        const actions = document.createElement('div');
        actions.className = 'detail-actions';
        actions.innerHTML = `
            <button class="btn btn-sm btn-outline" id="refreshBtn">Refresh from TMDB</button>
            ${s.status === 'watching'
                ? `<button class="btn btn-sm btn-outline" id="archiveBtn">Archive Series</button>`
                : `<button class="btn btn-sm btn-success" id="unarchiveBtn">Unarchive Series</button>`
            }
            <a href="/series" class="btn btn-sm btn-outline">Back to List</a>
        `;
        container.appendChild(actions);

        document.getElementById('refreshBtn').addEventListener('click', refreshSeries);
        const archBtn = document.getElementById('archiveBtn');
        if (archBtn) archBtn.addEventListener('click', () => setArchive(true));
        const unarchBtn = document.getElementById('unarchiveBtn');
        if (unarchBtn) unarchBtn.addEventListener('click', () => setArchive(false));

        // ── Mark entire series watched ──
        const markAllBar = document.createElement('div');
        markAllBar.className = 'mark-all-bar';
        markAllBar.innerHTML = `<button class="btn btn-sm btn-primary" id="markSeriesWatchedBtn">Mark Entire Series as Watched</button>`;
        container.appendChild(markAllBar);
        document.getElementById('markSeriesWatchedBtn').addEventListener('click', markSeriesWatched);

        // ── Season Tabs ──
        const seasonNums = Object.keys(s.seasons).map(Number).sort((a, b) => a - b);

        const tabsWrapper = document.createElement('div');
        tabsWrapper.className = 'season-tabs-wrapper';

        const tabBar = document.createElement('div');
        tabBar.className = 'season-tab-bar';

        const tabPanels = document.createElement('div');
        tabPanels.className = 'season-tab-panels';

        const activeSeason = keepSeason != null ? String(keepSeason) : String(seasonNums[0]);

        seasonNums.forEach((sn, idx) => {
            const seasonData = s.seasons[String(sn)];
            const isActive = String(sn) === activeSeason;

            // Tab button
            const tab = document.createElement('button');
            tab.className = 'season-tab-btn' + (isActive ? ' active' : '');
            tab.textContent = String(sn);
            tab.dataset.season = sn;
            tabBar.appendChild(tab);

            // Tab panel
            const panel = document.createElement('div');
            panel.className = 'season-tab-panel' + (isActive ? ' active' : '');
            panel.dataset.season = sn;

            const headerEl = document.createElement('div');
            headerEl.className = 'season-header';
            headerEl.innerHTML = `
                <span class="season-title">Season ${sn}</span>
                <button class="btn btn-sm season-toggle-btn ${seasonData.fully_watched ? 'btn-outline' : 'btn-success'}">
                    ${seasonData.fully_watched ? 'Unmark All' : 'Mark All Watched'}
                </button>
            `;
            panel.appendChild(headerEl);

            const epList = document.createElement('div');
            epList.className = 'season-episodes';

            seasonData.episodes.forEach(ep => {
                const row = document.createElement('div');
                let rowCls = 'episode-row ' + ep.type;
                if (ep.watched) rowCls += ' watched-row';
                row.className = rowCls;
                row.innerHTML = `
                    <input type="checkbox" class="ep-check" data-id="${ep.id}" ${ep.watched ? 'checked' : ''}>
                    <span class="ep-number">S${pad(ep.season_number)}E${pad(ep.episode_number)}</span>
                    <span class="ep-name" title="${escHtml(ep.name || '')}">${escHtml(ep.name || 'TBA')}</span>
                    <span class="ep-date">${ep.air_date || '—'}</span>
                `;
                epList.appendChild(row);
            });

            panel.appendChild(epList);
            tabPanels.appendChild(panel);

            // Toggle single episode
            epList.addEventListener('change', async (e) => {
                if (e.target.classList.contains('ep-check')) {
                    const epId = e.target.dataset.id;
                    try {
                        await fetch(`/api/episodes/${epId}/toggle`, {method: 'PUT'});
                        loadDetail(activeSeasonNum());
                    } catch (err) {
                        showToast('Failed to toggle', 'error');
                    }
                }
            });

            // Toggle full season
            headerEl.querySelector('.season-toggle-btn').addEventListener('click', async (e) => {
                e.stopPropagation();
                try {
                    await fetch(`/api/series/${seriesId}/seasons/${sn}/toggle`, {method: 'PUT'});
                    loadDetail(activeSeasonNum());
                } catch (err) {
                    showToast('Failed to toggle season', 'error');
                }
            });
        });

        // Tab switching
        tabBar.addEventListener('click', (e) => {
            const btn = e.target.closest('.season-tab-btn');
            if (!btn) return;
            tabBar.querySelectorAll('.season-tab-btn').forEach(b => b.classList.remove('active'));
            tabPanels.querySelectorAll('.season-tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            tabPanels.querySelector(`.season-tab-panel[data-season="${btn.dataset.season}"]`).classList.add('active');
        });

        tabsWrapper.appendChild(tabBar);
        tabsWrapper.appendChild(tabPanels);
        container.appendChild(tabsWrapper);
    }

    async function markSeriesWatched() {
        try {
            await fetch(`/api/series/${seriesId}/mark-watched`, {method: 'PUT'});
            showToast('All episodes marked as watched', 'success');
            loadDetail();
        } catch (err) {
            showToast('Failed to mark as watched', 'error');
        }
    }

    async function refreshSeries() {
        showToast('Refreshing from TMDB…', 'info');
        try {
            const resp = await fetch(`/api/series/${seriesId}/refresh`, {method: 'PUT'});
            if (resp.ok) {
                showToast('Refreshed!', 'success');
                loadDetail();
            } else {
                const d = await resp.json();
                showToast(d.error || 'Refresh failed', 'error');
            }
        } catch (err) {
            showToast('Refresh failed', 'error');
        }
    }

    async function setArchive(archive) {
        const url = archive
            ? `/api/series/${seriesId}/archive`
            : `/api/series/${seriesId}/unarchive`;
        try {
            await fetch(url, {method: 'PUT'});
            showToast(archive ? 'Archived' : 'Restored', 'success');
            loadDetail();
        } catch (err) {
            showToast('Action failed', 'error');
        }
    }

    function statusBadge(s) {
        if (s.status === 'archived') return '<span class="badge badge-archived">Archived</span>';
        if (s.series_status === 'Returning Series') return '<span class="badge badge-airing">Airing</span>';
        return '<span class="badge badge-ended">Ended</span>';
    }

    function pad(n) { return String(n).padStart(2, '0'); }

    function escHtml(str) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(str || ''));
        return div.innerHTML;
    }
})();
