import csv
import io
import json
from datetime import date

from flask import (Flask, render_template, request, jsonify, Response)
import requests

import config
from database import Database
from tmdb_client import TMDBClient

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

db = Database(config.DATABASE_PATH)
tmdb = TMDBClient()

# ─────────────────────────────────────────────
# Page routes
# ─────────────────────────────────────────────

@app.route('/')
def calendar_page():
    today = date.today()
    return render_template('calendar.html',
                           year=today.year, month=today.month)


@app.route('/series')
def series_list_page():
    return render_template('series_list.html')


@app.route('/series/<int:series_id>')
def series_detail_page(series_id):
    s = db.get_series(series_id)
    if not s:
        return "Series not found", 404
    return render_template('series_detail.html', series=s)


@app.route('/unwatched')
def unwatched_page():
    return render_template('unwatched.html')


# ─────────────────────────────────────────────
# API — Health check
# ─────────────────────────────────────────────

@app.route('/api/health')
def api_health():
    ok = tmdb.check_connection()
    return jsonify({'tmdb': ok})


# ─────────────────────────────────────────────
# API — Calendar
# ─────────────────────────────────────────────

@app.route('/api/calendar')
def api_calendar():
    try:
        year = int(request.args.get('year', date.today().year))
        month = int(request.args.get('month', date.today().month))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid year/month'}), 400

    episodes = db.get_calendar_episodes(year, month)

    days = {}
    for ep in episodes:
        day = ep['air_date'][8:10].lstrip('0') if ep.get('air_date') else None
        if day:
            days.setdefault(day, []).append({
                'id': ep['id'],
                'series_id': ep['series_id'],
                'series_name': ep['series_name'],
                'season': ep['season_number'],
                'episode': ep['episode_number'],
                'name': ep['name'],
                'watched': bool(ep['watched']),
                'type': ep['type'],
            })

    return jsonify({'year': year, 'month': month, 'days': days})


# ─────────────────────────────────────────────
# API — Series CRUD
# ─────────────────────────────────────────────

@app.route('/api/series')
def api_series_list():
    all_series = db.get_all_series()
    for s in all_series:
        s['poster_url'] = tmdb.poster_url(s.get('poster_path'), 'w185')
    return jsonify(all_series)


@app.route('/api/series/<int:series_id>')
def api_series_detail(series_id):
    s = db.get_series(series_id)
    if not s:
        return jsonify({'error': 'Not found'}), 404

    episodes = db.get_episodes_for_series(series_id)
    s['poster_url'] = tmdb.poster_url(s.get('poster_path'), 'w342')

    # Group episodes by season and compute episode type
    seasons = {}
    for ep in episodes:
        sn = ep['season_number']
        seasons.setdefault(sn, []).append(ep)

    enriched_seasons = {}
    for sn, eps in sorted(seasons.items()):
        max_ep = max(e['episode_number'] for e in eps) if eps else 0
        enriched = []
        for ep in eps:
            ep_type = 'normal'
            if ep['episode_number'] == 1:
                ep_type = 'premiere'
            if ep['episode_number'] == max_ep and max_ep > 0:
                is_last_season = sn == s['number_of_seasons']
                ended = s['series_status'] in ('Ended', 'Canceled')
                if is_last_season and ended:
                    ep_type = 'series-finale'
                else:
                    ep_type = 'season-finale'
            ep['type'] = ep_type
            enriched.append(ep)
        fully_watched = all(e['watched'] for e in eps) if eps else False
        enriched_seasons[str(sn)] = {
            'episodes': enriched,
            'fully_watched': fully_watched,
        }

    s['seasons'] = enriched_seasons
    return jsonify(s)


@app.route('/api/series/search')
def api_search():
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    try:
        results = tmdb.search_series(query)
        for r in results:
            r['poster_url'] = tmdb.poster_url(r.get('poster_path'), 'w92')
        return jsonify(results)
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 502


