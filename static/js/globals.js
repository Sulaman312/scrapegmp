// Shared state
let currentBusiness = null, currentData = null;
let reviewKeywords = [], allBusinesses = [], menuOpen = false;
let highlights = [];
let currentPage = 'home'; // Current page for multipage templates
let isMultipageTemplate = false; // Track if current template is multipage

const ADMIN_SECTIONS = ['hero', 'features', 'our-services', 'why-choose-us', 'values', 'gallery', 'videos', 'about', 'reviews', 'contact', 'cta', 'footer', 'services-page', 'media', 'design', 'seo', 'visibility'];
let ACTIVE_ADMIN_SECTIONS = ADMIN_SECTIONS.slice();
let TEMPLATE_DEFS = {};

const TEMPLATE_SECTION_TO_ADMIN = {
  hero: 'hero',
  features: 'features',
  our_services: 'our-services',
  why_choose_us: 'why-choose-us',
  values: 'values',
  gallery: 'gallery',
  videos: 'videos',
  about: 'about',
  reviews: 'reviews',
  contact: 'contact',
  cta: 'cta',
  footer: 'footer',
};

function setTemplateDefinitions(defs) {
  TEMPLATE_DEFS = defs || {};
}

function getSelectedTemplateId() {
  const selector = document.getElementById('template-select');
  return (selector && selector.value) ? selector.value : ((currentData && currentData.template) || 'default');
}

function getTemplateEnabledWebsiteSections(templateId) {
  const tid = templateId || getSelectedTemplateId();
  const templateDef = TEMPLATE_DEFS[tid] || {};
  const enabled = ((templateDef.sections || {}).enabled) || [];
  return Array.isArray(enabled) ? enabled.slice() : [];
}

function getActiveTemplateWebsiteSections() {
  return getTemplateEnabledWebsiteSections(getSelectedTemplateId());
}

function isTemplateSectionEnabled(sectionKey) {
  const enabled = getActiveTemplateWebsiteSections();
  if (!enabled.length) return true;
  return enabled.includes(sectionKey);
}

function applyTemplateSections(templateId) {
  const tid = templateId || getSelectedTemplateId();
  const enabledSet = new Set(getTemplateEnabledWebsiteSections(tid));
  const hasExplicitTemplateSections = enabledSet.size > 0;
  const alwaysVisible = new Set(['hero', 'footer', 'visibility', 'design', 'seo']);

  const panelToTemplateSection = {
    features: 'features',
    'our-services': 'features',
    'why-choose-us': 'features',
    values: 'values',
    gallery: 'gallery',
    videos: 'videos',
    about: 'about',
    reviews: 'reviews',
    contact: 'contact',
    cta: 'cta',
    'services-page': 'features',
  };

  ACTIVE_ADMIN_SECTIONS = [];

  ADMIN_SECTIONS.forEach((sectionKey) => {
    const navEl = document.getElementById(`nav-${sectionKey}`);
    const panelEl = document.getElementById(`panel-${sectionKey}`);
    const tplSection = panelToTemplateSection[sectionKey];
    const enabledByTemplate = alwaysVisible.has(sectionKey)
      || !hasExplicitTemplateSections
      || !tplSection
      || enabledSet.has(tplSection);

    if (navEl) navEl.style.display = enabledByTemplate ? '' : 'none';
    if (panelEl && !enabledByTemplate) panelEl.classList.add('hidden');

    if (enabledByTemplate) ACTIVE_ADMIN_SECTIONS.push(sectionKey);
  });

  if (typeof toggleCompanyImageSelectors === 'function') {
    toggleCompanyImageSelectors(tid);
  }

  if (typeof collectFeatures === 'function' && typeof renderFeatures === 'function') {
    renderFeatures(collectFeatures());
  }

  // Update color presets for template
  updatePresetsForTemplate(tid);

  const currentSection = (typeof getCurrentAdminSection === 'function') ? getCurrentAdminSection() : 'hero';
  if (!ACTIVE_ADMIN_SECTIONS.includes(currentSection) && ACTIVE_ADMIN_SECTIONS.length && typeof switchSection === 'function') {
    switchSection(ACTIVE_ADMIN_SECTIONS[0]);
  }
}
const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
const DAY_LBL = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

const DEF = { color1: '#4f7df5', color2: '#7c3aed', color3: '#06c9d4', hero_dark: '#06060f' };

const PRESETS_DEFAULT = [
  { name: 'Ocean Blue', c: ['#4f7df5', '#7c3aed', '#06c9d4'] },
  { name: 'Emerald',    c: ['#10b981', '#059669', '#0d9488'] },
  { name: 'Sunset',     c: ['#f59e0b', '#ef4444', '#ec4899'] },
  { name: 'Purple',     c: ['#16a34a', '#8b5cf6', '#a855f7'] },
  { name: 'Fire',       c: ['#f97316', '#ef4444', '#dc2626'] },
  { name: 'Sky',        c: ['#0ea5e9', '#38bdf8', '#7dd3fc'] },
];

