// ── Business list ─────────────────────────────────────────────────────────
async function loadBusinesses() {
  try {
    allBusinesses = await (await fetch('/api/businesses')).json();
    renderCompanyMenu();
  } catch {
    showToast('Failed to load businesses', 'error');
  }
}

// ── Templates list ────────────────────────────────────────────────────────
async function loadTemplates() {
  try {
    const templates = await (await fetch('/api/templates')).json();
    if (typeof setTemplateDefinitions === 'function') {
      const defs = {};
      (templates || []).forEach(t => { defs[t.id] = t; });
      setTemplateDefinitions(defs);
    }
    const selector = document.getElementById('template-select');
    if (selector) {
      selector.innerHTML = templates.map(t =>
        `<option value="${t.id}" title="${t.description}">${t.name}</option>`
      ).join('');
      if (typeof applyTemplateSections === 'function') applyTemplateSections(selector.value || 'default');
    }
  } catch (e) {
    console.error('Failed to load templates:', e);
    // Leave default option intact if error
  }
}

function renderCompanyMenu() {
  const businessItems = allBusinesses.map(b => `
    <div class="company-option ${currentBusiness === b.name ? 'selected' : ''}" onclick="pickCompany('${escAttr(b.name)}')">
      <span class="dot ${b.has_website ? 'bg-green-500' : 'bg-slate-500'}"></span>
      <div>
        <div class="font-medium text-slate-200">${esc(b.name)}</div>
        <div class="text-xs text-slate-500 mt-0.5">${b.has_ai ? '✦ AI enriched' : 'Not enriched'} · ${b.has_website ? 'Site ready' : 'No site'}</div>
      </div>
    </div>`).join('');

  const addButton = `
    <div class="company-option-add" onclick="showAddBusinessModal()">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
      </svg>
      <span>Add Business</span>
    </div>`;

  document.getElementById('companyMenu').innerHTML = businessItems + addButton;
}

function toggleCompanyMenu()  { menuOpen ? closeCompanyMenu() : openCompanyMenu(); }
function openCompanyMenu()    { menuOpen = true;  renderCompanyMenu(); document.getElementById('companyMenu').classList.remove('hidden'); }
function closeCompanyMenu()   { menuOpen = false; document.getElementById('companyMenu').classList.add('hidden'); }

async function pickCompany(name) {
  closeCompanyMenu();
  if (name === currentBusiness) return;
  currentBusiness = name;
  const biz = allBusinesses.find(b => b.name === name) || {};
  document.getElementById('companyBtnLabel').textContent = name;
  document.getElementById('companyDot').className = `dot ${biz.has_website ? 'bg-green-500' : 'bg-slate-500'}`;
  try {
    const res = await fetch(`/api/business/${encodeURIComponent(name)}`);
    if (!res.ok) throw new Error('Not found');
    currentData = await res.json();
    populateForm(currentData);
    if (typeof applyTemplateSections === 'function') {
      applyTemplateSections(currentData.template || 'default');
    }
    if (typeof renderVisibilityToggles === 'function') {
      renderVisibilityToggles();
    }
    if (typeof updatePageSelector === 'function') {
      updatePageSelector();
    }
    if (typeof _pvReset === 'function') _pvReset();
    document.getElementById('emptyState').classList.add('hidden');
    document.getElementById('navHint').classList.add('hidden');
    document.getElementById('sectionNav').classList.remove('hidden');
    document.getElementById('btnSave').disabled = document.getElementById('btnGenerate').disabled = false;
    if (typeof isMultipageTemplate !== 'undefined' && isMultipageTemplate) {
      if (currentPage === 'services') {
        switchSection('services-page');
      } else if (currentPage === 'contact') {
        switchSection('contact');
      } else {
        switchSection('our-services');
      }
    } else {
      switchSection('hero');
    }
  } catch (e) {
    showToast('Failed to load: ' + e.message, 'error');
  }
}

