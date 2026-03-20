import requests
import config


class TMDBClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or config.TMDB_API_KEY
        self.base_url = config.TMDB_BASE_URL
        self.image_base = config.TMDB_IMAGE_BASE
        self.session = requests.Session()

    def _get(self, path, params=None):
        params = params or {}
        headers = {}
        if self.api_key.startswith('eyJ'):
            headers['Authorization'] = f'Bearer {self.api_key}'
        else:
            params['api_key'] = self.api_key
        resp = self.session.get(f'{self.base_url}{path}', params=params,
                                headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def search_series(self, query):
        """Search for TV series on TMDB."""
        data = self._get('/search/tv', {'query': query})
        results = []
        for item in data.get('results', [])[:10]:
            results.append({
                'tmdb_id': item['id'],
                'name': item['name'],
                'first_air_date': item.get('first_air_date', ''),
                'overview': item.get('overview', ''),
                'poster_path': item.get('poster_path', ''),
            })
        return results

    def get_series_details(self, tmdb_id):
        """Get full series details from TMDB."""
        data = self._get(f'/tv/{tmdb_id}')
        return {
            'tmdb_id': data['id'],
            'name': data['name'],
            'poster_path': data.get('poster_path', ''),
            'overview': data.get('overview', ''),
            'series_status': data.get('status', ''),
            'number_of_seasons': data.get('number_of_seasons', 0),
            'number_of_episodes': data.get('number_of_episodes', 0),
            'seasons': [
                {
                    'season_number': s['season_number'],
                    'episode_count': s.get('episode_count', 0),
                    'name': s.get('name', ''),
                }
                for s in data.get('seasons', [])
            ]
        }

    def get_season_episodes(self, tmdb_id, season_number):
        """Get all episodes for a specific season."""
        data = self._get(f'/tv/{tmdb_id}/season/{season_number}')
        episodes = []
        for ep in data.get('episodes', []):
            episodes.append({
                'season_number': ep.get('season_number', season_number),
                'episode_number': ep['episode_number'],
                'name': ep.get('name', ''),
                'air_date': ep.get('air_date', None),
                'overview': ep.get('overview', ''),
            })
        return episodes

    def fetch_all_episodes(self, tmdb_id):
        """Fetch all episodes for a series (skips season 0 / Specials)."""
        details = self.get_series_details(tmdb_id)
        all_episodes = []
        for season in details['seasons']:
            sn = season['season_number']
            if sn == 0:
                continue  # Skip specials
            try:
                eps = self.get_season_episodes(tmdb_id, sn)
                all_episodes.extend(eps)
            except requests.HTTPError:
                continue
        return details, all_episodes

    def check_connection(self):
        """Return True if the API key is valid and TMDB is reachable."""
        try:
            data = self._get('/configuration')
            return bool(data.get('images'))
        except Exception:
            return False

    def poster_url(self, poster_path, size='w342'):
        if not poster_path:
            return ''
        return f'{self.image_base}/{size}{poster_path}'
