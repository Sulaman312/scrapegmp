// ── Bernard Template Specific Controls ──────────────────────────────────
let bernardBullets = [];
let bernardServicesCards = [];
let bernardWhyChooseCards = [];
let bernardServicesPageCards = [];
let _serviceImagePickerTarget = null;

function renderBernardBullets() {
  const container = document.getElementById('bernardBulletsList');
  if (!container) return;

  container.innerHTML = '';

  bernardBullets.forEach((bullet, idx) => {
    const bulletDiv = document.createElement('div');
    bulletDiv.className = 'border border-slate-200 rounded-lg p-3 space-y-2';

    bulletDiv.innerHTML = `
      <div class="flex items-center justify-between gap-2">
        <input type="text" class="fi font-semibold" placeholder="Bullet Title"
          value="${bullet.title || ''}"
          onchange="updateBernardBullet(${idx}, 'title', this.value)" />
        <button class="btn-icon-del" onclick="removeBernardBullet(${idx})" title="Remove bullet">
          <svg viewBox="0 0 24 24" width="18" height="18">
            <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
      <textarea class="fi" rows="2" placeholder="Bullet description"
        onchange="updateBernardBullet(${idx}, 'description', this.value)">${bullet.description || ''}</textarea>
    `;

    container.appendChild(bulletDiv);
  });
}

function addBernardBullet() {
  bernardBullets.push({ title: '', description: '' });
  renderBernardBullets();
  document.getElementById('btnSave').disabled = false;
  document.getElementById('btnGenerate').disabled = false;
}

function removeBernardBullet(idx) {
  bernardBullets.splice(idx, 1);
  renderBernardBullets();
  document.getElementById('btnSave').disabled = false;
  document.getElementById('btnGenerate').disabled = false;
}

function updateBernardBullet(idx, field, value) {
  if (bernardBullets[idx]) {
    bernardBullets[idx][field] = value;
    document.getElementById('btnSave').disabled = false;
    document.getElementById('btnGenerate').disabled = false;
  }
}

function renderBernardServicesCards(cards) {
  if (Array.isArray(cards)) {
    bernardServicesCards = cards.slice(0, 20).map(c => ({
      title: c?.title || '',
      description: c?.description || '',
      image: c?.image || '',
      link: c?.link || '#contact',
    }));
  }

  const container = document.getElementById('bernardServicesCardsList');
  if (!container) return;
  container.innerHTML = '';

  bernardServicesCards.forEach((card, idx) => {
    const wrap = document.createElement('div');
    wrap.className = 'feature-card';
    wrap.innerHTML = `
      <div class="feature-card-head">
        <div class="flex items-center gap-3">
          <span class="text-xs font-bold text-slate-500 uppercase tracking-wider">Service Card ${idx + 1}</span>
        </div>
        <button onclick="removeBernardServiceCard(${idx})" class="btn-dx">Remove</button>
      </div>
      <div class="p-3 space-y-2">
        <div><label class="fl">Title</label><input type="text" class="fi" value="${esc(card.title || '')}" onchange="updateBernardServiceCard(${idx}, 'title', this.value)" /></div>
        <div><label class="fl">Text</label><textarea class="fi" rows="3" onchange="updateBernardServiceCard(${idx}, 'description', this.value)">${esc(card.description || '')}</textarea></div>
        <div>
          <label class="fl">Image</label>
          <div class="flex gap-2">
            <input type="text" id="bernardServiceImg${idx}" class="fi flex-1" value="${esc(card.image || '')}" placeholder="images/All/0001.webp" onchange="updateBernardServiceCard(${idx}, 'image', this.value)" />
            <button type="button" class="btn-dx" onclick="openServiceImagePicker(${idx})">Select Image</button>
          </div>
        </div>
        <div><label class="fl">Link (optional)</label><input type="text" class="fi" value="${esc(card.link || '#contact')}" placeholder="#contact or https://..." onchange="updateBernardServiceCard(${idx}, 'link', this.value)" /></div>
      </div>
    `;
    container.appendChild(wrap);
  });
}

