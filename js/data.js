// data.js — Data model and localStorage interface

const MONTH_PREFIX = 'habits_';
const CONFIG_KEY = 'habits_config';

// ===== Month Key Helpers =====

export function todayInfo() {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1; // 1-indexed
  const day = now.getDate();
  return {
    year,
    month,
    day,
    monthKey: toMonthKey(year, month),
  };
}

export function toMonthKey(year, month) {
  return `${year}-${String(month).padStart(2, '0')}`;
}

export function parseMonthKey(monthKey) {
  const [year, month] = monthKey.split('-').map(Number);
  return { year, month };
}

export function offsetMonth(monthKey, delta) {
  let { year, month } = parseMonthKey(monthKey);
  month += delta;
  while (month < 1) { month += 12; year--; }
  while (month > 12) { month -= 12; year++; }
  return toMonthKey(year, month);
}

export function daysInMonth(year, month) {
  return new Date(year, month, 0).getDate();
}

export function formatMonthLabel(monthKey) {
  const { year, month } = parseMonthKey(monthKey);
  const date = new Date(year, month - 1, 1);
  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

export function formatDayLabel(monthKey, day) {
  const { year, month } = parseMonthKey(monthKey);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' });
}

// ===== localStorage Read/Write =====

export function getMonthData(monthKey) {
  const raw = localStorage.getItem(MONTH_PREFIX + monthKey);
  return raw ? JSON.parse(raw) : null;
}

export function saveMonthData(monthKey, data) {
  localStorage.setItem(MONTH_PREFIX + monthKey, JSON.stringify(data));
}

export function getConfig() {
  const raw = localStorage.getItem(CONFIG_KEY);
  return raw ? JSON.parse(raw) : {};
}

export function saveConfig(config) {
  localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
}

// ===== All Month Keys =====

export function getAllMonthKeys() {
  const keys = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key.startsWith(MONTH_PREFIX) && key !== CONFIG_KEY) {
      keys.push(key.replace(MONTH_PREFIX, ''));
    }
  }
  return keys.sort();
}

// ===== Get or Create Month =====

export function getOrCreateMonth(monthKey) {
  const existing = getMonthData(monthKey);
  if (existing) return existing;

  // Find most recent prior month to carry forward
  const allKeys = getAllMonthKeys().filter(k => k < monthKey);
  if (allKeys.length > 0) {
    const priorKey = allKeys[allKeys.length - 1];
    const priorData = getMonthData(priorKey);
    const newData = {
      month: monthKey,
      habits: priorData.habits.map(h => ({ ...h })),
      checks: {},
    };
    for (const habit of newData.habits) {
      newData.checks[habit.id] = [];
    }
    saveMonthData(monthKey, newData);
    return newData;
  }

  // First time ever — return empty (no habits yet)
  const newData = {
    month: monthKey,
    habits: [],
    checks: {},
  };
  saveMonthData(monthKey, newData);
  return newData;
}

// ===== Toggle Check =====

export function toggleCheck(monthKey, habitId, day) {
  const data = getMonthData(monthKey);
  if (!data) return false;

  if (!data.checks[habitId]) {
    data.checks[habitId] = [];
  }

  const arr = data.checks[habitId];
  const idx = arr.indexOf(day);
  if (idx === -1) {
    arr.push(day);
    arr.sort((a, b) => a - b);
  } else {
    arr.splice(idx, 1);
  }

  saveMonthData(monthKey, data);
  return idx === -1; // returns true if now checked
}

// ===== Update Habits =====

export function updateHabits(monthKey, habits) {
  const data = getOrCreateMonth(monthKey);
  const newChecks = {};
  for (const habit of habits) {
    newChecks[habit.id] = data.checks[habit.id] || [];
  }
  data.habits = habits;
  data.checks = newChecks;
  saveMonthData(monthKey, data);
  return data;
}

// ===== Generate unique ID =====

export function generateId() {
  return 'h' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}
