// ── Section switching ─────────────────────────────────────────────────────
let _currentAdminSection = 'hero';

function getCurrentAdminSection() {
  return _currentAdminSection;
}

function switchSection(s) {
  if (!ACTIVE_ADMIN_SECTIONS.includes(s)) return;
  ACTIVE_ADMIN_SECTIONS.forEach(t => {
    const panel = document.getElementById(`panel-${t}`);
    if (panel) panel.classList.toggle('hidden', t !== s);
    const n = document.getElementById(`nav-${t}`);
    if (n) n.classList.toggle('active', t === s);
  });
  _currentAdminSection = s;
  if (s === 'footer' && currentData) {
    updateFooterPreview(currentData.business, collectSocialLinks());
  }
  // Notify preview drawer to scroll to this section
  if (typeof _pvOnSectionChange === 'function') _pvOnSectionChange(s);
}

// ── Toast notifications ───────────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const icons = {
    success: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
    error:   '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    info:    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
  };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span style="display:flex;flex-shrink:0">${icons[type]}</span><span>${esc(msg)}</span>`;
  document.getElementById('toastContainer').appendChild(el);
  setTimeout(() => {
    el.style.transition = 'opacity .3s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 320);
  }, 3200);
}

// ── Autosave indicator ────────────────────────────────────────────────────
let _autosaveTimer = null, _savedAt = null;

function showAutosaveIndicator() {
  _savedAt = Date.now();
  const el  = document.getElementById('autosaveIndicator');
  const lbl = document.getElementById('autosaveLabel');
  if (!el) return;
  el.classList.remove('hidden', 'as-error');
  el.classList.add('as-ok');
  lbl.textContent = 'Saved just now';
  clearInterval(_autosaveTimer);
  _autosaveTimer = setInterval(() => {
    if (!_savedAt) return;
    const s = Math.round((Date.now() - _savedAt) / 1000);
    lbl.textContent = s < 5 ? 'Saved just now' : s < 60 ? `Saved ${s}s ago` : `Saved ${Math.floor(s / 60)}m ago`;
  }, 5000);
}

function showAutosaveError() {
  const el  = document.getElementById('autosaveIndicator');
  const lbl = document.getElementById('autosaveLabel');
  if (!el) return;
  el.classList.remove('hidden', 'as-ok');
  el.classList.add('as-error');
  lbl.textContent = 'Save failed';
}

// ── Dark / Light mode toggle ──────────────────────────────────────────────
function applyTheme(light) {
  const body  = document.body;
  const moon  = document.getElementById('iconMoon');
  const sun   = document.getElementById('iconSun');
  const track = document.getElementById('themeTrack');
  if (light) {
    body.classList.add('light');
    moon.style.display = 'none';
    sun.style.display  = '';
    track.classList.add('on');
  } else {
    body.classList.remove('light');
    moon.style.display = '';
    sun.style.display  = 'none';
    track.classList.remove('on');
  }
}

function toggleTheme() {
  const isLight = !document.body.classList.contains('light');
  applyTheme(isLight);
  localStorage.setItem('gmp_theme', isLight ? 'light' : 'dark');
}

// Restore saved theme preference immediately
(function () { applyTheme(localStorage.getItem('gmp_theme') === 'light'); })();
