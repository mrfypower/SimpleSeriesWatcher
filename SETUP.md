# Simple Series Watcher — Setup & Requirements

## Overview

**Simple Series Watcher** is a self-hosted, web-based episode calendar that lets you track TV series you're watching. It uses [TMDB](https://www.themoviedb.org/) as the data source and stores everything locally in an SQLite database — perfect for running on a personal NAS.

---

## Features & Requirements

### Calendar Overview
- Monthly calendar grid on the main page with every day shown as a tile
- Switch month and year with simple prev/next navigation + "Today" button
- Episodes of your watched series appear in the corresponding day tile (`Series Name S01E05`)
- Watched episodes are shown greyed out and struck through
- Color coding:
  - **Green** — first episode of a season (premiere)
  - **Orange** — last episode of a season (season finale)
  - **Red** — last episode of the entire series (series finale, only when the series has ended/been canceled)
- Click an episode in the calendar to toggle its watched status

### Series Management
- **Add** a series via a search field with live search results from TMDB (debounced, 400 ms)
- **Archive** a series you're no longer watching — watched data is preserved in the database
- **Unarchive** a series to resume tracking
- Archived series do **not** appear in the calendar

### Series List Page (`/series`)
- Grouped into three sections:
  1. **Currently Airing** — status = watching, TMDB status = "Returning Series"
  2. **Ended / Canceled** — status = watching, TMDB status ≠ "Returning Series"
  3. **Archived** — status = archived
- Each entry shows poster thumbnail, name, season count, and TMDB status
- Click a series card to open its detail page

### Series Detail Page (`/series/<id>`)
- Series title with poster image displayed next to it
- Episodes grouped by season
- Checkbox to mark/unmark individual episodes as watched
- "Mark All Watched" / "Unmark All" button per season
- Episode color coding (same as calendar)
- "Refresh from TMDB" button to fetch latest episodes
- Archive / Unarchive button

### Data Source — TMDB
- All series metadata and episode information comes from [TMDB API v3](https://developers.themoviedb.org/3)
- Data is fetched **only** when:
  - Searching for a series to add
  - Adding a new series (initial full fetch)
  - Manually refreshing a series
- After initial fetch, all data is served from the local database — no ongoing TMDB traffic

### Database
- **SQLite** — lightweight, file-based, ideal for NAS hosting (no external DB server needed)
- Tables: `series`, `episodes`
- **Export** — download the full database as a JSON file (`/api/export`)
- **Import** — upload a JSON backup file to restore series and watched status; series data is re-fetched from TMDB on import

### Responsive Design
- Works on desktop and mobile browsers
- Calendar tiles shrink gracefully on small screens
- Navigation collapses into a hamburger menu on mobile

---

## Tech Stack

| Component   | Technology                    |
|-------------|-------------------------------|
| Backend     | Python 3.12 + Flask           |
| Database    | SQLite 3                      |
| API Data    | TMDB API v3                   |
| Frontend    | Vanilla HTML / CSS / JS       |
| Production  | Gunicorn (WSGI server)        |
| Deployment  | Docker + Docker Compose       |

---

## Prerequisites

- **TMDB API Key** — free at <https://www.themoviedb.org/settings/api>
- **Docker + Docker Compose** (recommended for NAS) — OR Python 3.10+ for bare-metal

---

## Setup — Docker (Recommended for NAS)

### 1. Clone or copy the project

```bash
git clone <repo-url> SimpleSeriesWatcher
cd SimpleSeriesWatcher
```

### 2. Create the `.env` file

```bash
cp .env.example .env
```

Edit `.env` and set your TMDB API key:

```
TMDB_API_KEY=your_actual_api_key_here
```

### 3. Build and start

```bash
docker compose up -d --build
```

### 4. Open in browser

Navigate to `http://<your-nas-ip>:5000`

### 5. Stop / restart

```bash
docker compose down      # stop
docker compose up -d     # start again (data persists in Docker volume)
```

---

## Setup — Bare Metal (without Docker)

### 1. Create a virtual environment

```bash
cd SimpleSeriesWatcher
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create the `.env` file

```bash
cp .env.example .env
# Edit .env and set TMDB_API_KEY
```

### 4. Run with Gunicorn (production)

```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app
```

Or for development:

```bash
python app.py
```

### 5. Open in browser

Navigate to `http://localhost:5000`

---

## Project Structure

```
SimpleSeriesWatcher/
├── app.py               # Flask application & API routes
├── config.py            # Configuration (env vars)
├── database.py          # SQLite database operations
├── tmdb_client.py       # TMDB API client
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── .gitignore
├── .dockerignore
├── Dockerfile           # Docker image build
├── docker-compose.yml   # Docker Compose config
├── SETUP.md             # This file
├── data/                # SQLite database (created at runtime)
├── templates/
│   ├── base.html        # Base layout (navbar, scripts)
│   ├── calendar.html    # Calendar page
│   ├── series_list.html # Series list page
│   └── series_detail.html # Series detail page
└── static/
    ├── css/
    │   └── style.css    # Stylesheet
    └── js/
        ├── calendar.js      # Calendar rendering & navigation
        ├── series.js        # Series list & search logic
        └── series_detail.js # Episode management & toggling
```

---

## API Endpoints

| Method | Endpoint                                         | Description                        |
|--------|--------------------------------------------------|------------------------------------|
| GET    | `/api/calendar?year=YYYY&month=MM`               | Episodes for a given month         |
| GET    | `/api/series`                                     | List all series                    |
| GET    | `/api/series/<id>`                                | Series detail with episodes        |
| GET    | `/api/series/search?q=<query>`                   | Search TMDB for TV shows           |
| POST   | `/api/series`  (body: `{tmdb_id}`)               | Add a series                       |
| PUT    | `/api/series/<id>/archive`                       | Archive a series                   |
| PUT    | `/api/series/<id>/unarchive`                     | Unarchive a series                 |
| PUT    | `/api/series/<id>/refresh`                       | Refresh from TMDB                  |
| PUT    | `/api/episodes/<id>/toggle`                      | Toggle episode watched             |
| PUT    | `/api/series/<id>/seasons/<num>/toggle`          | Toggle entire season watched       |
| GET    | `/api/export`                                     | Download JSON backup               |
| POST   | `/api/import`  (multipart file)                   | Upload JSON backup to restore      |

---

## Backup & Restore

### Export

Click **Data → Export JSON** in the navbar, or visit `/api/export` directly. This downloads a JSON file containing all your series and watched episode data.

### Import

Click **Data → Import JSON** in the navbar and select a previously exported JSON file. The import process:
1. Re-fetches each series from TMDB (to get latest data)
2. Restores your watched episode markers
3. Preserves archive status

---

## Updating

### Docker

```bash
cd SimpleSeriesWatcher
git pull                     # or copy new files
docker compose up -d --build
```

### Bare Metal

```bash
cd SimpleSeriesWatcher
source .venv/bin/activate
git pull
pip install -r requirements.txt
# Restart gunicorn
```

---

## Notes

- **Season 0 (Specials)** are skipped to keep the calendar clean.
- **Episode types** are determined dynamically: premiere = episode 1 of a season, season finale = last episode of a season, series finale = last episode of the last season when the show is ended/canceled.
- The SQLite database is stored at `./data/ssw.db` by default (configurable via `DATABASE_PATH` env var).
- All TMDB images are served directly from TMDB's CDN — no images are stored locally.