// ── Save ──────────────────────────────────────────────────────────────────
async function saveChanges() {
  if (!currentBusiness) return;
  const btn = document.getElementById('btnSave');
  setBtn(btn, '<div class="spinner"></div>', 'Saving…', true);
  try {
    const payload = collectFormData();
    const res = await fetch(`/api/business/${encodeURIComponent(currentBusiness)}/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const r = await res.json();
    if (r.success) {
      currentData = payload;
      showAutosaveIndicator();
      if (typeof _pvOnSave === 'function') _pvOnSave();
    } else { showToast('Save failed: ' + (r.error || 'Unknown'), 'error'); showAutosaveError(); }
  } catch (e) {
    showToast('Save error: ' + e.message, 'error');
    showAutosaveError();
  } finally {
    setBtn(btn, svgSave(), 'Save Draft', false);
  }
}

// ── Generate ──────────────────────────────────────────────────────────────
// IMPORTANT: This now uses the LAST SAVED draft only.
// Live form edits (not yet saved) affect the preview drawer,
// but they do NOT change the generated site unless you click
// "Save Draft" first.
async function generateWebsite() {
  if (!currentBusiness) return;
  const btn = document.getElementById('btnGenerate');
  setBtn(btn, '<div class="spinner"></div>', 'Saving & Generating…', true);

  // First, save the current form data (including template selection)
  try {
    const formData = collectFormData();
    await fetch(`/api/business/${encodeURIComponent(currentBusiness)}/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });
  } catch (e) {
    console.warn('Failed to save draft before generating:', e);
  }

  showToast('Running generate_site.py with selected template…', 'info');
  try {
    const r = await (await fetch(`/api/business/${encodeURIComponent(currentBusiness)}/generate`, { method: 'POST' })).json();
    if (r.success) {
      showToast('Website generated! Click Open Site.', 'success');
      document.getElementById('btnPreview').style.display = '';
      loadBusinesses();
    } else {
      showToast('Generation failed — check console.', 'error');
      console.error(r.error);
    }
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  } finally {
    setBtn(btn, svgGen(), 'Generate Website', false);
  }
}

// Opens the PUBLISHED site only (last generated). Not the draft preview.
function previewWebsite() {
  if (currentBusiness) {
    window.open(`/site/${encodeURIComponent(currentBusiness)}/`, '_blank');
  }
}

// ── SEO character counters ────────────────────────────────────────────────
function setupSEOCounters() {
  const counter = (id, lid, w, o) => {
    const inp = document.getElementById(id);
    const lbl = document.getElementById(lid);
    inp.addEventListener('input', () => {
      const n = inp.value.length;
      lbl.textContent = `${n} characters`;
      lbl.className = `text-xs mt-1 ${n > o ? 'char-over' : n > w ? 'char-warn' : 'char-ok'}`;
    });
  };
  counter('ai-seo_title',       'seoTitleCount', 50, 60);
  counter('ai-seo_description', 'seoDescCount',  150, 160);
}

// ── Add Business Modal ────────────────────────────────────────────────────
function showAddBusinessModal() {
  closeCompanyMenu();
  const modal = document.getElementById('addBusinessModal');
  if (modal) {
    // Reset to input form
    document.getElementById('modalInputForm').classList.remove('hidden');
    document.getElementById('modalProgressView').classList.add('hidden');
    document.getElementById('modalSubmitBtn').classList.remove('hidden');
    document.getElementById('modalCancelBtn').textContent = 'Cancel';
    document.getElementById('modalCloseBtn').style.display = '';

    modal.classList.remove('hidden');
    document.getElementById('businessUrlInput').value = '';
    document.getElementById('businessUrlInput').focus();
  }
}

function hideAddBusinessModal() {
  const modal = document.getElementById('addBusinessModal');
  if (modal) modal.classList.add('hidden');
}

function showModalProgress() {
  // Hide input form, show progress
  document.getElementById('modalInputForm').classList.add('hidden');
  document.getElementById('modalProgressView').classList.remove('hidden');
  document.getElementById('modalSubmitBtn').classList.add('hidden');
  document.getElementById('modalCancelBtn').textContent = 'Running...';
  document.getElementById('modalCancelBtn').disabled = true;
  document.getElementById('modalCloseBtn').style.display = 'none';

  // Reset all steps
  ['progressStep1', 'progressStep2', 'progressStep3'].forEach(id => {
    const el = document.getElementById(id);
    el.classList.remove('active', 'completed');
  });
  document.getElementById('modalProgressBar').style.width = '0%';
}

function updateModalProgress(step) {
  // step: 1 = scraping, 2 = AI enrichment, 3 = finalizing
  const steps = ['progressStep1', 'progressStep2', 'progressStep3'];
  const percentages = [33, 66, 100];

  // Mark previous steps as completed
  for (let i = 0; i < step - 1; i++) {
    const el = document.getElementById(steps[i]);
    el.classList.remove('active');
    el.classList.add('completed');
  }

  // Mark current step as active
  if (step <= 3) {
    const currentEl = document.getElementById(steps[step - 1]);
    currentEl.classList.add('active');
    currentEl.classList.remove('completed');
  }

  // Update progress bar
  document.getElementById('modalProgressBar').style.width = percentages[step - 1] + '%';
}

