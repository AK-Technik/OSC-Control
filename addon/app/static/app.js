/* ShowControl UI — app.js */

// ── Toast ──────────────────────────────────────────────────────────────────

let _toastTimer = null;

function showToast(message, type = 'ok') {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.className = `toast ${type}`;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => {
    el.classList.add('hidden');
  }, 3000);
}

// ── Fetch helpers ──────────────────────────────────────────────────────────

async function postJSON(url, data) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return r.json();
}

// ── Touch feedback ─────────────────────────────────────────────────────────

document.addEventListener('click', e => {
  const btn = e.target.closest('.btn, .type-tile, .profile-option');
  if (btn) {
    btn.style.transition = 'transform 0.08s';
    btn.style.transform = 'scale(0.96)';
    setTimeout(() => { btn.style.transform = ''; }, 120);
  }
});
