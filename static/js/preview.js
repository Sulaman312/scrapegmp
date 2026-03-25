// ── Live Preview Drawer ────────────────────────────────────────────────────

// Maps admin section keys → generated website anchor IDs
// (null means scroll to top / hero)
const PV_ANCHORS = {
  hero:          null,
  features:      'features',
  gallery:       'gallery',
  videos:        'videos',
  about:         null,
  reviews:       'testimonials',
  popular_times: 'hours',
  contact:       'contact',
  cta:           null,
  footer:        null,
  design:        null,
  seo:           null,
  visibility:    null,
};

const PV_LABELS = {
  hero:          'Hero',
  features:      'Features',
  gallery:       'Gallery',
  videos:        'Videos',
  about:         'About',
  reviews:       'Client Reviews',
  popular_times: 'Popular Times',
  contact:       'Contact',
  cta:           'CTA Banner',
  footer:        'Footer',
  design:        'Design',
  seo:           'SEO',
  visibility:    'Sections',
};

// Desktop render width — forces lg/xl breakpoints so hidden images appear
const PV_DESKTOP_W = 1280;
// Phone emulation width
const PV_PHONE_W   = 390;
const PV_PHONE_H   = 844;

let _pvOpen      = false;
let _pvSection   = 'hero';
let _pvDevice   = 'desktop';
let _pvLoaded   = false;   // true once iframe has been given a real src
let _pvTimer    = null;    // debounce timer for post-save reload
let _pvLiveTimer = null;   // debounce timer for live preview (content/color changes)
let _pvResObs   = null;    // ResizeObserver instance

const PV_LIVE_DEBOUNCE_MS = 380;

// ── Toggle drawer open / closed ────────────────────────────────────────────
function togglePreview() {
  _pvOpen = !_pvOpen;
  document.body.classList.toggle('preview-open', _pvOpen);

  const btn = document.getElementById('btnTogglePreview');
  if (btn) btn.classList.toggle('pv-active', _pvOpen);

  if (_pvOpen) {
    _pvInitResizeObserver();
    if (!currentBusiness) {
      _pvShowEmpty(true);
    } else if (!_pvLoaded) {
      _pvLoad();
    } else {
      // Drawer just opened — re-apply scale after the 280ms CSS transition finishes
      setTimeout(_pvApplyScale, 320);
    }
  }
}

// ── Load / reload the iframe ───────────────────────────────────────────────
function _pvLoad() {
  if (!currentBusiness) { _pvShowEmpty(true); return; }

  _pvShowEmpty(false);
  _pvShowLoading(true);

  const iframe = document.getElementById('pvIframe');
  if (!iframe) return;

  // Set src — iframe will start rendering at the CSS default (1280×900px desktop)
  // so all lg: breakpoints fire correctly from the very first paint.
  iframe.src = `/preview/${encodeURIComponent(currentBusiness)}/`;
  _pvLoaded = true;
  _pvInitResizeObserver();

  // Apply scale after the 280ms opening transition, in case the drawer was
  // just opened (wrapper.offsetWidth may still be 0 at this point).
  setTimeout(_pvApplyScale, 320);
}

// ── iframe onload callback (set via HTML attribute) ────────────────────────
function _pvIframeLoaded() {
  const iframe = document.getElementById('pvIframe');
  // Ignore the initial about:blank load
  if (!iframe || !iframe.src || iframe.src === 'about:blank') return;

  _pvShowLoading(false);
  _pvApplyScale();

  // Wait for the page's own JS (AOS, fonts, Tailwind) before scrolling
  setTimeout(() => _pvScrollToSection(_pvSection), 500);
}