async function submitAddBusiness() {
  const urlInput = document.getElementById('businessUrlInput');
  const url = urlInput.value.trim();

  if (!url) {
    showToast('Please enter a Google Maps URL', 'error');
    return;
  }

  if (!url.includes('google.com/maps')) {
    showToast('Please enter a valid Google Maps URL', 'error');
    return;
  }

  // Get selected language
  const selectedLangBtn = document.querySelector('.language-btn.active');
  const language = selectedLangBtn ? selectedLangBtn.dataset.lang : 'fr';

  // Show progress view
  showModalProgress();

  // Step 1: Scraping - starts immediately
  updateModalProgress(1);

  try {
    // Start the API call
    const fetchPromise = fetch('/api/scrape-and-enrich', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url, language: language }),
    });

    // Wait at least 3 seconds on step 1 (scraping takes time)
    await Promise.all([
      fetchPromise,
      new Promise(resolve => setTimeout(resolve, 3000))
    ]);

    const res = await fetchPromise;

    // Check if response is OK
    if (!res.ok) {
      const contentType = res.headers.get('content-type');
      let errorMsg = `Server error (${res.status})`;

      // Try to get error message from response
      if (contentType && contentType.includes('application/json')) {
        try {
          const errorData = await res.json();
          errorMsg = errorData.error || errorMsg;
        } catch (e) {
          // JSON parsing failed, use default message
        }
      } else {
        // Not JSON - probably HTML error page
        const text = await res.text();
        console.error('Non-JSON response:', text.substring(0, 200));
        errorMsg = `Server error: received HTML instead of JSON (status ${res.status})`;
      }

      hideAddBusinessModal();
      showToast('Failed: ' + errorMsg, 'error');
      return;
    }

    const result = await res.json();

    if (result.success) {
      // Step 2: AI Enrichment (show this step)
      updateModalProgress(2);
      await new Promise(resolve => setTimeout(resolve, 1500));

      // Step 3: Finalizing
      updateModalProgress(3);
      await new Promise(resolve => setTimeout(resolve, 1000));

      hideAddBusinessModal();
      showToast(`Business "${result.business_name}" added successfully!`, 'success');
      await loadBusinesses();
      await pickCompany(result.business_name);
    } else {
      hideAddBusinessModal();
      showToast('Failed: ' + (result.error || 'Unknown error'), 'error');
    }
  } catch (e) {
    hideAddBusinessModal();
    console.error('Scrape and enrich error:', e);

    // Provide more specific error message for JSON parsing errors
    if (e.message && e.message.includes('JSON')) {
      showToast('Error: Server returned invalid response. Check console for details.', 'error');
    } else {
      showToast('Error: ' + e.message, 'error');
    }
  }
}

// ── Template Selection ────────────────────────────────────────────────────
function updateTemplateAndPreview() {
  const selectedTemplate = document.getElementById('template-select').value;
  currentData = currentData || {};
  currentData.template = selectedTemplate;
  if (typeof applyTemplateSections === 'function') {
    applyTemplateSections(selectedTemplate);
  }
  if (typeof renderVisibilityToggles === 'function') {
    renderVisibilityToggles();
  }
  // Toggle Bernard-specific fields
  if (typeof toggleBernardFields === 'function') {
    toggleBernardFields(selectedTemplate);
  }
  // Update page selector visibility for multipage templates
  if (typeof updatePageSelector === 'function') {
    updatePageSelector();
  }
  // Update color presets for the selected template and apply the first one
  if (typeof updatePresetsForTemplate === 'function') {
    updatePresetsForTemplate(selectedTemplate);
  }
  // Apply the first preset of the template as default color scheme
  if (typeof PRESETS !== 'undefined' && PRESETS.length > 0 && typeof applyPreset === 'function') {
    const firstPreset = PRESETS[0];
    applyPreset(...firstPreset.c);
  }
  // Use updateLivePreview to send currentData with the new template via POST
  if (typeof updateLivePreview === 'function') {
    updateLivePreview();
  }
  showToast(`Template changed to: ${selectedTemplate}`, 'info');
}

// ── Bootstrap ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadBusinesses();
  loadTemplates();
  setupSEOCounters();
  buildPresets();
  updateColorPreviews();
  document.addEventListener('click', e => {
    if (menuOpen && !document.getElementById('companyDropdown').contains(e.target)) closeCompanyMenu();
  });

  // Add keyboard listener for modal
  document.addEventListener('keydown', e => {
    const modal = document.getElementById('addBusinessModal');
    if (modal && !modal.classList.contains('hidden')) {
      if (e.key === 'Escape') hideAddBusinessModal();
      if (e.key === 'Enter') submitAddBusiness();
    }
  });

  // Language selector buttons
  document.querySelectorAll('.language-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.language-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
});
