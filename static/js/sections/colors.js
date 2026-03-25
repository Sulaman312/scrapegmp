function setColorPair(key, hex) {
  const h = (hex || '').startsWith('#') ? hex : '#' + hex;
  const p = document.getElementById(`cp-${key}`);
  const t = document.getElementById(`ch-${key}`);
  if (p) p.value = h;
  if (t) t.value = h.toUpperCase();
}

function onColorChange() {
  ['color1', 'color2', 'color3', 'cta', 'hero_dark'].forEach(k => {
    const p = document.getElementById(`cp-${k}`);
    const t = document.getElementById(`ch-${k}`);
    if (p && t) t.value = p.value.toUpperCase();
  });
  updateColorPreviews();
  syncAllCtaControls();
}

function onHexInput(key) {
  let v = document.getElementById(`ch-${key}`).value.trim();
  if (!v.startsWith('#')) v = '#' + v;
  if (/^#[0-9a-fA-F]{6}$/.test(v)) {
    const p = document.getElementById(`cp-${key}`);
    if (p) p.value = v;
    updateColorPreviews();
  }
}

function getColorVal(key) {
  const v = (document.getElementById(`ch-${key}`)?.value || '').trim();
  return /^#[0-9a-fA-F]{6}$/i.test(v) ? v : null;
}

function updateColorPreviews() {
  const c1  = getColorVal('color1')   || DEF.color1;
  const c2  = getColorVal('color2')   || DEF.color2;
  const c3  = getColorVal('color3')   || DEF.color3;
  const cta = getColorVal('cta')      || c1;

  document.getElementById('gradientPreview').style.background =
    `linear-gradient(135deg,${c1} 0%,${c2} 50%,${c3} 100%)`;

  const btn = document.getElementById('ctaBtnPreview');
  btn.style.background  = `linear-gradient(135deg,${cta},${cta}dd)`;
  btn.style.boxShadow   = `0 4px 15px ${cta}55`;

  const banner = document.getElementById('ctaBannerPreview');
  if (banner) {
    banner.style.background = cta;
    banner.style.boxShadow  = `0 4px 15px ${cta}55`;
  }
}

function applyPreset(c1, c2, c3) {
  setColorPair('color1', c1);
  setColorPair('color2', c2);
  setColorPair('color3', c3);
  setColorPair('cta', c1);
  updateColorPreviews();
}

function resetCtaColor()  { setColorPair('cta', getColorVal('color1') || DEF.color1); updateColorPreviews(); }
function resetHeroColor() { setColorPair('hero_dark', DEF.hero_dark); updateColorPreviews(); }

// ── CTA color mirrors (Hero section + CTA banner section) ─────────────────
function syncAllCtaControls() {
  const p = document.getElementById('cp-cta');
  if (!p) return;
  const hex   = p.value;
  const hexUp = hex.toUpperCase();
  [['cp-cta-h', 'ch-cta-h'], ['cp-cta-c', 'ch-cta-c']].forEach(([pid, tid]) => {
    const ep = document.getElementById(pid);
    const et = document.getElementById(tid);
    if (ep) ep.value = hex;
    if (et) et.value = hexUp;
  });
}

function syncHeroCtaControls() { syncAllCtaControls(); }

function _applyCtaColor(hex, skipPickerId) {
  setColorPair('cta', hex);
  updateColorPreviews();
  const hexUp = hex.toUpperCase();
  [['cp-cta-h', 'ch-cta-h'], ['cp-cta-c', 'ch-cta-c']].forEach(([pid, tid]) => {
    if (pid !== skipPickerId) { const e = document.getElementById(pid); if (e) e.value = hex; }
    if (tid !== skipPickerId) { const e = document.getElementById(tid); if (e) e.value = hexUp; }
  });
}

function onHeroCtaColorPick(hex) { _applyCtaColor(hex, 'cp-cta-h'); }
function onHeroCtaHexInput(v) {
  if (!v.startsWith('#')) v = '#' + v;
  if (/^#[0-9a-fA-F]{6}$/.test(v)) _applyCtaColor(v, 'ch-cta-h');
}
function onCtaBannerColorPick(hex) { _applyCtaColor(hex, 'cp-cta-c'); }
function onCtaBannerHexInput(v) {
  if (!v.startsWith('#')) v = '#' + v;
  if (/^#[0-9a-fA-F]{6}$/.test(v)) _applyCtaColor(v, 'ch-cta-c');
}

function buildPresets() {
  const grid = document.getElementById('presetsGrid');
  PRESETS.forEach(p => {
    const btn = document.createElement('button');
    btn.style.cssText = 'background:#1e293b;border:1px solid #334155;border-radius:.5rem;padding:.375rem;cursor:pointer;transition:border-color .15s;';
    btn.innerHTML = `<div style="height:22px;border-radius:.25rem;background:linear-gradient(to right,${p.c[0]},${p.c[1]},${p.c[2]})"></div>
      <span style="display:block;text-align:center;font-size:.7rem;color:#64748b;margin-top:.25rem">${p.name}</span>`;
    btn.addEventListener('mouseenter', () => btn.style.borderColor = '#16a34a');
    btn.addEventListener('mouseleave', () => btn.style.borderColor = '#334155');
    btn.onclick = () => applyPreset(...p.c);
    grid.appendChild(btn);
  });
}
