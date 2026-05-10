import { supabase } from './supabase-client.js';
import { escapeHtml } from './util.js';

export function renderAuth(container, onLogin) {
  container.innerHTML = `
    <div class="auth-card">
      <h2>Legal Doc Catalog</h2>
      <p class="auth-subtitle">Sign in to access your documents</p>
      <form id="auth-form">
        <label for="auth-email">Email</label>
        <input type="email" id="auth-email" required autocomplete="email">
        <label for="auth-password">Password</label>
        <input type="password" id="auth-password" required minlength="6" autocomplete="current-password">
        <div id="auth-error" class="auth-error" hidden></div>
        <button type="submit" id="auth-submit">Sign In</button>
        <button type="button" id="auth-toggle" class="btn-link">Need an account? Sign up</button>
      </form>
    </div>
  `;

  let isSignUp = false;
  const form = container.querySelector('#auth-form');
  const submitBtn = container.querySelector('#auth-submit');
  const toggleBtn = container.querySelector('#auth-toggle');
  const errorEl = container.querySelector('#auth-error');

  toggleBtn.addEventListener('click', () => {
    isSignUp = !isSignUp;
    submitBtn.textContent = isSignUp ? 'Sign Up' : 'Sign In';
    toggleBtn.textContent = isSignUp
      ? 'Already have an account? Sign in'
      : 'Need an account? Sign up';
    errorEl.hidden = true;
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = form.querySelector('#auth-email').value.trim();
    const password = form.querySelector('#auth-password').value;

    submitBtn.disabled = true;
    submitBtn.textContent = isSignUp ? 'Signing up...' : 'Signing in...';
    errorEl.hidden = true;

    const { error } = isSignUp
      ? await supabase.auth.signUp({ email, password })
      : await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      errorEl.textContent = error.message;
      errorEl.hidden = false;
      submitBtn.disabled = false;
      submitBtn.textContent = isSignUp ? 'Sign Up' : 'Sign In';
      return;
    }

    if (isSignUp) {
      errorEl.textContent = 'Check your email to confirm your account.';
      errorEl.hidden = false;
      errorEl.classList.add('auth-info');
      submitBtn.disabled = false;
      submitBtn.textContent = 'Sign Up';
      return;
    }

    onLogin();
  });
}

export function renderHeaderUser(container, session) {
  const email = session.user.email;
  container.innerHTML = `
    <span class="user-badge">${escapeHtml(email)}</span>
    <button id="logout-btn" class="btn-small">Sign Out</button>
  `;
  container.querySelector('#logout-btn').addEventListener('click', async () => {
    await supabase.auth.signOut();
  });
}