@app.route('/api/series', methods=['POST'])
def api_add_series():
    data = request.get_json()
    if not data or 'tmdb_id' not in data:
        return jsonify({'error': 'tmdb_id required'}), 400

    tmdb_id = int(data['tmdb_id'])

    # Check if already exists and active
    existing = db.get_series_by_tmdb_id(tmdb_id)
    if existing and existing['status'] == 'watching':
        return jsonify({'error': 'Series already added', 'id': existing['id']}), 409

    try:
        details, all_episodes = tmdb.fetch_all_episodes(tmdb_id)
    except requests.RequestException as e:
        return jsonify({'error': f'TMDB error: {e}'}), 502

    series_id = db.add_series(
        tmdb_id=details['tmdb_id'],
        name=details['name'],
        poster_path=details['poster_path'],
        overview=details['overview'],
        series_status=details['series_status'],
        num_seasons=details['number_of_seasons'],
        num_episodes=details['number_of_episodes'],
    )
    db.upsert_episodes(series_id, all_episodes)

    return jsonify({'id': series_id, 'name': details['name']}), 201


@app.route('/api/series/<int:series_id>/mark-watched', methods=['PUT'])
def api_mark_series_watched(series_id):
    if not db.get_series(series_id):
        return jsonify({'error': 'Not found'}), 404
    db.mark_series_watched(series_id)
    return jsonify({'ok': True})


@app.route('/api/series/<int:series_id>/archive', methods=['PUT'])
def api_archive(series_id):
    db.archive_series(series_id)
    return jsonify({'ok': True})


@app.route('/api/series/<int:series_id>/unarchive', methods=['PUT'])
def api_unarchive(series_id):
    db.unarchive_series(series_id)
    return jsonify({'ok': True})


@app.route('/api/series/<int:series_id>/refresh', methods=['PUT'])
def api_refresh(series_id):
    s = db.get_series(series_id)
    if not s:
        return jsonify({'error': 'Not found'}), 404
    try:
        details, all_episodes = tmdb.fetch_all_episodes(s['tmdb_id'])
    except requests.RequestException as e:
        return jsonify({'error': f'TMDB error: {e}'}), 502

    db.update_series_meta(
        series_id,
        name=details['name'],
        poster_path=details['poster_path'],
        overview=details['overview'],
        series_status=details['series_status'],
        num_seasons=details['number_of_seasons'],
        num_episodes=details['number_of_episodes'],
    )
    db.upsert_episodes(series_id, all_episodes)
    return jsonify({'ok': True})


# ─────────────────────────────────────────────
# API — Episode toggling
# ─────────────────────────────────────────────

@app.route('/api/episodes/<int:episode_id>/toggle', methods=['PUT'])
def api_toggle_episode(episode_id):
    new_val = db.toggle_episode(episode_id)
    if new_val is None:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'watched': bool(new_val)})


# ─────────────────────────────────────────────
# API — Unwatched
# ─────────────────────────────────────────────

@app.route('/api/unwatched')
def api_unwatched():
    episodes = db.get_unwatched_episodes()

    series_map = {}
    series_order = []
    for ep in episodes:
        sid = ep['series_id']
        if sid not in series_map:
            series_map[sid] = {
                'id': sid,
                'name': ep['series_name'],
                'poster_url': tmdb.poster_url(ep.get('poster_path'), 'w185'),
                'seasons': {},
            }
            series_order.append(sid)
        sn = str(ep['season_number'])
        series_map[sid]['seasons'].setdefault(sn, []).append({
            'id': ep['id'],
            'season_number': ep['season_number'],
            'episode_number': ep['episode_number'],
            'name': ep['name'],
            'air_date': ep['air_date'],
        })

    return jsonify([series_map[sid] for sid in series_order])


@app.route('/api/series/<int:series_id>/seasons/<int:season_number>/toggle',
           methods=['PUT'])
def api_toggle_season(series_id, season_number):
    fully = db.is_season_fully_watched(series_id, season_number)
    db.set_season_watched(series_id, season_number, not fully)
    return jsonify({'watched': not fully})


