// daily-view.js — Daily checklist view

import { getOrCreateMonth, toggleCheck, formatDayLabel, todayInfo, daysInMonth, parseMonthKey } from './data.js';

export function renderDailyView(container, monthKey, day, onNavigate) {
  const data = getOrCreateMonth(monthKey);
  const { year, month } = parseMonthKey(monthKey);
  const totalDays = daysInMonth(year, month);
  const today = todayInfo();
  const isToday = monthKey === today.monthKey && day === today.day;

  // Empty state
  if (data.habits.length === 0) {
    container.innerHTML = `
      <div class="welcome">
        <h2>No habits yet</h2>
        <p>Set up your daily habits for ${new Date(year, month - 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })} to get started.</p>
        <button class="setup-btn" id="welcome-setup">Set Up Habits</button>
      </div>
    `;
    return;
  }

  const checkedCount = data.habits.filter(h =>
    (data.checks[h.id] || []).includes(day)
  ).length;
  const pct = data.habits.length > 0 ? Math.round((checkedCount / data.habits.length) * 100) : 0;

  container.innerHTML = `
    <div class="daily-view">
      <div class="daily-header">
        <button class="day-nav" data-dir="prev" aria-label="Previous day">&#8249;</button>
        <div class="day-label">
          ${formatDayLabel(monthKey, day)}
          ${isToday ? '<span class="today-badge">Today</span>' : ''}
        </div>
        <button class="day-nav" data-dir="next" aria-label="Next day">&#8250;</button>
      </div>
      <ul class="habit-checklist">
        ${data.habits.map(habit => {
          const checked = (data.checks[habit.id] || []).includes(day);
          return `
            <li data-habit-id="${habit.id}" data-day="${day}" class="${checked ? 'checked' : ''}">
              <div class="check-circle">
                <span class="checkmark">&#10003;</span>
              </div>
              <span class="habit-name">${escapeHtml(habit.name)}</span>
            </li>
          `;
        }).join('')}
      </ul>
      <div class="daily-progress">
        ${checkedCount} of ${data.habits.length} done
        <div class="progress-bar">
          <div class="progress-fill" style="width: ${pct}%"></div>
        </div>
      </div>
    </div>
  `;

  // Event: toggle check
  container.querySelector('.habit-checklist').addEventListener('click', (e) => {
    const li = e.target.closest('li[data-habit-id]');
    if (!li) return;
    const habitId = li.dataset.habitId;
    const d = Number(li.dataset.day);
    const nowChecked = toggleCheck(monthKey, habitId, d);
    li.classList.toggle('checked', nowChecked);

    // Update progress
    const allItems = container.querySelectorAll('.habit-checklist li');
    const count = Array.from(allItems).filter(el => el.classList.contains('checked')).length;
    const progress = container.querySelector('.daily-progress');
    const fill = container.querySelector('.progress-fill');
    if (progress && fill) {
      progress.firstChild.textContent = `${count} of ${data.habits.length} done `;
      fill.style.width = `${Math.round((count / data.habits.length) * 100)}%`;
    }
  });

  // Event: day navigation
  container.querySelectorAll('.day-nav').forEach(btn => {
    btn.addEventListener('click', () => {
      const dir = btn.dataset.dir === 'prev' ? -1 : 1;
      navigateDay(monthKey, day, totalDays, dir, onNavigate);
    });
  });

  // Swipe support
  let touchStartX = 0;
  const view = container.querySelector('.daily-view');
  if (view) {
    view.addEventListener('touchstart', (e) => {
      touchStartX = e.touches[0].clientX;
    }, { passive: true });

    view.addEventListener('touchend', (e) => {
      const dx = e.changedTouches[0].clientX - touchStartX;
      if (Math.abs(dx) > 50) {
        const dir = dx > 0 ? -1 : 1; // swipe left = next, swipe right = prev
        navigateDay(monthKey, day, totalDays, dir, onNavigate);
      }
    }, { passive: true });
  }
}

function navigateDay(monthKey, currentDay, totalDays, delta, onNavigate) {
  let newDay = currentDay + delta;
  let newMonthKey = monthKey;

  if (newDay < 1) {
    // Go to previous month's last day
    const { year, month } = parseMonthKey(monthKey);
    let prevMonth = month - 1;
    let prevYear = year;
    if (prevMonth < 1) { prevMonth = 12; prevYear--; }
    newMonthKey = `${prevYear}-${String(prevMonth).padStart(2, '0')}`;
    newDay = daysInMonth(prevYear, prevMonth);
  } else if (newDay > totalDays) {
    // Go to next month's first day
    const { year, month } = parseMonthKey(monthKey);
    let nextMonth = month + 1;
    let nextYear = year;
    if (nextMonth > 12) { nextMonth = 1; nextYear++; }
    newMonthKey = `${nextYear}-${String(nextMonth).padStart(2, '0')}`;
    newDay = 1;
  }

  if (onNavigate) {
    onNavigate(newMonthKey, newDay);
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
