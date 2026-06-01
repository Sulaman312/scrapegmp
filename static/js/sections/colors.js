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
  const notes = personalization.style_notes || {};
  const posts = personalization.google_posts || {};
  const websiteRead = personalization.openai_website_read || {};

  if (notes.user_editable_markdown) return notes.user_editable_markdown;

  const uniqueText = (values, limit = 12) => {
    const seen = new Set();
    return (Array.isArray(values) ? values : [])
      .map(value => String(value || '').trim())
      .filter(value => {
        const key = value.toLowerCase();
        if (!value || seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, limit);
  };
  const list = (values, emptyText = 'none found', limit = 12) => {
    const items = uniqueText(values, limit);
    return items.length ? items.map(value => `- ${value}`).join('\n') : `- ${emptyText}`;
  };
  const websiteSignals = uniqueText([
    ...(notes.website_headings || []),
    ...(notes.website_services || []),
    ...(notes.website_ctas || []),
    ...(notes.website_nav_labels || []),
  ], 30);
  const latestPosts = (Array.isArray(posts.latest) ? posts.latest : [])
    .slice(0, 4)
    .map(post => {
      const date = String(post?.date || 'Recent post').trim();
      const body = String(post?.body || '').replace(/\s+/g, ' ').trim();
      return body ? `${date}: ${body.slice(0, 320)}${body.length > 320 ? '...' : ''}` : date;
    });
  const documentExcerpt = String(notes.document_excerpt || '')
    .split(/\r?\n/)
    .filter(line => !/#[0-9a-f]{6}\b/i.test(line) && !/\b(colou?rs?|palette)\b/i.test(line))
    .join('\n')
    .trim();

  return [
    `# ${brand.business_name || 'Business'} Personalization`,
    ``,
    `## Brand Profile`,
    `- Name: ${brand.business_name || ''}`,
    `- Type: ${brand.business_type || ''}`,
    `- Website title: ${brand.website_title || ''}`,
    `- Website description: ${brand.meta_description || ''}`,
    ``,
    `## Content Sources`,
    `- Google Maps business profile: ${sources.google_maps ? 'available' : 'not available'}`,
    `- Google posts collected: ${sources.google_posts_count || posts.count || 0}`,
    `- Business website: ${sources.business_website || 'not provided'}`,
    `- Design document: ${sources.design_document || 'not provided'}`,
    ``,
    `## Writing Direction`,
    `${notes.writing_direction || 'Use the available business sources to write clear, specific website content.'}`,
    ``,
    `## Website Signals`,
    `${list(websiteSignals, 'none found', 30)}`,
    ``,
    `## Website Understanding`,
    `${websiteRead.summary || 'No additional website summary was found.'}`,
    `${list(websiteRead.company_descriptions, 'no company descriptions found', 8)}`,
    ``,
    `## Identified Services and Offers`,
    `${list([
      ...(websiteRead.services || []),
      ...(websiteRead.products || []),
      ...(websiteRead.offers || []),
    ], 'none found', 20)}`,
    ``,
    `## Tone and Style Signals`,
    `${list(websiteRead.tone_and_style, 'none found', 10)}`,
    ``,
    `## Contact and Location Signals`,
    `${list(websiteRead.contact_or_location_notes, 'none found', 12)}`,
    ``,
    `## Recent Google Posts`,
    `${list(latestPosts, 'none found', 4)}`,
    ``,
    `## Uploaded Design Notes`,
    `${documentExcerpt ? documentExcerpt.slice(0, 4000) : 'No design notes were provided.'}`,
  ].join('\n');
}

function escapePersonalizationHtml(value) {
  return String(value || '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  }[ch]));
}

function renderPersonalizationMarkdown(markdown) {
  const lines = String(markdown || '').split(/\r?\n/);
  const html = [];
  let listOpen = false;
  const closeList = () => {
    if (listOpen) html.push('</ul>');
    listOpen = false;
  };

  lines.forEach(raw => {
    const line = raw.trim();
    if (!line) {
      closeList();
      return;
    }
    if (line.startsWith('## ')) {
      closeList();
      html.push(`<h3>${escapePersonalizationHtml(line.slice(3))}</h3>`);
      return;
    }
    if (line.startsWith('# ')) {
      closeList();
      html.push(`<h2>${escapePersonalizationHtml(line.slice(2))}</h2>`);
      return;
    }
    if (line.startsWith('- ')) {
      if (!listOpen) {
        html.push('<ul>');
        listOpen = true;
      }
      html.push(`<li>${escapePersonalizationHtml(line.slice(2))}</li>`);
      return;
    }
    closeList();
    html.push(`<p>${escapePersonalizationHtml(line)}</p>`);
  });
  closeList();
  return html.join('');
}

function renderPersonalizationStats(personalization) {
  const sources = personalization?.sources || {};
  const posts = personalization?.google_posts || {};
  const items = [
    ['Google Maps', sources.google_maps ? 'Connected' : 'Not available'],
    ['Google posts', String(sources.google_posts_count || posts.count || 0)],
    ['Website', sources.business_website ? 'Included' : 'Not provided'],
    ['Design document', sources.design_document ? 'Included' : 'Not provided'],
  ];
  return items.map(([label, value]) => `
    <div class="personalization-stat">
      <span>${escapePersonalizationHtml(label)}</span>
      <strong>${escapePersonalizationHtml(value)}</strong>
    </div>
  `).join('');
}

function populatePersonalization(personalization, hasPersonalization) {
  const missing = document.getElementById('personalizationMissingCard');
  const summaryCard = document.getElementById('personalizationSummaryCard');
  const markdown = document.getElementById('personalizationMarkdown');
  const preview = document.getElementById('personalizationMarkdownPreview');
  const stats = document.getElementById('personalizationSourceStats');

  if (!hasPersonalization || !personalization || typeof personalization !== 'object') {
    if (missing) missing.classList.remove('hidden');
    if (summaryCard) summaryCard.classList.add('hidden');
    return;
  }

  if (missing) missing.classList.add('hidden');
  if (summaryCard) summaryCard.classList.remove('hidden');
  const value = personalizationToMarkdown(personalization);
  if (markdown) {
    markdown.value = value;
    markdown.classList.add('hidden');
  }
  if (preview) {
    preview.innerHTML = renderPersonalizationMarkdown(value);
    preview.classList.remove('hidden');
  }
  if (stats) stats.innerHTML = renderPersonalizationStats(personalization);
  const editBtn = document.getElementById('personalizationEditBtn');
  if (editBtn) editBtn.textContent = 'Edit Content Notes';
  document.getElementById('personalizationDirtyNote')?.classList.add('hidden');
}

function collectPersonalization() {
  const personalization = (currentData || {}).personalization || {};
  const markdown = document.getElementById('personalizationMarkdown');
  if (markdown && markdown.value.trim()) {
    personalization.style_notes = personalization.style_notes || {};
    personalization.style_notes.user_editable_markdown = markdown.value.trim();
  }
  return personalization;
}

function onPersonalizationMarkdownChange() {
  const markdown = document.getElementById('personalizationMarkdown');
  const preview = document.getElementById('personalizationMarkdownPreview');
  if (markdown && preview) preview.innerHTML = renderPersonalizationMarkdown(markdown.value);
  document.getElementById('personalizationDirtyNote')?.classList.remove('hidden');
}

function togglePersonalizationEdit() {
  const markdown = document.getElementById('personalizationMarkdown');
  const preview = document.getElementById('personalizationMarkdownPreview');
  const editBtn = document.getElementById('personalizationEditBtn');
  if (!markdown || !preview || !editBtn) return;
  const editing = markdown.classList.contains('hidden');
  markdown.classList.toggle('hidden', !editing);
  preview.classList.toggle('hidden', editing);
  editBtn.textContent = editing ? 'Preview Notes' : 'Edit Content Notes';
  if (editing) markdown.focus();
  if (!editing) {
    preview.innerHTML = renderPersonalizationMarkdown(markdown.value);
  }
}
