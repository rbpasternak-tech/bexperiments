// habit-editor.js — Modal for editing monthly habit list

import { getOrCreateMonth, updateHabits, generateId, formatMonthLabel } from './data.js';

let currentOnSave = null;

export function openHabitEditor(monthKey, onSave) {
  currentOnSave = onSave;
  const modal = document.getElementById('habit-editor-modal');
  const content = modal.querySelector('.modal-content');
  const data = getOrCreateMonth(monthKey);

  // Clone habits for editing
  const editHabits = data.habits.length > 0
    ? data.habits.map(h => ({ ...h }))
    : [];

  content.innerHTML = `
    <h2 class="modal-title">Habits for ${formatMonthLabel(monthKey)}</h2>
    <ul class="habit-editor-list" id="editor-list">
      ${editHabits.map(h => habitItemHtml(h)).join('')}
    </ul>
    <button class="add-habit-btn" id="add-habit-btn">+ Add Habit</button>
    <div class="modal-actions">
      <button class="btn-cancel" id="editor-cancel">Cancel</button>
      <button class="btn-save" id="editor-save">Save</button>
    </div>
  `;

  modal.classList.remove('hidden');

  // Focus first empty input if any
  const firstEmpty = content.querySelector('input[value=""]');
  if (firstEmpty) firstEmpty.focus();

  // Event: add habit
  content.querySelector('#add-habit-btn').addEventListener('click', () => {
    const list = content.querySelector('#editor-list');
    const count = list.querySelectorAll('.habit-editor-item').length;
    if (count >= 15) {
      alert('Maximum 15 habits per month.');
      return;
    }
    const newHabit = { id: generateId(), name: '', order: count };
    list.insertAdjacentHTML('beforeend', habitItemHtml(newHabit));
    const newInput = list.querySelector('.habit-editor-item:last-child input');
    if (newInput) newInput.focus();
  });

  // Event: remove habit
  content.querySelector('#editor-list').addEventListener('click', (e) => {
    const btn = e.target.closest('.remove-btn');
    if (!btn) return;
    const item = btn.closest('.habit-editor-item');
    if (item) item.remove();
  });

  // Event: cancel
  content.querySelector('#editor-cancel').addEventListener('click', () => {
    closeEditor();
  });

  // Event: backdrop click
  modal.querySelector('.modal-backdrop').addEventListener('click', () => {
    closeEditor();
  });

  // Event: save
  content.querySelector('#editor-save').addEventListener('click', () => {
    const items = content.querySelectorAll('.habit-editor-item');
    const habits = [];
    let order = 0;

    items.forEach(item => {
      const name = item.querySelector('input').value.trim();
      if (name === '') return; // skip empty
      const id = item.dataset.habitId;
      habits.push({ id, name, order: order++ });
    });

    // Check for duplicates
    const names = habits.map(h => h.name.toLowerCase());
    const dupes = names.filter((n, i) => names.indexOf(n) !== i);
    if (dupes.length > 0) {
      alert(`Duplicate habit name: "${dupes[0]}". Each habit must have a unique name.`);
      return;
    }

    updateHabits(monthKey, habits);
    closeEditor();
    if (currentOnSave) currentOnSave();
  });

  // Drag-to-reorder
  setupDragReorder(content.querySelector('#editor-list'));
}

function closeEditor() {
  const modal = document.getElementById('habit-editor-modal');
  modal.classList.add('hidden');
}

function habitItemHtml(habit) {
  return `
    <li class="habit-editor-item" data-habit-id="${habit.id}">
      <span class="drag-handle">&#9776;</span>
      <input type="text" value="${escapeAttr(habit.name)}" maxlength="30" placeholder="Habit name">
      <button class="remove-btn" aria-label="Remove">&times;</button>
    </li>
  `;
}

function escapeAttr(str) {
  return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ===== Lightweight drag-to-reorder =====

function setupDragReorder(list) {
  let dragItem = null;
  let startY = 0;
  let currentY = 0;

  list.addEventListener('touchstart', (e) => {
    const handle = e.target.closest('.drag-handle');
    if (!handle) return;
    dragItem = handle.closest('.habit-editor-item');
    if (!dragItem) return;
    startY = e.touches[0].clientY;
    currentY = startY;
    dragItem.style.opacity = '0.6';
    dragItem.style.transition = 'none';
  }, { passive: true });

  list.addEventListener('touchmove', (e) => {
    if (!dragItem) return;
    currentY = e.touches[0].clientY;
    const dy = currentY - startY;
    dragItem.style.transform = `translateY(${dy}px)`;

    // Find sibling to swap with
    const items = Array.from(list.querySelectorAll('.habit-editor-item'));
    const dragIndex = items.indexOf(dragItem);
    const itemHeight = dragItem.offsetHeight;

    if (dy > itemHeight / 2 && dragIndex < items.length - 1) {
      list.insertBefore(items[dragIndex + 1], dragItem);
      startY += itemHeight;
    } else if (dy < -itemHeight / 2 && dragIndex > 0) {
      list.insertBefore(dragItem, items[dragIndex - 1]);
      startY -= itemHeight;
    }
  }, { passive: true });

  const endDrag = () => {
    if (!dragItem) return;
    dragItem.style.opacity = '';
    dragItem.style.transform = '';
    dragItem.style.transition = '';
    dragItem = null;
  };

  list.addEventListener('touchend', endDrag);
  list.addEventListener('touchcancel', endDrag);
}
