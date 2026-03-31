// ── Section definitions ────────────────────────────────────────────────────
const VIS_SECTIONS = [
  {
    key:      'features',
    label:    'Features',
    desc:     'Feature cards and attributes bento grid',
    svg:      '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    navLabel: 'Features',
  },
  {
    key:      'values',
    label:    'Values',
    desc:     'Floating value cards around center image',
    svg:      '<path d="M12 2l2.6 5.27L20.5 8l-4.25 4.14L17.2 18 12 15.27 6.8 18l.95-5.86L3.5 8l5.9-.73L12 2z"/>',
    navLabel: 'Values',
  },
  {
    key:      'gallery',
    label:    'Photo Gallery',
    desc:     'Image gallery with hover zoom effects',
    svg:      '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>',
    navLabel: 'Gallery',
  },
  {
    key:         'videos',
    label:       'Videos',
    desc:        'Embedded video player section',
    svg:         '<polygon points="5 3 19 12 5 21 5 3"/>',
    navLabel:    'Videos',
    noDataHint:  'Upload videos in the Videos panel to enable this section.',
  },
  {
    key:      'about',
    label:    'About & Highlights',
    desc:     'About paragraph with bullet point highlights',
    svg:      '<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    navLabel: null,
  },
  {
    key:      'reviews',
    label:    'Client Reviews',
    desc:     'Customer testimonials grid with star ratings',
    svg:      '<path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>',
    navLabel: 'Reviews',
  },
  {
    key:      'popular_times',
    label:    'Popular Times',
    desc:     'Busy hours bar chart per day of the week',
    svg:      '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
    navLabel: 'Availability',
  },
  {
    key:      'contact',
    label:    'Contact & Map',
    desc:     'Contact details, opening hours and Google Map',
    svg:      '<path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.95 11.5a19.79 19.79 0 01-3.07-8.67A2 2 0 012.85 1h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L7.09 8.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/>',
    navLabel: 'Contact',
  },
  {
    key:      'cta',
    label:    'Call to Action Banner',
    desc:     'Full-width gradient CTA section with button',
    svg:      '<path d="M13 10V3L4 14h7v7l9-11h-7z"/>',
    navLabel: null,
  },
  {
    key:      'keywords',
    label:    'Keywords Marquee',
    desc:     'Auto-scrolling review keyword tags strip',
    svg:      '<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="15" y2="18"/>',
    navLabel: null,
  },
];

function _getVisibleTemplateSections() {
  return VIS_SECTIONS.filter(s => typeof isTemplateSectionEnabled === 'function' ? isTemplateSectionEnabled(s.key) : true);
}

function _syncSidebarWithVisibility() {
  if (!currentData) return;
  const vis = currentData.section_visibility || {};
  _getVisibleTemplateSections().forEach((section) => {
    const nav = document.getElementById(`nav-${section.key}`);
    if (!nav) return;
    const hasData = _hasContent(section.key, currentData);
    const showInSidebar = vis[section.key] !== false && hasData;
    nav.style.display = showInSidebar ? '' : 'none';
  });
}

// ── Content availability check — mirrors generate_site.py's conditions ────
function _hasContent(key, data) {
  const ai  = data.ai       || {};
  const biz = data.business || {};
  switch (key) {
    case 'features':
      return !!(
        (ai.features   && ai.features.length   > 0) ||
        (data.about_attrs && data.about_attrs.length > 0)
      );
    case 'values':
      return !!(
        (ai.values && ai.values.length > 0) ||
        (ai.features && ai.features.length > 0)
      );
    case 'gallery':
      return !!(data.images && data.images.length > 0);
    case 'videos':
      // _has_videos is injected by admin.py (filesystem scan)
      return !!data._has_videos;
    case 'about':
      return !!(
        (ai.about_paragraph && ai.about_paragraph.length > 60) ||
        (ai.hero_subtitle   && ai.hero_subtitle.length   > 40)
      );
    case 'reviews':
      return !!(data.reviews && data.reviews.some(r => (r.text || '').trim()));
    case 'popular_times':
      return !!(data.popular_times && Object.keys(data.popular_times).length > 0);
    case 'contact':
      return true; // always renders (address / phone always present)
    case 'cta':
      return !!(biz.website || ai.cta_link || ai.cta_primary);
    case 'keywords':
      return !!(data.review_keywords && data.review_keywords.filter(k => k.length > 2).length > 0);
    default:
      return true;
  }
}

