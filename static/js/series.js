/* ═══════════════════════════════════════
   Series list page logic
   ═══════════════════════════════════════ */

(function () {
    const container = document.getElementById('seriesListContainer');
    const searchInput = document.getElementById('seriesSearchInput');
    const searchResults = document.getElementById('searchResults');
    let debounceTimer = null;

    // Load series list on page load
    loadSeriesList();

    // ── Live search ──
    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const q = searchInput.value.trim();
        if (q.length < 2) {
            searchResults.classList.remove('open');
            searchResults.innerHTML = '';
            return;
        }
        debounceTimer = setTimeout(() => searchTMDB(q), 400);
    });

    searchInput.addEventListener('blur', () => {
        setTimeout(() => searchResults.classList.remove('open'), 200);
    });
    searchInput.addEventListener('focus', () => {
        if (searchResults.innerHTML) searchResults.classList.add('open');
    });

    async function searchTMDB(query) {
        try {
            const resp = await fetch(`/api/series/search?q=${encodeURIComponent(query)}`);
            const data = await resp.json();
            renderSearchResults(data);
        } catch (err) {
            searchResults.innerHTML = '<div style="padding:.75rem;color:#adb5bd">Search failed</div>';
            searchResults.classList.add('open');
        }
    }

    function renderSearchResults(results) {
        searchResults.innerHTML = '';
        if (!results.length) {
            searchResults.innerHTML = '<div style="padding:.75rem;color:#adb5bd">No results found</div>';
            searchResults.classList.add('open');
            return;
        }
        results.forEach(r => {
            const item = document.createElement('div');
            item.className = 'search-result-item';
            const year = r.first_air_date ? r.first_air_date.substring(0, 4) : '';
            item.innerHTML = `
                <img src="${r.poster_url || ''}" alt="" onerror="this.style.display='none'">
                <div class="search-result-info">
                    <div class="name">${escHtml(r.name)}</div>
                    <div class="year">${year}</div>
                </div>
            `;
            item.addEventListener('click', () => addSeries(r.tmdb_id, r.name));
            searchResults.appendChild(item);
        });
        searchResults.classList.add('open');
    }

    async function addSeries(tmdbId, name) {
        searchResults.classList.remove('open');
        searchInput.value = '';
        showToast(`Adding "${name}"…`, 'info');
        try {
            const resp = await fetch('/api/series', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({tmdb_id: tmdbId}),
            });
            const data = await resp.json();
            if (resp.ok) {
                showToast(`"${data.name}" added!`, 'success');
                loadSeriesList();
            } else if (resp.status === 409) {
                showToast('Series already in your list', 'info');
            } else {
                showToast(data.error || 'Failed to add', 'error');
            }
        } catch (err) {
            showToast('Failed to add series', 'error');
        }
    }

    async function loadSeriesList() {
        container.innerHTML = '<div class="loader">Loading…</div>';
        try {
            const resp = await fetch('/api/series');
            const data = await resp.json();
            renderSeriesList(data);
        } catch (err) {
            container.innerHTML = '<div class="loader">Failed to load series</div>';
        }
    }

    function renderSeriesList(series) {
        const airing = series.filter(s => s.status === 'watching' && s.series_status === 'Returning Series');
        const ended = series.filter(s => s.status === 'watching' && s.series_status !== 'Returning Series');
        const archived = series.filter(s => s.status === 'archived');

        if (!series.length) {
            container.innerHTML = '<div class="no-series">No series yet. Use the search bar above to add one!</div>';
            return;
        }

        container.innerHTML = '';
        if (airing.length) container.appendChild(buildGroup('Currently Airing', airing, false));
        if (ended.length) container.appendChild(buildGroup('Ended / Canceled', ended, false));
        if (archived.length) container.appendChild(buildGroup('Archived', archived, true));
    }

    function buildGroup(title, items, isArchived) {
        const group = document.createElement('div');
        group.className = 'series-group';
        group.innerHTML = `<div class="series-group-title">${title}</div>`;

        items.forEach(s => {
            const card = document.createElement('a');
            card.href = `/series/${s.id}`;
            card.className = 'series-card';
            card.innerHTML = `
                <img src="${s.poster_url || ''}" alt="" onerror="this.style.display='none'">
                <div class="series-card-info">
                    <div class="series-card-name">${escHtml(s.name)}</div>
                    <div class="series-card-meta">
                        ${s.number_of_seasons} season${s.number_of_seasons !== 1 ? 's' : ''} &middot;
                        ${s.series_status || 'Unknown'}
                    </div>
                </div>
                <div class="series-card-actions">
                    ${isArchived
                        ? `<button class="btn btn-sm btn-success unarchive-btn" data-id="${s.id}" title="Unarchive">Unarchive</button>`
                        : `<button class="btn btn-sm btn-outline archive-btn" data-id="${s.id}" title="Archive">Archive</button>`
                    }
                </div>
            `;
            group.appendChild(card);
        });

        // Event delegation for archive/unarchive buttons
        group.addEventListener('click', async (e) => {
            const archiveBtn = e.target.closest('.archive-btn');
            const unarchiveBtn = e.target.closest('.unarchive-btn');
            if (archiveBtn) {
                e.preventDefault();
                e.stopPropagation();
                await archiveSeries(archiveBtn.dataset.id);
            }
            if (unarchiveBtn) {
                e.preventDefault();
                e.stopPropagation();
                await unarchiveSeries(unarchiveBtn.dataset.id);
            }
        });

        return group;
    }

    async function archiveSeries(id) {
        try {
            await fetch(`/api/series/${id}/archive`, {method: 'PUT'});
            showToast('Series archived', 'success');
            loadSeriesList();
        } catch (err) {
            showToast('Failed to archive', 'error');
        }
    }

    async function unarchiveSeries(id) {
        try {
            await fetch(`/api/series/${id}/unarchive`, {method: 'PUT'});
            showToast('Series restored', 'success');
            loadSeriesList();
        } catch (err) {
            showToast('Failed to restore', 'error');
        }
    }

    function escHtml(str) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }
})();
