function setf(id, val) {
  const e = document.getElementById(id);
  if (e) e.value = (val == null ? '' : val);
}

function getf(id) {
  const e = document.getElementById(id);
  return e ? e.value.trim() : '';
}

function toFloat(v) { const n = parseFloat(v); return isNaN(n) ? null : n; }
function toInt(v)   { const n = parseInt(v);   return isNaN(n) ? null : n; }

function esc(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escAttr(s) { return String(s).replace(/'/g, "\\'"); }

function setBtn(btn, icon, label, dis) {
  btn.disabled = dis;
  btn.innerHTML = icon + ' ' + label;
}

function svgSave() {
  return '<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"/></svg>';
}

function svgGen() {
  return '<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>';
}
