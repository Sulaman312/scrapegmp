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
  // Store the business URL for later use
  window.currentBusinessUrl = biz.url || `/site/${encodeURIComponent(name)}/`;
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
    document.getElementById('btnSave').disabled = document.getElementById('btnGenerate').disabled = document.getElementById('btnReScrape').disabled = false;
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
    // Use the subdomain URL if available, otherwise fall back to /site/ path
    const url = window.currentBusinessUrl || `/site/${encodeURIComponent(currentBusiness)}/`;
    window.open(url, '_blank');
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
  updateModalProgress(1);

  try {
    // Step 1: Start the background job
    const startRes = await fetch('/api/scrape-and-enrich', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url, language: language }),
    });

    if (!startRes.ok) {
      const contentType = startRes.headers.get('content-type');
      let errorMsg = `Server error (${startRes.status})`;

      if (contentType && contentType.includes('application/json')) {
        try {
          const errorData = await startRes.json();
          errorMsg = errorData.error || errorMsg;
        } catch (e) {
          // JSON parsing failed
        }
      } else {
        const text = await startRes.text();
        console.error('Non-JSON response:', text.substring(0, 200));
        errorMsg = `Server error: received HTML instead of JSON (status ${startRes.status})`;
      }

      hideAddBusinessModal();
      showToast('Failed to start scrape: ' + errorMsg, 'error');
      return;
    }

    const startResult = await startRes.json();

    if (!startResult.success) {
      hideAddBusinessModal();
      showToast('Failed: ' + (startResult.error || 'Unknown error'), 'error');
      return;
    }

    const jobId = startResult.job_id;
    console.log('Scrape job started:', jobId);

    // Step 2: Poll for job completion
    let lastProgress = 0;
    const pollInterval = 2000; // Poll every 2 seconds
    const maxWaitTime = 600000; // 10 minutes max
    const startTime = Date.now();

    while (Date.now() - startTime < maxWaitTime) {
      await new Promise(resolve => setTimeout(resolve, pollInterval));

      const statusRes = await fetch(`/api/scrape-status/${jobId}`);
      if (!statusRes.ok) {
        console.error('Failed to check job status');
        continue;
      }

      const statusData = await statusRes.json();
      if (!statusData.success) {
        hideAddBusinessModal();
        showToast('Job status error: ' + (statusData.error || 'Unknown'), 'error');
        return;
      }

      const { status, progress, business_name, error } = statusData;
      console.log(`Job ${jobId} status: ${status} (${progress}%)`);

      // Update progress bar based on status
      if (progress > lastProgress) {
        lastProgress = progress;
        if (progress < 30) {
          updateModalProgress(1); // Scraping
        } else if (progress < 90) {
          updateModalProgress(2); // Enriching
        } else {
          updateModalProgress(3); // Finalizing
        }
      }

      // Check if job completed
      if (status === 'completed') {
        updateModalProgress(3);
        await new Promise(resolve => setTimeout(resolve, 500));

        hideAddBusinessModal();
        showToast(`Business "${business_name}" added successfully!`, 'success');
        await loadBusinesses();
        await pickCompany(business_name);
        return;
      }

      // Check if job failed
      if (status === 'failed') {
        hideAddBusinessModal();
        showToast('Scrape failed: ' + (error || 'Unknown error'), 'error');
        return;
      }

      // Continue polling for queued, scraping, enriching states
    }

    // Timeout
    hideAddBusinessModal();
    showToast('Scrape timed out after 10 minutes. It may still be processing.', 'error');

  } catch (e) {
    hideAddBusinessModal();
    console.error('Scrape and enrich error:', e);

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
    applyPreset(...firstPreset.c, firstPreset.cta);
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

  // Close re-scrape modal when clicking outside
  document.getElementById('reScrapeModal')?.addEventListener('click', e => {
    if (e.target.id === 'reScrapeModal') hideReScrapeModal();
  });

  // Add keyboard listener for modals
  document.addEventListener('keydown', e => {
    const addModal = document.getElementById('addBusinessModal');
    const rescrapeModal = document.getElementById('reScrapeModal');

    if (addModal && !addModal.classList.contains('hidden')) {
      if (e.key === 'Escape') hideAddBusinessModal();
      if (e.key === 'Enter') submitAddBusiness();
    }

    if (rescrapeModal && !rescrapeModal.classList.contains('hidden')) {
      if (e.key === 'Escape') hideReScrapeModal();
      if (e.key === 'Enter') confirmReScrape();
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

// ── Re-scrape ─────────────────────────────────────────────────────────────
function reScrapeData() {
  if (!currentBusiness) return;
  document.getElementById('reScrapeModal').classList.remove('hidden');
}

function hideReScrapeModal() {
  document.getElementById('reScrapeModal').classList.add('hidden');
}

async function confirmReScrape() {
  hideReScrapeModal();

  const btn = document.getElementById('btnReScrape');
  setBtn(btn, '<div class="spinner"></div>', 'Re-scraping…', true);
  showToast('Re-scraping business data from Google Maps…', 'info');

  try {
    const res = await fetch(`/api/business/${encodeURIComponent(currentBusiness)}/re-scrape`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const result = await res.json();

    if (result.success) {
      showToast('✓ Data re-scraped successfully!', 'success');
      // Reload the business to show updated data
      const refresh = await fetch(`/api/business/${encodeURIComponent(currentBusiness)}`);
      currentData = await refresh.json();
      populateForm(currentData);
      if (typeof _pvRefresh === 'function') _pvRefresh();
    } else {
      showToast('Re-scrape failed: ' + (result.error || 'Unknown error'), 'error');
    }
  } catch (e) {
    showToast('Re-scrape error: ' + e.message, 'error');
  } finally {
    setBtn(btn, svgRefresh(), 'Re-scrape', false);
  }
}

function svgRefresh() {
  return `<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>`;
}