const PRESETS_BERNARD = [
  { name: 'Blue Professional', c: ['#1E3A8A', '#DBEAFE', '#F59E0B'] },
  { name: 'Blue Clean', c: ['#0284C7', '#E0F2FE', '#F97316'] },
  { name: 'Navy Orange', c: ['#1E40AF', '#DBEAFE', '#FB923C'] },
  { name: 'Red Professional', c: ['#991B1B', '#FEE2E2', '#F59E0B'] },
  { name: 'Crimson', c: ['#9F1239', '#FCE7F3', '#F97316'] },
  { name: 'Red Orange', c: ['#B91C1C', '#FEE2E2', '#FB923C'] },
];

const PRESETS_FACADE = [
  { name: 'Ocean Blue', c: ['#4f7df5', '#7c3aed', '#06c9d4'] },
  { name: 'Emerald',    c: ['#10b981', '#059669', '#0d9488'] },
  { name: 'Sunset',     c: ['#f59e0b', '#ef4444', '#ec4899'] },
  { name: 'Purple',     c: ['#16a34a', '#8b5cf6', '#a855f7'] },
  { name: 'Fire',       c: ['#f97316', '#ef4444', '#dc2626'] },
  { name: 'Sky',        c: ['#0ea5e9', '#38bdf8', '#7dd3fc'] },
];

let PRESETS = PRESETS_DEFAULT;

function updatePresetsForTemplate(templateId) {
  if (templateId === 'bernard') {
    PRESETS = PRESETS_BERNARD;
  } else if (templateId === 'facade') {
    PRESETS = PRESETS_FACADE;
  } else {
    PRESETS = PRESETS_DEFAULT;
  }
  if (typeof buildPresets === 'function') {
    const grid = document.getElementById('presetsGrid');
    if (grid) {
      grid.innerHTML = '';
      buildPresets();
    }
  }
}

const SOCIAL_PLATFORMS = [
  {
    id: 'facebook', name: 'Facebook', color: '#1877F2',
    svg: '<svg viewBox="0 0 24 24"><path d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z"/></svg>'
  },
  {
    id: 'instagram', name: 'Instagram', color: '#E1306C',
    svg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5"/><path d="M16 11.37A4 4 0 1112.63 8 4 4 0 0116 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>'
  },
  {
    id: 'linkedin', name: 'LinkedIn', color: '#0A66C2',
    svg: '<svg viewBox="0 0 24 24"><path d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-2-2 2 2 0 00-2 2v7h-4v-7a6 6 0 016-6zM2 9h4v12H2z"/><circle cx="4" cy="4" r="2"/></svg>'
  },
  {
    id: 'youtube', name: 'YouTube', color: '#FF0000',
    svg: '<svg viewBox="0 0 24 24"><path d="M22.54 6.42a2.78 2.78 0 00-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46a2.78 2.78 0 00-1.95 1.96A29 29 0 001 12a29 29 0 00.46 5.33A2.78 2.78 0 003.41 19.1C5.12 19.56 12 19.56 12 19.56s6.88 0 8.59-.46a2.78 2.78 0 001.95-1.95A29 29 0 0023 12a29 29 0 00-.46-5.58z"/><polygon points="9.75 15.02 15.5 12 9.75 8.98 9.75 15.02" fill="#fff"/></svg>'
  },
  {
    id: 'twitter', name: 'Twitter / X', color: '#000',
    svg: '<svg viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.737l7.73-8.835L1.254 2.25H8.08l4.261 5.632zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'
  },
  {
    id: 'tiktok', name: 'TikTok', color: '#010101',
    svg: '<svg viewBox="0 0 24 24"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.34 6.34 0 106.34 6.34V8.75a8.12 8.12 0 004.77 1.52V6.82a4.85 4.85 0 01-1-.13z"/></svg>'
  },
  {
    id: 'whatsapp', name: 'WhatsApp', color: '#25D366',
    svg: '<svg viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>'
  },
  {
    id: 'pinterest', name: 'Pinterest', color: '#E60023',
    svg: '<svg viewBox="0 0 24 24"><path d="M12 0a12 12 0 00-4.373 23.178c-.03-.528-.005-1.163.13-1.738l.97-4.11s-.248-.494-.248-1.228c0-1.15.668-2.01 1.5-2.01.707 0 1.05.53 1.05.167 0 .71-.453 1.775-.687 2.763-.195.824.413 1.495 1.224 1.495 1.467 0 2.597-1.547 2.597-3.78 0-1.975-1.42-3.354-3.448-3.354-2.348 0-3.725 1.76-3.725 3.579 0 .708.272 1.466.613 1.88a.246.246 0 01.057.233c-.062.26-.2.824-.228.939-.037.15-.122.182-.28.11-1.048-.488-1.703-2.023-1.703-3.257 0-2.647 1.923-5.082 5.547-5.082 2.912 0 5.177 2.073 5.177 4.844 0 2.89-1.822 5.213-4.348 5.213-.85 0-1.649-.442-1.923-.962l-.522 1.948c-.19.727-.698 1.636-1.04 2.19.785.243 1.615.374 2.476.374a12 12 0 000-24z"/></svg>'
  },
];