// ── Scale the iframe to fill the wrapper at desktop width ─────────────────
// Desktop : render at PV_DESKTOP_W (1280px), CSS-scale down to fill drawer
// Mobile  : render at PV_PHONE_W  (390px), fill the full wrapper height naturally
function _pvApplyScale() {
  const wrapper = document.getElementById('pvWrapper');
  const iframe  = document.getElementById('pvIframe');
  if (!wrapper || !iframe) return;

  const W = wrapper.offsetWidth;
  const H = wrapper.offsetHeight;
  // Skip while CSS opening transition is still in progress (W is 0)
  if (W < 50 || H < 50) return;

  if (_pvDevice === 'mobile') {
    // ── Mobile mode ──────────────────────────────────────────────────
    // Render at 390px wide (real phone viewport) so the site's responsive
    // mobile layout is shown. Iframe fills the full wrapper height so the
    // user can scroll inside the iframe panel naturally.
    wrapper.style.display        = 'flex';
    wrapper.style.justifyContent = 'center';
    wrapper.style.alignItems     = 'flex-start';
    wrapper.style.overflowY      = 'hidden';
    wrapper.style.overflowX      = 'hidden';

    iframe.style.cssText = [
      'position:relative',
      `width:${PV_PHONE_W}px`,
      `height:${H}px`,
      'border:none',
      'display:block',
      'flex-shrink:0',
      'border-radius:28px',
      'box-shadow:0 0 0 10px #0d1e35,0 0 0 11px #1e3a5f,0 40px 100px rgba(0,0,0,.8)',
      'overflow:hidden',
    ].join(';') + ';';

  } else {
    // ── Desktop mode ──────────────────────────────────────────────────
    // Render at 1280px wide — activates all lg:/xl: breakpoints.
    // CSS transform scales the whole page visually to fit the drawer.
    wrapper.style.display        = '';
    wrapper.style.justifyContent = '';
    wrapper.style.alignItems     = '';
    wrapper.style.overflowY      = 'hidden';
    wrapper.style.overflowX      = 'hidden';

    const scale = W / PV_DESKTOP_W;
    // The iframe occupies 1280px × (H/scale)px in DOM space.
    // After the scale transform it visually fills exactly W × H pixels.
    iframe.style.cssText = [
      'position:absolute',
      'top:0',
      'left:0',
      `width:${PV_DESKTOP_W}px`,
      `height:${Math.ceil(H / scale)}px`,
      `transform:scale(${scale})`,
      'transform-origin:top left',
      'border:none',
      'display:block',
    ].join(';') + ';';
  }
}

// ── Watch drawer width and re-scale on resize ─────────────────────────────
function _pvInitResizeObserver() {
  if (_pvResObs) return;
  const wrapper = document.getElementById('pvWrapper');
  if (!wrapper || typeof ResizeObserver === 'undefined') return;

  _pvResObs = new ResizeObserver(() => {
    if (_pvOpen) _pvApplyScale();
  });
  _pvResObs.observe(wrapper);
}

// ── Scroll the already-loaded iframe to the active section ────────────────
function _pvScrollToSection(section) {
  const anchor = PV_ANCHORS[section];
  try {
    const iframe = document.getElementById('pvIframe');
    const doc    = iframe?.contentDocument;
    if (!doc || !doc.body) return;

    let scrollY = 0;
    if (anchor) {
      const target = doc.getElementById(anchor);
      if (target) {
        // offsetTop gives position in the iframe's unscaled coordinate space
        scrollY = Math.max(0, target.offsetTop - 20);
      }
    }
    iframe.contentWindow?.scrollTo({ top: scrollY, behavior: 'smooth' });
  } catch (e) {
    // Cross-origin safety (same-origin, so shouldn't happen)
  }
}

// ── Called by ui.js whenever the active section changes ───────────────────
function _pvOnSectionChange(section) {
  _pvSection = section;
  _pvUpdateBadge();

  if (!_pvOpen || !_pvLoaded) return;
  _pvScrollToSection(section);
}

