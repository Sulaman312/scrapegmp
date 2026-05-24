function setColorPair(key, hex) {
  const h = (hex || '').startsWith('#') ? hex : '#' + hex;
  const p = document.getElementById(`cp-${key}`);
  const t = document.getElementById(`ch-${key}`);
  if (p) p.value = h;
  if (t) t.value = h.toUpperCase();
}

function onColorChange() {
  ['color1', 'color2', 'color3'].forEach(k => {
    const p = document.getElementById(`cp-${k}`);
    const t = document.getElementById(`ch-${k}`);
    if (p && t) t.value = p.value.toUpperCase();
  });
  updateColorPreviews();
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

  const preview = document.getElementById('gradientPreview');
  if (preview) {
    preview.style.background = `linear-gradient(135deg,${c1} 0%,${c2} 50%,${c3} 100%)`;
  }
}

function applyPreset(c1, c2, c3) {
  setColorPair('color1', c1);
  setColorPair('color2', c2);
  setColorPair('color3', c3);
  updateColorPreviews();
}

function _currentTemplateIdForColors() {
  return (document.getElementById('template-select')?.value || (currentData || {}).template || 'default');
}

function getPersonalizationPaletteForTemplate(templateId) {
  const colors = (((currentData || {}).personalization || {}).colors || {});
  const templatePalettes = colors.template_palettes || {};
  return templatePalettes[templateId] || templatePalettes.default || null;
}

function getPresetSourceForTemplate(templateId) {
  const palette = getPersonalizationPaletteForTemplate(templateId);
  if (palette && Array.isArray(palette.presets) && palette.presets.length) {
    return palette.presets.map(p => ({ name: p.name || 'Preset', c: [p.color1, p.color2, p.color3] }));
  }
  if (Array.isArray(colorsToPresetArray((((currentData || {}).personalization || {}).colors || {}).suggested_color_presets))) {
    return colorsToPresetArray((((currentData || {}).personalization || {}).colors || {}).suggested_color_presets);
  }
  return PRESETS;
}

function getMainPaletteForTemplate(templateId) {
  const palette = getPersonalizationPaletteForTemplate(templateId);
  return palette?.main || null;
}

function applyMainPaletteForTemplate(templateId) {
  const main = getMainPaletteForTemplate(templateId);
  if (main?.color1 && main?.color2 && main?.color3) {
    applyPreset(main.color1, main.color2, main.color3);
    return true;
  }
  return false;
}

function colorsToPresetArray(presets) {
  if (!Array.isArray(presets) || !presets.length) return null;
  return presets.map(p => ({ name: p.name || 'Preset', c: [p.color1, p.color2, p.color3] }));
}