// ── Build a single section row ─────────────────────────────────────────────
function _visBuildRow(s, shown, hasContent) {
  const svgIcon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none"
       stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${s.svg}</svg>`;

  // ── No-data state: disabled row ──────────────────────────────────────────
  if (!hasContent) {
    const noDataNote = s.noDataHint || 'No data — this section won\'t appear on the site';
    return `
<div class="vis-sec-row vis-hidden-row vis-no-content-row" id="vis-row-${s.key}">
  <div class="flex items-center gap-3 min-w-0">
    <div class="vis-icon-wrap vis-icon-off" id="vis-icon-${s.key}">${svgIcon}</div>
    <div class="min-w-0">
      <div class="vis-name vis-off" id="vis-label-${s.key}">${s.label}</div>
      <div class="vis-desc">${s.desc}</div>
      <div class="vis-no-data-note">${noDataNote}</div>
    </div>
  </div>
  <div class="flex items-center gap-3 shrink-0 ml-3">
    <span class="vis-badge no-content" id="vis-status-${s.key}">No Data</span>
    <div class="vis-toggle vis-toggle-disabled" id="vis-btn-${s.key}" title="No content available for this section">
      <div class="vis-thumb"></div>
    </div>
  </div>
</div>`;
  }

  // ── Normal visible / hidden state ────────────────────────────────────────
  const rowCls   = shown ? 'vis-sec-row'              : 'vis-sec-row vis-hidden-row';
  const iconCls  = shown ? 'vis-icon-wrap vis-icon-on' : 'vis-icon-wrap vis-icon-off';
  const nameCls  = shown ? 'vis-name'                  : 'vis-name vis-off';
  const badgeCls = shown ? 'vis-badge on'              : 'vis-badge off';
  const badgeTxt = shown ? 'Visible'                   : 'Hidden';
  const togOn    = shown ? 'vis-on'                    : '';
  const title    = shown ? 'Click to hide this section': 'Click to show this section';

  return `
<div class="${rowCls}" id="vis-row-${s.key}">
  <div class="flex items-center gap-3 min-w-0">
    <div class="${iconCls}" id="vis-icon-${s.key}">${svgIcon}</div>
    <div class="min-w-0">
      <div class="${nameCls}" id="vis-label-${s.key}">${s.label}</div>
      <div class="vis-desc">${s.desc}</div>
    </div>
  </div>
  <div class="flex items-center gap-3 shrink-0 ml-3">
    <span class="${badgeCls}" id="vis-status-${s.key}">${badgeTxt}</span>
    <div class="vis-toggle ${togOn}" id="vis-btn-${s.key}"
         onclick="toggleSection('${s.key}')" title="${title}">
      <div class="vis-thumb"></div>
    </div>
  </div>
</div>`;
}

// ── Render all section toggle rows ─────────────────────────────────────────
function renderVisibilityToggles() {
  const container = document.getElementById('sectionToggles');
  if (!container || !currentData) return;

  const vis = currentData.section_visibility || {};
  container.innerHTML = _getVisibleTemplateSections().map(s => {
    const has = _hasContent(s.key, currentData);
    return _visBuildRow(s, vis[s.key] !== false, has);
  }).join('');

  _syncVisibilityPreview();
  _syncSidebarWithVisibility();
}

// ── Toggle a single section ────────────────────────────────────────────────
function toggleSection(key) {
  if (!currentData) return;
  // Guard: do nothing if section has no content
  if (!_hasContent(key, currentData)) return;

  if (!currentData.section_visibility) currentData.section_visibility = {};

  // flip: undefined/true → false, false → true
  const newVal = currentData.section_visibility[key] === false;
  currentData.section_visibility[key] = newVal;

  const shown = newVal;

  // Row dim
  const row = document.getElementById(`vis-row-${key}`);
  if (row) row.className = shown ? 'vis-sec-row' : 'vis-sec-row vis-hidden-row';

  // Icon wrapper
  const icon = document.getElementById(`vis-icon-${key}`);
  if (icon) icon.className = shown ? 'vis-icon-wrap vis-icon-on' : 'vis-icon-wrap vis-icon-off';

  // Label
  const lbl = document.getElementById(`vis-label-${key}`);
  if (lbl) lbl.className = shown ? 'vis-name' : 'vis-name vis-off';

  // Badge
  const sts = document.getElementById(`vis-status-${key}`);
  if (sts) {
    sts.textContent = shown ? 'Visible' : 'Hidden';
    sts.className   = shown ? 'vis-badge on' : 'vis-badge off';
  }

  // Toggle button
  const btn = document.getElementById(`vis-btn-${key}`);
  if (btn) btn.classList.toggle('vis-on', shown);

  // Rebuild nav links in preview (exclude no-data sections)
  _syncVisibilityPreview();
  _syncSidebarWithVisibility();

  _scheduleVisSave();
  if (typeof scheduleLivePreviewUpdate === 'function') scheduleLivePreviewUpdate();
}

// ── Social icon SVGs (matches generate_site.py) ───────────────────────────
function _socialSVG(platform) {
  const p = (platform || '').toLowerCase();
  if (p.includes('facebook'))  return '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z"/></svg>';
  if (p.includes('instagram')) return '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5"/><path d="M16 11.37A4 4 0 1112.63 8 4 4 0 0116 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>';
  if (p.includes('linkedin'))  return '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-2-2 2 2 0 00-2 2v7h-4v-7a6 6 0 016-6zM2 9h4v12H2z"/><circle cx="4" cy="4" r="2"/></svg>';
  if (p.includes('youtube'))   return '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M22.54 6.42a2.78 2.78 0 00-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46a2.78 2.78 0 00-1.95 1.96A29 29 0 001 12a29 29 0 00.46 5.33A2.78 2.78 0 003.41 19.1C5.12 19.56 12 19.56 12 19.56s6.88 0 8.59-.46a2.78 2.78 0 001.95-1.95A29 29 0 0023 12a29 29 0 00-.46-5.58z"/><polygon points="9.75 15.02 15.5 12 9.75 8.98" fill="#fff"/></svg>';
  if (p.includes('twitter') || p.includes(' x')) return '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.737l7.73-8.835L1.254 2.25H8.08l4.261 5.632zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>';
  if (p.includes('tiktok'))    return '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.34 6.34 0 106.34 6.34V8.75a8.12 8.12 0 004.77 1.52V6.82a4.85 4.85 0 01-1-.13z"/></svg>';
  if (p.includes('whatsapp'))  return '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>';
  if (p === '__maps__') return '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>';
  return '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>';
}

// ── Sync the website preview (nav links, names, footer data) ───────────────
function _syncVisibilityPreview() {
  if (!currentData) return;
  const biz     = currentData.business     || {};
  const ai      = currentData.ai           || {};
  const vis     = currentData.section_visibility || {};
  const socials = currentData.social_links || [];

  const name    = biz.name    || 'Business Name';
  const website = biz.website || '';
  const ctaLbl  = ai.cta_primary || ai.cta_btn_label || 'Get Started';

  // Nav logo + CTA
  const navName = document.getElementById('visNavName');
  if (navName) navName.textContent = name;
  const navCta = document.getElementById('visNavCta');
  if (navCta) navCta.textContent = ctaLbl + ' →';

  // Nav links — only sections that have content AND are not hidden
  const linksEl = document.getElementById('visNavLinks');
  if (linksEl) {
    linksEl.innerHTML = _getVisibleTemplateSections()
      .filter(s => s.navLabel && vis[s.key] !== false && _hasContent(s.key, currentData))
      .map(s => `<span class="vis-nav-link">${s.navLabel}</span>`)
      .join('');
  }

  // Footer logo
  const footName = document.getElementById('visFooterName');
  if (footName) footName.textContent = name;

  // Footer tagline
  const footTag = document.getElementById('visFooterTagline');
  if (footTag) {
    footTag.textContent = ai.footer_tagline || ai.about_paragraph || ai.hero_subtitle || 'Serving you with excellence';
  }

  // Footer social icons
  const footSoc = document.getElementById('visFooterSocial');
  if (footSoc) {
    const icons = [];
    (Array.isArray(socials) ? socials : []).slice(0, 4).forEach(lnk => {
      const platform = typeof lnk === 'string' ? '' : (lnk.platform || '');
      icons.push(`<div class="vis-footer-social-icon">${_socialSVG(platform)}</div>`);
    });
    if (biz.google_maps_url) {
      icons.push(`<div class="vis-footer-social-icon">${_socialSVG('__maps__')}</div>`);
    }
    if (!icons.length) {
      for (let i = 0; i < 3; i++) icons.push('<div class="vis-footer-social-icon" style="background:rgba(255,255,255,0.03)"></div>');
    }
    footSoc.innerHTML = icons.join('');
  }

  // Footer contact fields
  const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val || '—'; };
  setText('visFooterAddr',  biz.address);
  setText('visFooterPhone', biz.phone);
  setText('visFooterEmail', biz.email);
  setText('visFooterWeb',   website.replace(/^https?:\/\//, '') || null);

  // Footer bottom bar
  const fc = document.getElementById('visFooterCopy');
  if (fc) fc.textContent = `© ${new Date().getFullYear()} ${name}. All rights reserved.`;

  // Hide Google Maps link if no URL
  const fm = document.getElementById('visFooterMaps');
  if (fm) fm.style.display = biz.google_maps_url ? '' : 'none';
}

// ── Debounced save ─────────────────────────────────────────────────────────
let _visSaveTimer = null;
function _scheduleVisSave() {
  clearTimeout(_visSaveTimer);
  _visSaveTimer = setTimeout(() => saveChanges(), 700);
}