function openServiceImagePicker(idx, source = 'services') {
  const imageList = (typeof collectImages === 'function') ? collectImages() : [];
  if (!imageList.length) {
    if (typeof showToast === 'function') {
      showToast('No images available. Add images in Media first.', 'info');
    }
    return;
  }

  _serviceImagePickerTarget = { idx, source };
  const existingModal = document.getElementById('serviceImagePickerModal');
  if (existingModal) existingModal.remove();

  const currentPath = source === 'servicesPage'
    ? (bernardServicesPageCards[idx]?.image || '')
    : (bernardServicesCards[idx]?.image || '');

  const overlay = document.createElement('div');
  overlay.className = 'icon-picker-modal';
  overlay.id = 'serviceImagePickerModal';
  overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };

  const cells = imageList.map((imgPath) => {
    const selected = imgPath === currentPath ? ' selected' : '';
    const src = `/media/${currentBusiness}/${imgPath}`;
    const name = imgPath.split('/').pop();
    return `
      <div class="hero-img-cell${selected}" data-path="${esc(imgPath)}" title="${esc(imgPath)}">
        <img class="hero-img-thumb" src="${esc(src)}" loading="lazy" onerror="this.style.background='#1e293b'"/>
        <div class="hero-img-name">${esc(name)}</div>
        <div class="hero-img-check"><svg viewBox="0 0 11 11"><polyline points="1.5,5.5 4.5,9 9.5,1.5"/></svg></div>
      </div>
    `;
  }).join('');

  overlay.innerHTML = `
    <div class="icon-picker-box" style="width:min(920px, 94vw);">
      <div class="icon-picker-head">
        <span class="material-symbols-outlined" style="color:#16a34a">image</span>
        <span style="font-weight:700;color:#f1f5f9;font-size:.95rem">Select Service Image</span>
        <input class="icon-picker-search" id="serviceImgSearch" placeholder="Search images…" oninput="filterServiceImagePicker(this.value)" autocomplete="off"/>
        <button class="icon-picker-close" onclick="document.getElementById('serviceImagePickerModal')?.remove()" title="Close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <div id="serviceImageGrid" class="hero-img-grid" style="padding:1rem;max-height:68vh;overflow:auto;">${cells}</div>
    </div>
  `;

  document.body.appendChild(overlay);

  overlay.querySelectorAll('#serviceImageGrid .hero-img-cell').forEach((cell) => {
    cell.addEventListener('click', () => selectServiceImageFromPicker(cell.dataset.path || ''));
  });

  setTimeout(() => overlay.querySelector('#serviceImgSearch')?.focus(), 50);
}

function selectServiceImageFromPicker(imgPath) {
  if (!_serviceImagePickerTarget || !imgPath) return;

  const { idx, source } = _serviceImagePickerTarget;
  if (source === 'servicesPage') {
    updateBernardServicesPageCard(idx, 'image', imgPath);
    const input = document.getElementById(`bernardServicesPageImg${idx}`);
    if (input) input.value = imgPath;
  } else {
    updateBernardServiceCard(idx, 'image', imgPath);
    const input = document.getElementById(`bernardServiceImg${idx}`);
    if (input) input.value = imgPath;
  }

  document.getElementById('serviceImagePickerModal')?.remove();
  _serviceImagePickerTarget = null;
}

function filterServiceImagePicker(query) {
  const term = (query || '').toLowerCase().trim();
  const cells = document.querySelectorAll('#serviceImageGrid .hero-img-cell');
  cells.forEach((cell) => {
    const path = (cell.dataset.path || '').toLowerCase();
    const show = !term || path.includes(term);
    cell.style.display = show ? '' : 'none';
  });
}

function addBernardServiceCard() {
  bernardServicesCards.push({ title: '', description: '', image: '', link: '#contact' });
  renderBernardServicesCards();
}

function removeBernardServiceCard(idx) {
  bernardServicesCards.splice(idx, 1);
  renderBernardServicesCards();
}

function updateBernardServiceCard(idx, field, value) {
  if (!bernardServicesCards[idx]) return;
  bernardServicesCards[idx][field] = value;
}

function collectBernardServicesCards() {
  return bernardServicesCards
    .map(c => ({
      title: (c.title || '').trim(),
      description: (c.description || '').trim(),
      image: (c.image || '').trim(),
      link: (c.link || '#contact').trim() || '#contact',
    }))
    .filter(c => c.title || c.description || c.image);
}

function renderBernardWhyChooseCards(cards) {
  if (Array.isArray(cards)) {
    bernardWhyChooseCards = cards.slice(0, 20).map(c => ({
      icon: c?.icon || 'star',
      title: c?.title || '',
      description: c?.description || '',
    }));
  }

  const container = document.getElementById('bernardWhyChooseCardsList');
  if (!container) return;
  container.innerHTML = '';

  bernardWhyChooseCards.forEach((card, idx) => {
    const wrap = document.createElement('div');
    wrap.className = 'feature-card';
    wrap.innerHTML = `
      <div class="feature-card-head">
        <div class="flex items-center gap-3">
          <span class="text-xs font-bold text-slate-500 uppercase tracking-wider">Why Choose Card ${idx + 1}</span>
        </div>
        <button onclick="removeBernardWhyChooseCard(${idx})" class="btn-dx">Remove</button>
      </div>
      <div class="p-3 space-y-2">
        <div><label class="fl">Icon</label><input type="text" class="fi" value="${esc(card.icon || 'star')}" placeholder="material symbol, e.g. verified" onchange="updateBernardWhyChooseCard(${idx}, 'icon', this.value)" /></div>
        <div><label class="fl">Title</label><input type="text" class="fi" value="${esc(card.title || '')}" onchange="updateBernardWhyChooseCard(${idx}, 'title', this.value)" /></div>
        <div><label class="fl">Text</label><textarea class="fi" rows="3" onchange="updateBernardWhyChooseCard(${idx}, 'description', this.value)">${esc(card.description || '')}</textarea></div>
      </div>
    `;
    container.appendChild(wrap);
  });
}