// ── Live preview: update iframe from current form data (no save) ────────────
function scheduleLivePreviewUpdate() {
  if (!_pvOpen || !currentBusiness) return;
  clearTimeout(_pvLiveTimer);
  _pvLiveTimer = setTimeout(updateLivePreview, PV_LIVE_DEBOUNCE_MS);
}

async function updateLivePreview() {
  if (!_pvOpen || !currentBusiness || typeof collectFormData !== 'function') return;
  const iframe = document.getElementById('pvIframe');
  if (!iframe) return;

  try {
    const payload = collectFormData();
    const res = await fetch(`/api/preview/${encodeURIComponent(currentBusiness)}/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) return;
    const html = await res.text();
    iframe.srcdoc = html;
    _pvLoaded = true;
    _pvShowLoading(false);
    setTimeout(_pvApplyScale, 80);
    setTimeout(() => _pvScrollToSection(_pvSection), 120);
  } catch (e) {
    console.warn('Live preview update failed', e);
  }
}

// ── Called by api.js after a successful save ───────────────────────────────
function _pvOnSave() {
  if (!_pvOpen) return;
  clearTimeout(_pvTimer);
  clearTimeout(_pvLiveTimer);
  // Small delay lets the server finish writing before we reload
  _pvTimer = setTimeout(() => {
    _pvLoaded = false;
    _pvLoad();
  }, 450);
}

// ── Called by api.js when a different business is picked ──────────────────
function _pvReset() {
  _pvLoaded = false;
  const iframe = document.getElementById('pvIframe');
  if (iframe) iframe.src = 'about:blank';
  _pvUpdateBadge();

  if (_pvOpen) {
    if (currentBusiness) _pvLoad();
    else _pvShowEmpty(true);
  }
}

// ── Switch between desktop and mobile preview ──────────────────────────────
function _pvSetDevice(device) {
  _pvDevice = device;
  const wrapper = document.getElementById('pvWrapper');
  if (wrapper) wrapper.classList.toggle('pv-mobile', device === 'mobile');

  document.getElementById('pvBtnDesktop')?.classList.toggle('active', device === 'desktop');
  document.getElementById('pvBtnMobile')?.classList.toggle('active',  device === 'mobile');

  // Re-size iframe for the new mode
  setTimeout(_pvApplyScale, 50); // tiny delay lets classList update flush
}

// ── Manual refresh button ──────────────────────────────────────────────────
function _pvRefresh() {
  if (!currentBusiness) return;
  _pvLoaded = false;
  _pvLoad();
}

// ── Open preview in a new browser tab ─────────────────────────────────────
function _pvOpenNewTab() {
  if (!currentBusiness) return;
  window.open(`/preview/${encodeURIComponent(currentBusiness)}/`, '_blank');
}

// ── Update the "Viewing: X" badge ─────────────────────────────────────────
function _pvUpdateBadge() {
  const badge = document.getElementById('pvSectionBadge');
  if (badge) badge.textContent = PV_LABELS[_pvSection] || _pvSection;
}

// ── Loading / empty-state helpers ─────────────────────────────────────────
function _pvShowLoading(show) {
  const el = document.getElementById('pvLoading');
  if (el) el.style.display = show ? '' : 'none';
}

function _pvShowEmpty(show) {
  const empty   = document.getElementById('pvEmpty');
  const wrapper = document.getElementById('pvWrapper');
  if (empty)   { empty.style.display   = show ? 'flex' : 'none'; }
  if (wrapper) { wrapper.style.display = show ? 'none' : '';      }
}

// ── Attach live preview updates to form edits (content + colors) ───────────
(function () {
  function attachLivePreviewListeners() {
    const main = document.querySelector('main');
    if (main && !main._pvLiveAttached) {
      main._pvLiveAttached = true;
      main.addEventListener('input', scheduleLivePreviewUpdate);
      main.addEventListener('change', scheduleLivePreviewUpdate);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attachLivePreviewListeners);
  } else {
    attachLivePreviewListeners();
  }
})();
