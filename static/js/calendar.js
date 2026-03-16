/* ═══════════════════════════════════════
   Calendar page logic
   ═══════════════════════════════════════ */

const MONTHS = [
    'January','February','March','April','May','June',
    'July','August','September','October','November','December'
];
const DAY_HEADERS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

let currentYear, currentMonth;

function initCalendar(year, month) {
    currentYear = year;
    currentMonth = month;

    document.getElementById('prevMonth').addEventListener('click', () => navigate(-1));
    document.getElementById('nextMonth').addEventListener('click', () => navigate(1));
    document.getElementById('todayBtn').addEventListener('click', () => {
        const now = new Date();
        currentYear = now.getFullYear();
        currentMonth = now.getMonth() + 1;
        loadCalendar();
    });

    loadCalendar();
}

function navigate(delta) {
    currentMonth += delta;
    if (currentMonth > 12) { currentMonth = 1; currentYear++; }
    if (currentMonth < 1) { currentMonth = 12; currentYear--; }
    loadCalendar();
}

async function loadCalendar() {
    document.getElementById('calendarTitle').textContent =
        `${MONTHS[currentMonth - 1]} ${currentYear}`;

    const grid = document.getElementById('calendarGrid');
    grid.innerHTML = '<div class="loader" style="grid-column:1/-1">Loading…</div>';

    try {
        const resp = await fetch(`/api/calendar?year=${currentYear}&month=${currentMonth}`);
        const data = await resp.json();
        renderCalendar(data);
    } catch (err) {
        grid.innerHTML = '<div class="loader" style="grid-column:1/-1">Failed to load calendar</div>';
    }
}

function renderCalendar(data) {
    const grid = document.getElementById('calendarGrid');
    grid.innerHTML = '';

    // Day-of-week headers
    DAY_HEADERS.forEach(d => {
        const el = document.createElement('div');
        el.className = 'calendar-day-header';
        el.textContent = d;
        grid.appendChild(el);
    });

    // Determine first day of month and total days
    const firstDate = new Date(data.year, data.month - 1, 1);
    const daysInMonth = new Date(data.year, data.month, 0).getDate();
    // getDay() returns 0=Sun, adjust so Mon=0
    let startDay = (firstDate.getDay() + 6) % 7;

    const today = new Date();
    const isCurrentMonth = today.getFullYear() === data.year &&
                           (today.getMonth() + 1) === data.month;

    // Empty cells before day 1
    for (let i = 0; i < startDay; i++) {
        const cell = document.createElement('div');
        cell.className = 'calendar-cell empty';
        grid.appendChild(cell);
    }

    // Day cells
    for (let day = 1; day <= daysInMonth; day++) {
        const cell = document.createElement('div');
        cell.className = 'calendar-cell';
        if (isCurrentMonth && day === today.getDate()) {
            cell.classList.add('today');
        }

        const num = document.createElement('div');
        num.className = 'calendar-day-num';
        num.textContent = day;
        cell.appendChild(num);

        const dayStr = String(day);
        const eps = data.days[dayStr] || [];
        eps.forEach(ep => {
            const tag = document.createElement('div');
            let cls = 'calendar-ep ' + ep.type;
            if (ep.watched) cls = 'calendar-ep watched';
            tag.className = cls;
            tag.textContent = `${ep.series_name} S${pad(ep.season)}E${pad(ep.episode)}`;
            tag.title = `${ep.series_name} — S${pad(ep.season)}E${pad(ep.episode)}: ${ep.name || ''}${ep.watched ? ' (watched)' : ''}`;
            tag.addEventListener('click', () => toggleFromCalendar(ep.id, tag));
            cell.appendChild(tag);
        });

        grid.appendChild(cell);
    }

    // Trailing empty cells
    const totalCells = startDay + daysInMonth;
    const remainder = totalCells % 7;
    if (remainder) {
        for (let i = 0; i < 7 - remainder; i++) {
            const cell = document.createElement('div');
            cell.className = 'calendar-cell empty';
            grid.appendChild(cell);
        }
    }
}

async function toggleFromCalendar(episodeId, el) {
    try {
        const resp = await fetch(`/api/episodes/${episodeId}/toggle`, {method: 'PUT'});
        const data = await resp.json();
        // Refresh calendar to update styles
        loadCalendar();
    } catch (err) {
        if (typeof showToast === 'function') showToast('Failed to toggle', 'error');
    }
}

function pad(n) {
    return String(n).padStart(2, '0');
}