function addBernardWhyChooseCard() {
  bernardWhyChooseCards.push({ icon: 'star', title: '', description: '' });
  renderBernardWhyChooseCards();
}

function removeBernardWhyChooseCard(idx) {
  bernardWhyChooseCards.splice(idx, 1);
  renderBernardWhyChooseCards();
}

function updateBernardWhyChooseCard(idx, field, value) {
  if (!bernardWhyChooseCards[idx]) return;
  bernardWhyChooseCards[idx][field] = value;
}

function collectBernardWhyChooseCards() {
  return bernardWhyChooseCards
    .map(c => ({
      icon: (c.icon || 'star').trim() || 'star',
      title: (c.title || '').trim(),
      description: (c.description || '').trim(),
    }))
    .filter(c => c.title || c.description);
}

function renderBernardServicesPageCards(cards) {
  if (Array.isArray(cards)) {
    bernardServicesPageCards = cards.slice(0, 20).map(c => ({
      title: c?.title || '',
      description: c?.description || '',
      image: c?.image || '',
      link: c?.link || '#contact',
    }));
  }

  const container = document.getElementById('bernardServicesPageCardsList');
  if (!container) return;
  container.innerHTML = '';

  bernardServicesPageCards.forEach((card, idx) => {
    const wrap = document.createElement('div');
    wrap.className = 'feature-card';
    wrap.innerHTML = `
      <div class="feature-card-head">
        <div class="flex items-center gap-3">
          <span class="text-xs font-bold text-slate-500 uppercase tracking-wider">Service Card ${idx + 1}</span>
        </div>
        <button onclick="removeBernardServicesPageCard(${idx})" class="btn-dx">Remove</button>
      </div>
      <div class="p-3 space-y-2">
        <div><label class="fl">Title</label><input type="text" class="fi" value="${esc(card.title || '')}" onchange="updateBernardServicesPageCard(${idx}, 'title', this.value)" /></div>
        <div><label class="fl">Text</label><textarea class="fi" rows="3" onchange="updateBernardServicesPageCard(${idx}, 'description', this.value)">${esc(card.description || '')}</textarea></div>
        <div>
          <label class="fl">Image</label>
          <div class="flex gap-2">
            <input type="text" id="bernardServicesPageImg${idx}" class="fi flex-1" value="${esc(card.image || '')}" placeholder="images/All/0001.webp" onchange="updateBernardServicesPageCard(${idx}, 'image', this.value)" />
            <button type="button" class="btn-dx" onclick="openServiceImagePicker(${idx}, 'servicesPage')">Select Image</button>
          </div>
        </div>
        <div><label class="fl">Link (optional)</label><input type="text" class="fi" value="${esc(card.link || '#contact')}" placeholder="#contact or https://..." onchange="updateBernardServicesPageCard(${idx}, 'link', this.value)" /></div>
      </div>
    `;
    container.appendChild(wrap);
  });
}

function addBernardServicesPageCard() {
  bernardServicesPageCards.push({ title: '', description: '', image: '', link: '#contact' });
  renderBernardServicesPageCards();
}

function removeBernardServicesPageCard(idx) {
  bernardServicesPageCards.splice(idx, 1);
  renderBernardServicesPageCards();
}

function updateBernardServicesPageCard(idx, field, value) {
  if (!bernardServicesPageCards[idx]) return;
  bernardServicesPageCards[idx][field] = value;
}

function collectBernardServicesPageCards() {
  return bernardServicesPageCards
    .map(c => ({
      title: (c.title || '').trim(),
      description: (c.description || '').trim(),
      image: (c.image || '').trim(),
      link: (c.link || '#contact').trim() || '#contact',
    }))
    .filter(c => c.title || c.description || c.image);
}

// Toggle Bernard-specific fields based on template selection
function toggleBernardFields(template) {
  const isBernard = template === 'bernard';
  const isFacade = template === 'facade';
  const isMultipage = typeof isMultipageTemplate !== 'undefined' && isMultipageTemplate;

  document.querySelectorAll('.bernard-only').forEach(el => {
    el.style.display = isBernard ? '' : 'none';
  });

  document.querySelectorAll('.multipage-only').forEach(el => {
    el.style.display = ((isBernard || isFacade) && isMultipage) ? '' : 'none';
  });

  // Show/hide highlights (default templates)
  const highlightsCard = document.getElementById('highlightsCard');
  if (highlightsCard) {
    highlightsCard.style.display = isBernard ? 'none' : '';
  }

  // Show/hide Bernard bullet points
  const bernardBulletsCard = document.getElementById('bernardAboutBulletsCard');
  if (bernardBulletsCard) {
    bernardBulletsCard.style.display = isBernard ? '' : 'none';
  }

  // Show/hide Years of Experience
  const bernardYearsCard = document.getElementById('bernardYearsCard');
  if (bernardYearsCard) {
    bernardYearsCard.style.display = isBernard ? '' : 'none';
  }
}
