// app.js — App initialization, view routing, event wiring

import { getOrCreateMonth, getConfig, saveConfig, todayInfo, formatMonthLabel, offsetMonth } from './data.js';
import { renderDailyView } from './daily-view.js';
import { renderGridView } from './grid-view.js';
import { renderStatsView } from './stats-view.js';
import { openHabitEditor } from './habit-editor.js';

const state = {
  currentMonthKey: null,
  currentDay: null,
  currentView: 'daily',
};

function init() {
  const config = getConfig();
  const today = todayInfo();

  state.currentMonthKey = today.monthKey;
  state.currentDay = today.day;
  state.currentView = config.currentView || 'daily';

  // Ensure current month data exists
  getOrCreateMonth(state.currentMonthKey);

  bindEvents();
  render();

  // Register service worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./service-worker.js').catch(() => {});
  }
}

function render() {
  const container = document.getElementById('app-content');
  const isStats = state.currentView === 'stats';

  document.getElementById('month-label').textContent =
    isStats ? 'Statistics' : formatMonthLabel(state.currentMonthKey);

  // Show/hide month nav in stats view
  document.getElementById('prev-month').style.visibility = isStats ? 'hidden' : '';
  document.getElementById('next-month').style.visibility = isStats ? 'hidden' : '';

  // Update toggle buttons
  document.getElementById('btn-daily').classList.toggle('active', state.currentView === 'daily');
  document.getElementById('btn-grid').classList.toggle('active', state.currentView === 'grid');
  document.getElementById('btn-stats').classList.toggle('active', state.currentView === 'stats');

  if (state.currentView === 'daily') {
    renderDailyView(container, state.currentMonthKey, state.currentDay, (newMonthKey, newDay) => {
      if (newMonthKey !== state.currentMonthKey) {
        state.currentMonthKey = newMonthKey;
        document.getElementById('month-label').textContent = formatMonthLabel(state.currentMonthKey);
      }
      state.currentDay = newDay;
      render();
    });
  } else if (state.currentView === 'grid') {
    renderGridView(container, state.currentMonthKey);
  } else {
    renderStatsView(container);
  }

  // Wire up welcome setup button if present
  const welcomeBtn = document.getElementById('welcome-setup');
  if (welcomeBtn) {
    welcomeBtn.addEventListener('click', () => {
      openHabitEditor(state.currentMonthKey, () => render());
    });
  }

  saveConfig({ currentView: state.currentView, lastActiveMonth: state.currentMonthKey });
}

function bindEvents() {
  // View toggle
  document.getElementById('btn-daily').addEventListener('click', () => {
    if (state.currentView === 'daily') return;
    state.currentView = 'daily';
    // Reset to today when switching to daily
    const today = todayInfo();
    if (state.currentMonthKey === today.monthKey) {
      state.currentDay = today.day;
    }
    render();
  });

  document.getElementById('btn-grid').addEventListener('click', () => {
    if (state.currentView === 'grid') return;
    state.currentView = 'grid';
    render();
  });

  document.getElementById('btn-stats').addEventListener('click', () => {
    if (state.currentView === 'stats') return;
    state.currentView = 'stats';
    render();
  });

  // Month navigation
  document.getElementById('prev-month').addEventListener('click', () => {
    state.currentMonthKey = offsetMonth(state.currentMonthKey, -1);
    state.currentDay = 1;
    getOrCreateMonth(state.currentMonthKey);
    render();
  });

  document.getElementById('next-month').addEventListener('click', () => {
    state.currentMonthKey = offsetMonth(state.currentMonthKey, 1);
    state.currentDay = 1;
    getOrCreateMonth(state.currentMonthKey);
    render();
  });

  // Edit habits
  document.getElementById('btn-edit-habits').addEventListener('click', () => {
    openHabitEditor(state.currentMonthKey, () => render());
  });
}

// Boot
document.addEventListener('DOMContentLoaded', init);
