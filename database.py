import sqlite3
import os
from datetime import datetime


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self):
        conn = self.get_connection()
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tmdb_id INTEGER UNIQUE NOT NULL,
                name TEXT NOT NULL,
                poster_path TEXT,
                overview TEXT,
                status TEXT DEFAULT 'watching',
                series_status TEXT,
                number_of_seasons INTEGER DEFAULT 0,
                number_of_episodes INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id INTEGER NOT NULL,
                season_number INTEGER NOT NULL,
                episode_number INTEGER NOT NULL,
                name TEXT,
                air_date TEXT,
                watched INTEGER DEFAULT 0,
                FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE,
                UNIQUE(series_id, season_number, episode_number)
            );

            CREATE INDEX IF NOT EXISTS idx_episodes_air_date ON episodes(air_date);
            CREATE INDEX IF NOT EXISTS idx_episodes_series ON episodes(series_id);
            CREATE INDEX IF NOT EXISTS idx_series_status ON series(status);
        ''')
        conn.commit()
        conn.close()

    # ── Series operations ──

    def add_series(self, tmdb_id, name, poster_path, overview, series_status,
                   num_seasons, num_episodes):
        conn = self.get_connection()
        try:
            existing = conn.execute(
                'SELECT id, status FROM series WHERE tmdb_id = ?', (tmdb_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    '''UPDATE series SET status='watching', name=?, poster_path=?,
                       overview=?, series_status=?, number_of_seasons=?,
                       number_of_episodes=?, last_updated=? WHERE id=?''',
                    (name, poster_path, overview, series_status, num_seasons,
                     num_episodes, datetime.now().isoformat(), existing['id'])
                )
                conn.commit()
                return existing['id']
            else:
                cursor = conn.execute(
                    '''INSERT INTO series
                       (tmdb_id, name, poster_path, overview, status,
                        series_status, number_of_seasons, number_of_episodes)
                       VALUES (?,?,?,?,?,?,?,?)''',
                    (tmdb_id, name, poster_path, overview, 'watching',
                     series_status, num_seasons, num_episodes)
                )
                conn.commit()
                return cursor.lastrowid
        finally:
            conn.close()

    def update_series_meta(self, series_id, name, poster_path, overview,
                           series_status, num_seasons, num_episodes):
        conn = self.get_connection()
        try:
            conn.execute(
                '''UPDATE series SET name=?, poster_path=?, overview=?,
                   series_status=?, number_of_seasons=?, number_of_episodes=?,
                   last_updated=? WHERE id=?''',
                (name, poster_path, overview, series_status, num_seasons,
                 num_episodes, datetime.now().isoformat(), series_id)
            )
            conn.commit()
        finally:
            conn.close()

    def archive_series(self, series_id):
        conn = self.get_connection()
        try:
            conn.execute("UPDATE series SET status='archived' WHERE id=?",
                         (series_id,))
            conn.commit()
        finally:
            conn.close()

    def unarchive_series(self, series_id):
        conn = self.get_connection()
        try:
            conn.execute("UPDATE series SET status='watching' WHERE id=?",
                         (series_id,))
            conn.commit()
        finally:
            conn.close()

    def get_all_series(self):
        conn = self.get_connection()
        try:
            rows = conn.execute(
                '''SELECT s.*,
                          (SELECT MIN(e.air_date)
                           FROM episodes e
                           WHERE e.series_id = s.id
                           AND e.air_date >= date('now')
                           AND e.watched = 0) as next_air_date
                   FROM series s
                   ORDER BY s.name'''
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_series(self, series_id):
        conn = self.get_connection()
        try:
            row = conn.execute(
                'SELECT * FROM series WHERE id=?', (series_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_series_by_tmdb_id(self, tmdb_id):
        conn = self.get_connection()
        try:
            row = conn.execute(
                'SELECT * FROM series WHERE tmdb_id=?', (tmdb_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ── Episode operations ──

    def upsert_episodes(self, series_id, episodes):
        """Insert or update episodes, preserving watched status."""
        conn = self.get_connection()
        try:
            for ep in episodes:
                conn.execute(
                    '''INSERT INTO episodes
                       (series_id, season_number, episode_number, name, air_date)
                       VALUES (?,?,?,?,?)
                       ON CONFLICT(series_id, season_number, episode_number)
                       DO UPDATE SET name=excluded.name, air_date=excluded.air_date''',
                    (series_id, ep['season_number'], ep['episode_number'],
                     ep['name'], ep['air_date'])
                )
            conn.commit()
        finally:
            conn.close()

    def get_episodes_for_series(self, series_id):
        conn = self.get_connection()
        try:
            rows = conn.execute(
                '''SELECT * FROM episodes WHERE series_id=?
                   ORDER BY season_number, episode_number''',
                (series_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def toggle_episode(self, episode_id):
        conn = self.get_connection()
        try:
            conn.execute(
                'UPDATE episodes SET watched = 1 - watched WHERE id=?',
                (episode_id,)
            )
            conn.commit()
            row = conn.execute(
                'SELECT watched FROM episodes WHERE id=?', (episode_id,)
            ).fetchone()
            return row['watched'] if row else None
        finally:
            conn.close()

    def set_season_watched(self, series_id, season_number, watched):
        conn = self.get_connection()
        try:
            conn.execute(
                '''UPDATE episodes SET watched=?
                   WHERE series_id=? AND season_number=?''',
                (1 if watched else 0, series_id, season_number)
            )
            conn.commit()
        finally:
            conn.close()

    def mark_series_watched(self, series_id):
        conn = self.get_connection()
        try:
            conn.execute(
                'UPDATE episodes SET watched=1 WHERE series_id=?',
                (series_id,)
            )
            conn.commit()
        finally:
            conn.close()

    def is_season_fully_watched(self, series_id, season_number):
        conn = self.get_connection()
        try:
            row = conn.execute(
                '''SELECT COUNT(*) as total,
                          SUM(watched) as watched_count
                   FROM episodes
                   WHERE series_id=? AND season_number=?''',
                (series_id, season_number)
            ).fetchone()
            if row and row['total'] > 0:
                return row['watched_count'] == row['total']
            return False
        finally:
            conn.close()

    # ── Calendar ──

    def get_calendar_episodes(self, year, month):
        conn = self.get_connection()
        try:
            start_date = f'{year:04d}-{month:02d}-01'
            if month == 12:
                end_date = f'{year + 1:04d}-01-01'
            else:
                end_date = f'{year:04d}-{month + 1:02d}-01'

            episodes = conn.execute(
                '''SELECT e.id, e.series_id, e.season_number, e.episode_number,
                          e.name, e.air_date, e.watched,
                          s.name as series_name, s.series_status,
                          s.number_of_seasons
                   FROM episodes e
                   JOIN series s ON e.series_id = s.id
                   WHERE e.air_date >= ? AND e.air_date < ?
                   AND s.status = 'watching'
                   ORDER BY e.air_date, s.name, e.season_number,
                            e.episode_number''',
                (start_date, end_date)
            ).fetchall()

            # Pre-compute max episode per (series, season) for finale detection
            season_max = {}
            for ep in episodes:
                key = (ep['series_id'], ep['season_number'])
                if key not in season_max:
                    row = conn.execute(
                        '''SELECT MAX(episode_number) as max_ep
                           FROM episodes
                           WHERE series_id=? AND season_number=?''',
                        (ep['series_id'], ep['season_number'])
                    ).fetchone()
                    season_max[key] = row['max_ep'] if row else 0

            result = []
            for ep in episodes:
                d = dict(ep)
                key = (ep['series_id'], ep['season_number'])
                max_ep = season_max.get(key, 0)

                # Determine type with priority:
                # series_finale > season_finale > premiere > normal
                ep_type = 'normal'
                if ep['episode_number'] == 1:
                    ep_type = 'premiere'
                if ep['episode_number'] == max_ep and max_ep > 0:
                    is_last_season = (
                        ep['season_number'] == ep['number_of_seasons']
                    )
                    series_ended = ep['series_status'] in (
                        'Ended', 'Canceled'
                    )
                    if is_last_season and series_ended:
                        ep_type = 'series-finale'
                    else:
                        ep_type = 'season-finale'
                d['type'] = ep_type
                result.append(d)

            return result
        finally:
            conn.close()

    # ── Export / Import ──

    def export_data(self):
        conn = self.get_connection()
        try:
            series_list = conn.execute('SELECT * FROM series').fetchall()
            data = []
            for s in series_list:
                watched = conn.execute(
                    '''SELECT season_number, episode_number
                       FROM episodes
                       WHERE series_id=? AND watched=1
                       ORDER BY season_number, episode_number''',
                    (s['id'],)
                ).fetchall()
                data.append({
                    'tmdb_id': s['tmdb_id'],
                    'name': s['name'],
                    'status': s['status'],
                    'watched_episodes': [
                        {'season': w['season_number'],
                         'episode': w['episode_number']}
                        for w in watched
                    ]
                })
            return {
                'app': 'Simple Series Watcher',
                'version': '1.0',
                'exported_at': datetime.now().isoformat(),
                'data': {'series': data}
            }
        finally:
            conn.close()

    def import_watched(self, series_id, watched_episodes):
        """Mark specific episodes as watched from an import."""
        conn = self.get_connection()
        try:
            for w in watched_episodes:
                conn.execute(
                    '''UPDATE episodes SET watched=1
                       WHERE series_id=? AND season_number=?
                       AND episode_number=?''',
                    (series_id, w['season'], w['episode'])
                )
            conn.commit()
        finally:
            conn.close()

    def delete_series_episodes(self, series_id):
        """Remove all episodes for a series (used before full refresh)."""
        conn = self.get_connection()
        try:
            conn.execute('DELETE FROM episodes WHERE series_id=?',
                         (series_id,))
            conn.commit()
        finally:
            conn.close()

    def get_unwatched_episodes(self):
        """Return all unwatched episodes for 'watching' series, ordered by series name,
        season, and episode number."""
        conn = self.get_connection()
        try:
            rows = conn.execute(
                '''SELECT e.id, e.series_id, e.season_number, e.episode_number,
                          e.name, e.air_date,
                          s.name as series_name, s.poster_path
                   FROM episodes e
                   JOIN series s ON e.series_id = s.id
                   WHERE e.watched = 0
                   AND s.status = 'watching'
                   ORDER BY s.name, e.season_number, e.episode_number'''
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