function buildPresets() {
  const grid = document.getElementById('presetsGrid');
  if (!grid) return;
  const sourcePresets = getPresetSourceForTemplate(_currentTemplateIdForColors()) || PRESETS;
  grid.innerHTML = '';
  sourcePresets.forEach(p => {
    if (!p.c || p.c.length < 3 || !p.c[0] || !p.c[1] || !p.c[2]) return;
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

// ── Logo-based Coloring Functions ─────────────────────────────────────────
function loadLogoColors(logoColors) {
  const logoColorsCard = document.getElementById('logoColorsCard');
  const dominantSection = document.getElementById('logoDominantColor');
  const paletteSection = document.getElementById('logoPalette');

  if (!logoColors || (!logoColors.dominant_color && !logoColors.palette?.length)) {
    logoColorsCard.style.display = 'none';
    return;
  }

  logoColorsCard.style.display = 'block';

  // Display dominant color
  if (logoColors.dominant_color) {
    dominantSection.classList.remove('hidden');
    const preview = document.getElementById('dominantColorPreview');
    const hexInput = document.getElementById('dominantColorHex');
    preview.style.backgroundColor = logoColors.dominant_color;
    hexInput.value = logoColors.dominant_color.toUpperCase();
  }

  // Display color palette
  if (logoColors.palette && logoColors.palette.length > 0) {
    paletteSection.classList.remove('hidden');
    const paletteContainer = document.getElementById('paletteColors');
    paletteContainer.innerHTML = '';

    logoColors.palette.forEach((color, index) => {
      const colorItem = document.createElement('div');
      colorItem.className = 'cursor-pointer';
      colorItem.innerHTML = `
        <div style="width:60px;height:60px;border-radius:8px;background:${color};border:1px solid #475569;transition:transform 0.2s;cursor:pointer;"
             onmouseover="this.style.transform='scale(1.1)'"
             onmouseout="this.style.transform='scale(1)'"
             onclick="applyPaletteColor('${color}', ${index})"
             title="Click to apply to Color ${(index % 3) + 1}">
        </div>
        <div style="text-align:center;font-size:0.7rem;color:#94a3b8;margin-top:0.25rem;">${color.toUpperCase()}</div>
      `;
      paletteContainer.appendChild(colorItem);
    });
  }
}

function applyDominantColor() {
  const hexInput = document.getElementById('dominantColorHex');
  if (hexInput && hexInput.value) {
    setColorPair('color1', hexInput.value);
    updateColorPreviews();
  }
}

function applyPaletteColor(color, index) {
  const targetKey = `color${(index % 3) + 1}`;
  setColorPair(targetKey, color);
  updateColorPreviews();
}

function personalizationToMarkdown(personalization) {
  if (!personalization || typeof personalization !== 'object') return '';
  const sources = personalization.sources || {};
  const brand = personalization.brand || {};
  const colors = personalization.colors || {};
  const selected = colors.selected_theme || {};
  const templatePalettes = colors.template_palettes || {};
  const notes = personalization.style_notes || {};
  const posts = personalization.google_posts || {};

  return [
    `# Personalization`,
    ``,
    `## Sources`,
    `- Google Maps: ${sources.google_maps ? 'yes' : 'no'}`,
    `- Google posts scraped: ${sources.google_posts_count || posts.count || 0}`,
    `- Website: ${sources.business_website || 'not provided'}`,
    `- Design document: ${sources.design_document || 'not provided'}`,
    `- Color source: ${sources.color_source || 'unknown'}`,
    ``,
    `## Brand`,
    `- Name: ${brand.business_name || ''}`,
    `- Type: ${brand.business_type || ''}`,
    `- Website title: ${brand.website_title || ''}`,
    ``,
    `## Selected Theme`,
    `- Color 1: ${selected.color1 || ''}`,
    `- Color 2: ${selected.color2 || ''}`,
    `- Color 3: ${selected.color3 || ''}`,
    ``,
    `## Template Palettes`,
    `${Object.entries(templatePalettes).map(([name, palette]) => `- ${name}: ${palette?.main?.color1 || ''}, ${palette?.main?.color2 || ''}, ${palette?.main?.color3 || ''} + ${(palette?.presets || []).length} presets`).join('\n') || '- none'}`,
    ``,
    `## Website Signals`,
    `${(notes.website_headings || []).slice(0, 8).map(h => `- ${h}`).join('\n') || '- none'}`,
    ``,
    `## Writing Direction`,
    `${notes.writing_direction || ''}`,
  ].join('\n');
}

function populatePersonalization(personalization, hasPersonalization) {
  const missing = document.getElementById('personalizationMissingCard');
  const summaryCard = document.getElementById('personalizationSummaryCard');
  const jsonCard = document.getElementById('personalizationJsonCard');
  const markdown = document.getElementById('personalizationMarkdown');
  const jsonEl = document.getElementById('personalizationJson');

  if (!hasPersonalization || !personalization || typeof personalization !== 'object') {
    if (missing) missing.classList.remove('hidden');
    if (summaryCard) summaryCard.classList.add('hidden');
    if (jsonCard) jsonCard.classList.add('hidden');
    return;
  }

  if (missing) missing.classList.add('hidden');
  if (summaryCard) summaryCard.classList.remove('hidden');
  if (jsonCard) jsonCard.classList.remove('hidden');
  if (markdown) markdown.value = personalizationToMarkdown(personalization);
  if (jsonEl) jsonEl.value = JSON.stringify(personalization, null, 2);
  document.getElementById('personalizationDirtyNote')?.classList.add('hidden');
}

function collectPersonalization() {
  const jsonEl = document.getElementById('personalizationJson');
  if (!jsonEl || !jsonEl.value.trim()) return (currentData || {}).personalization || {};
  try {
    return JSON.parse(jsonEl.value);
  } catch {
    return (currentData || {}).personalization || {};
  }
}

function onPersonalizationJsonChange() {
  document.getElementById('personalizationDirtyNote')?.classList.remove('hidden');
}

function formatPersonalizationJson() {
  const jsonEl = document.getElementById('personalizationJson');
  if (!jsonEl) return;
  try {
    const parsed = JSON.parse(jsonEl.value || '{}');
    jsonEl.value = JSON.stringify(parsed, null, 2);
    const markdown = document.getElementById('personalizationMarkdown');
    if (markdown) markdown.value = personalizationToMarkdown(parsed);
  } catch (e) {
    showToast('Personalization JSON is invalid: ' + e.message, 'error');
  }
}
