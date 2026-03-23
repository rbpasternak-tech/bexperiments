// stats-view.js — All-time statistics view

import { getAllMonthKeys, getMonthData, todayInfo, daysInMonth, parseMonthKey } from './data.js';

export function renderStatsView(container) {
  const today = todayInfo();
  const allKeys = getAllMonthKeys();

  if (allKeys.length === 0) {
    container.innerHTML = `<div class="welcome"><h2>No data yet</h2><p>Start tracking habits to see your stats.</p></div>`;
    return;
  }

  const currentData = getMonthData(today.monthKey) || { habits: [], checks: {} };

  if (currentData.habits.length === 0) {
    container.innerHTML = `<div class="welcome"><h2>No habits set up</h2><p>Add habits to start tracking.</p></div>`;
    return;
  }

  const habitStats = currentData.habits.map(habit => computeHabitStats(habit, allKeys, today));

  // Summary cards
  const totalChecks   = habitStats.reduce((s, h) => s + h.totalChecked, 0);
  const totalPossible = habitStats.reduce((s, h) => s + h.totalDays, 0);
  const overallRate   = totalPossible > 0 ? Math.round((totalChecks / totalPossible) * 100) : 0;

  const elapsed = today.day;
  const thisMonthChecked  = currentData.habits.reduce((s, h) => {
    return s + (currentData.checks[h.id] || []).filter(d => d <= elapsed).length;
  }, 0);
  const thisMonthPossible = currentData.habits.length * elapsed;
  const thisMonthRate     = thisMonthPossible > 0 ? Math.round((thisMonthChecked / thisMonthPossible) * 100) : 0;

  const bestCurrentStreak = habitStats.length > 0 ? Math.max(...habitStats.map(h => h.currentStreak)) : 0;
  const bestEverStreak    = habitStats.length > 0 ? Math.max(...habitStats.map(h => h.bestStreak)) : 0;

  container.innerHTML = `
    <div class="stats-view">
      <div class="stats-summary">
        <div class="stat-card">
          <div class="stat-value">${thisMonthRate}%</div>
          <div class="stat-label">This month</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${overallRate}%</div>
          <div class="stat-label">All time</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${bestCurrentStreak}</div>
          <div class="stat-label">Current streak</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${bestEverStreak}</div>
          <div class="stat-label">Best streak</div>
        </div>
      </div>

      <h2 class="stats-section-title">Per Habit</h2>
      <ul class="habit-stats-list">
        ${habitStats.map(h => `
          <li class="habit-stat-item">
            <div class="habit-stat-header">
              <span class="habit-stat-name">${escapeHtml(h.name)}</span>
              <span class="habit-stat-streak">${h.currentStreak} day streak</span>
            </div>
            <div class="habit-stat-bar-wrap">
              <div class="habit-stat-bar">
                <div class="habit-stat-fill" style="width: ${h.monthRate}%"></div>
              </div>
              <span class="habit-stat-pct">${h.monthRate}%</span>
            </div>
            <div class="habit-stat-meta">
              <span>${h.totalChecked} of ${h.totalDays} days checked all time</span>
              <span>Best: ${h.bestStreak} days</span>
            </div>
          </li>
        `).join('')}
      </ul>

      <p class="stats-footer">${allKeys.length} month${allKeys.length !== 1 ? 's' : ''} of data</p>
    </div>
  `;
}

function computeHabitStats(habit, allKeys, today) {
  let totalDays = 0;
  let totalChecked = 0;
  const timeline = []; // ordered oldest → newest: {checked: bool}

  for (const key of allKeys) {
    const data = getMonthData(key);
    if (!data) continue;
    if (!data.habits.find(h => h.id === habit.id)) continue;

    const { year, month } = parseMonthKey(key);
    const isCurrentMonth = key === today.monthKey;
    const lastDay = isCurrentMonth ? today.day : daysInMonth(year, month);
    const checks = data.checks[habit.id] || [];

    for (let d = 1; d <= lastDay; d++) {
      const checked = checks.includes(d);
      totalDays++;
      if (checked) totalChecked++;
      timeline.push({ checked });
    }
  }

  // This month rate
  const thisMonthData = getMonthData(today.monthKey);
  let monthRate = 0;
  if (thisMonthData && thisMonthData.habits.find(h => h.id === habit.id)) {
    const checks = thisMonthData.checks[habit.id] || [];
    const monthChecked = checks.filter(d => d <= today.day).length;
    monthRate = today.day > 0 ? Math.round((monthChecked / today.day) * 100) : 0;
  }

  const allTimeRate = totalDays > 0 ? Math.round((totalChecked / totalDays) * 100) : 0;

  // Best streak
  let bestStreak = 0;
  let run = 0;
  for (const { checked } of timeline) {
    run = checked ? run + 1 : 0;
    if (run > bestStreak) bestStreak = run;
  }

  // Current streak (backwards from end)
  let currentStreak = 0;
  for (let i = timeline.length - 1; i >= 0; i--) {
    if (timeline[i].checked) currentStreak++;
    else break;
  }

  return { name: habit.name, totalDays, totalChecked, monthRate, allTimeRate, currentStreak, bestStreak };
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
