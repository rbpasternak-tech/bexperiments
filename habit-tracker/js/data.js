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

const CORRUPT_BACKUP_PREFIX = 'corrupt-backup:';

/**
 * Reads and parses a JSON value from localStorage.
 * Unparseable or invalid values are copied to a backup key (outside the
 * habits_ namespace, so they are never read as a month) and logged, then
 * treated as missing so the app keeps working instead of crashing.
 * @param {string} key - localStorage key.
 * @param {Function} isValid - Returns true if the parsed value is usable.
 * @returns {*} The parsed value, or null if missing or corrupt.
 */
function readJson(key, isValid) {
  const raw = localStorage.getItem(key);
  if (raw === null) return null;
  try {
    const value = JSON.parse(raw);
    if (isValid(value)) return value;
  } catch (_) {
    // Fall through to backup below.
  }
  let backupKey = CORRUPT_BACKUP_PREFIX + key;
  try {
    const existing = localStorage.getItem(backupKey);
    if (existing !== null && existing !== raw) {
      backupKey += ':' + Date.now();
    }
    if (existing !== raw) {
      localStorage.setItem(backupKey, raw);
    }
    console.error(`Habit Tracker: stored data for "${key}" is corrupt; backed it up to "${backupKey}".`);
  } catch (err) {
    console.error(`Habit Tracker: stored data for "${key}" is corrupt and could not be backed up. Raw value:`, raw, err);
  }
  return null;
}

const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

export function getMonthData(monthKey) {
  return readJson(MONTH_PREFIX + monthKey, (v) => isObject(v) && Array.isArray(v.habits) && isObject(v.checks));
}

export function saveMonthData(monthKey, data) {
  localStorage.setItem(MONTH_PREFIX + monthKey, JSON.stringify(data));
}

export function getConfig() {
  return readJson(CONFIG_KEY, isObject) || {};
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
  let priorData = null;
  for (let i = allKeys.length - 1; i >= 0 && !priorData; i--) {
    priorData = getMonthData(allKeys[i]);
  }
  if (priorData) {
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