// ═══════════════════════════════════════════════════════════════════════════
// MULTIPAGE SUPPORT
// ═══════════════════════════════════════════════════════════════════════════

// Templates that support multipage
const MULTIPAGE_TEMPLATES = ['bernard'];

function isTemplateMultipage(templateId) {
  return MULTIPAGE_TEMPLATES.includes(templateId);
}

function updatePageSelector() {
  const templateId = getSelectedTemplateId();
  const pageSelector = document.getElementById('page-select');

  if (!pageSelector) return;

  isMultipageTemplate = isTemplateMultipage(templateId);

  if (isMultipageTemplate) {
    pageSelector.style.display = '';
    // Set current page if stored in data
    if (currentData && currentData.current_page) {
      currentPage = currentData.current_page;
      pageSelector.value = currentPage;
    }
  } else {
    pageSelector.style.display = 'none';
  }

  if (typeof toggleBernardFields === 'function') {
    toggleBernardFields(templateId);
  }

  // Show/hide multipage-specific nav items and panels
  updateMultipageUI();
}

function updateMultipageUI() {
  const templateId = getSelectedTemplateId();
  const isBernard = templateId === 'bernard';
  const isMulti = isMultipageTemplate;

  const websiteSections = ['hero', 'features', 'our-services', 'why-choose-us', 'values', 'gallery', 'videos', 'about', 'reviews', 'contact', 'cta', 'footer', 'services-page'];
  let allowedWebsiteSections = websiteSections.slice();

  if (isBernard && isMulti) {
    if (currentPage === 'services') {
      allowedWebsiteSections = ['services-page'];
    } else if (currentPage === 'contact') {
      allowedWebsiteSections = ['contact'];
    } else {
      allowedWebsiteSections = ['hero', 'features', 'our-services', 'why-choose-us', 'values', 'gallery', 'videos', 'about', 'reviews', 'contact', 'cta', 'footer'];
    }
  }

  // Respect template-enabled sections when available (except for the forced single-section pages above)
  const enabledTemplateSections = new Set(getTemplateEnabledWebsiteSections(templateId));
  const hasTemplateRules = enabledTemplateSections.size > 0;
  if (!(isBernard && isMulti && (currentPage === 'services' || currentPage === 'contact'))) {
    if (hasTemplateRules) {
      const mapping = {
        hero: 'hero', features: 'features', values: 'values', gallery: 'gallery', videos: 'videos',
        about: 'about', reviews: 'reviews', contact: 'contact', cta: 'cta', footer: 'footer',
        'our-services': 'features', 'why-choose-us': 'features',
        'services-page': 'features'
      };
      allowedWebsiteSections = allowedWebsiteSections.filter(s => enabledTemplateSections.has(mapping[s]) || s === 'hero' || s === 'footer');
    }
  }

  const visibleSet = new Set(allowedWebsiteSections);
  ADMIN_SECTIONS.forEach(sectionKey => {
    const nav = document.getElementById(`nav-${sectionKey}`);
    const panel = document.getElementById(`panel-${sectionKey}`);
    const isWebsite = websiteSections.includes(sectionKey);
    const shouldShow = !isWebsite || visibleSet.has(sectionKey);
    if (nav) nav.style.display = shouldShow ? '' : 'none';
    if (panel && !shouldShow) panel.classList.add('hidden');
  });

  ACTIVE_ADMIN_SECTIONS = ADMIN_SECTIONS.filter(sectionKey => {
    const nav = document.getElementById(`nav-${sectionKey}`);
    return !nav || nav.style.display !== 'none';
  });

  const preferred = (isBernard && isMulti && currentPage === 'services')
    ? 'services-page'
    : (isBernard && isMulti && currentPage === 'contact')
      ? 'contact'
      : (isBernard && isMulti && currentPage === 'home')
        ? 'our-services'
        : 'hero';

  if (typeof getCurrentAdminSection === 'function' && typeof switchSection === 'function') {
    const currentSection = getCurrentAdminSection();
    if (!ACTIVE_ADMIN_SECTIONS.includes(currentSection) || (ACTIVE_ADMIN_SECTIONS.includes(preferred) && currentSection !== preferred && (currentPage === 'services' || currentPage === 'contact'))) {
      switchSection(ACTIVE_ADMIN_SECTIONS.includes(preferred) ? preferred : (ACTIVE_ADMIN_SECTIONS[0] || 'hero'));
    }
  }
}

function changeCurrentPage() {
  const pageSelector = document.getElementById('page-select');
  if (!pageSelector) return;

  currentPage = pageSelector.value;

  // Store current page selection
  if (currentData) {
    currentData.current_page = currentPage;
  }

  // Update multipage UI to show/hide appropriate nav items
  updateMultipageUI();

  // Update preview to show the selected page
  if (typeof updateLivePreview === 'function') {
    updateLivePreview();
  }

  // Show toast notification
  const pageNames = {
    home: 'Home Page',
    services: 'Services Page',
    contact: 'Contact Page'
  };
  showToast(`Switched to ${pageNames[currentPage] || currentPage}`, 'info');
}