# ─────────────────────────────────────────────
# API — Export / Import
# ─────────────────────────────────────────────

@app.route('/api/export')
def api_export():
    data = db.export_data()
    return Response(
        json.dumps(data, indent=2, ensure_ascii=False),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=ssw_backup.json'}
    )


@app.route('/api/import', methods=['POST'])
def api_import():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    f = request.files['file']
    try:
        raw = f.read()
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return jsonify({'error': 'Invalid JSON file'}), 400

    if 'data' not in data or 'series' not in data.get('data', {}):
        return jsonify({'error': 'Invalid backup format'}), 400

    results = []
    for entry in data['data']['series']:
        tmdb_id = entry.get('tmdb_id')
        if not tmdb_id:
            continue

        try:
            details, all_episodes = tmdb.fetch_all_episodes(tmdb_id)
        except requests.RequestException:
            results.append({'tmdb_id': tmdb_id, 'status': 'tmdb_error'})
            continue

        series_id = db.add_series(
            tmdb_id=details['tmdb_id'],
            name=details['name'],
            poster_path=details['poster_path'],
            overview=details['overview'],
            series_status=details['series_status'],
            num_seasons=details['number_of_seasons'],
            num_episodes=details['number_of_episodes'],
        )
        db.upsert_episodes(series_id, all_episodes)

        # Restore status
        if entry.get('status') == 'archived':
            db.archive_series(series_id)

        # Restore watched episodes
        watched = entry.get('watched_episodes', [])
        if watched:
            db.import_watched(series_id, watched)

        results.append({'tmdb_id': tmdb_id, 'name': details['name'],
                        'status': 'ok'})

    return jsonify({'results': results})


@app.route('/api/import/csv', methods=['POST'])
def api_import_csv():
    """Import series and watched status from an episodecalendar.com CSV export."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    f = request.files['file']
    try:
        raw = f.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        return jsonify({'error': 'Invalid file encoding'}), 400

    reader = csv.DictReader(io.StringIO(raw))
    required = {'show', 'season', 'number', 'watched'}
    if not required.issubset(set(reader.fieldnames or [])):
        return jsonify({'error': 'Invalid CSV format. Expected columns: show, season, number, watched'}), 400

    # Group episodes by show name
    shows = {}
    for row in reader:
        name = row['show'].strip()
        if not name:
            continue
        shows.setdefault(name, []).append({
            'season': int(row['season']),
            'episode': int(row['number']),
            'watched': row['watched'].strip().lower() == 'true',
        })

    results = []
    for show_name, episodes in shows.items():
        # Search TMDB for the show
        try:
            search_results = tmdb.search_series(show_name)
        except requests.RequestException:
            results.append({'name': show_name, 'status': 'tmdb_search_error'})
            continue

        if not search_results:
            results.append({'name': show_name, 'status': 'not_found'})
            continue

        tmdb_id = search_results[0]['tmdb_id']

        try:
            details, all_episodes = tmdb.fetch_all_episodes(tmdb_id)
        except requests.RequestException:
            results.append({'name': show_name, 'status': 'tmdb_error'})
            continue

        series_id = db.add_series(
            tmdb_id=details['tmdb_id'],
            name=details['name'],
            poster_path=details['poster_path'],
            overview=details['overview'],
            series_status=details['series_status'],
            num_seasons=details['number_of_seasons'],
            num_episodes=details['number_of_episodes'],
        )
        db.upsert_episodes(series_id, all_episodes)

        # Mark watched episodes
        watched = [ep for ep in episodes if ep['watched']]
        if watched:
            db.import_watched(series_id, watched)

        results.append({
            'name': details['name'],
            'tmdb_id': tmdb_id,
            'status': 'ok',
            'episodes_imported': len(episodes),
            'episodes_watched': len(watched),
        })

    ok_count = sum(1 for r in results if r['status'] == 'ok')
    fail_count = len(results) - ok_count
    return jsonify({'results': results, 'imported': ok_count, 'failed': fail_count})


# ─────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT, debug=False)
