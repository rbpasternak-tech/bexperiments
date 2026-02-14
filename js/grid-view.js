// grid-view.js — Monthly grid view

import { getOrCreateMonth, toggleCheck, daysInMonth, parseMonthKey, todayInfo } from './data.js';

export function renderGridView(container, monthKey) {
  const data = getOrCreateMonth(monthKey);
  const { year, month } = parseMonthKey(monthKey);
  const totalDays = daysInMonth(year, month);
  const today = todayInfo();
  const isCurrentMonth = monthKey === today.monthKey;

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

  // Build header row
  let headerCells = '<th class="sticky-col">Habit</th>';
  for (let d = 1; d <= totalDays; d++) {
    const todayClass = (isCurrentMonth && d === today.day) ? ' today' : '';
    headerCells += `<th class="day-col${todayClass}">${d}</th>`;
  }
  headerCells += '<th class="stats-col"></th>';

  // Build body rows
  let bodyRows = '';
  for (const habit of data.habits) {
    const checks = data.checks[habit.id] || [];
    let cells = `<td class="sticky-col" title="${escapeAttr(habit.name)}">${escapeHtml(habit.name)}</td>`;

    for (let d = 1; d <= totalDays; d++) {
      const checked = checks.includes(d);
      const todayClass = (isCurrentMonth && d === today.day) ? ' today' : '';
      const futureClass = (isCurrentMonth && d > today.day) ? ' future' : '';
      cells += `<td class="cell${checked ? ' checked' : ''}${todayClass}${futureClass}" data-habit-id="${habit.id}" data-day="${d}">${checked ? '&#10003;' : ''}</td>`;
    }

    // Stats: checked / elapsed days
    const elapsed = isCurrentMonth ? today.day : totalDays;
    const count = checks.filter(d => d <= elapsed).length;
    cells += `<td class="stats-col">${count}/${elapsed}</td>`;

    bodyRows += `<tr data-habit-id="${habit.id}">${cells}</tr>`;
  }

  container.innerHTML = `
    <div class="grid-view">
      <div class="grid-scroll-container">
        <table class="habit-grid">
          <thead><tr>${headerCells}</tr></thead>
          <tbody>${bodyRows}</tbody>
        </table>
      </div>
    </div>
  `;

  // Auto-scroll to today's column
  if (isCurrentMonth) {
    const scrollContainer = container.querySelector('.grid-scroll-container');
    const stickyWidth = 100;
    const cellWidth = 36;
    const targetScroll = (today.day - 1) * cellWidth - (scrollContainer.clientWidth - stickyWidth) / 2 + cellWidth / 2;
    scrollContainer.scrollLeft = Math.max(0, targetScroll);
  }

  // Event: toggle check on cell tap
  container.querySelector('.habit-grid').addEventListener('click', (e) => {
    const cell = e.target.closest('.cell');
    if (!cell) return;
    const habitId = cell.dataset.habitId;
    const day = Number(cell.dataset.day);
    const nowChecked = toggleCheck(monthKey, habitId, day);
    cell.classList.toggle('checked', nowChecked);
    cell.innerHTML = nowChecked ? '&#10003;' : '';

    // Update stats for this row
    const row = cell.closest('tr');
    const statsCell = row.querySelector('.stats-col');
    if (statsCell) {
      const elapsed = isCurrentMonth ? today.day : totalDays;
      const allCells = row.querySelectorAll('.cell');
      let count = 0;
      allCells.forEach(c => {
        const d = Number(c.dataset.day);
        if (d <= elapsed && c.classList.contains('checked')) count++;
      });
      statsCell.textContent = `${count}/${elapsed}`;
    }
  });
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function escapeAttr(str) {
  return str.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
