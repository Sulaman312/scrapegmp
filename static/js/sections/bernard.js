// ── Bernard Template Specific Controls ──────────────────────────────────
let bernardBullets = [];
let bernardServicesCards = [];
let bernardWhyChooseCards = [];
let bernardServicesPageCards = [];

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
        <div><label class="fl">Image Path</label><input type="text" class="fi" value="${esc(card.image || '')}" placeholder="images/All/0001.webp" onchange="updateBernardServiceCard(${idx}, 'image', this.value)" /></div>
        <div><label class="fl">Link (optional)</label><input type="text" class="fi" value="${esc(card.link || '#contact')}" placeholder="#contact or https://..." onchange="updateBernardServiceCard(${idx}, 'link', this.value)" /></div>
      </div>
    `;
    container.appendChild(wrap);
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
        <div><label class="fl">Image Path</label><input type="text" class="fi" value="${esc(card.image || '')}" placeholder="images/All/0001.webp" onchange="updateBernardServicesPageCard(${idx}, 'image', this.value)" /></div>
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

  document.querySelectorAll('.bernard-only').forEach(el => {
    el.style.display = isBernard ? '' : 'none';
  });

  document.querySelectorAll('.multipage-only').forEach(el => {
    el.style.display = (isBernard && typeof isMultipageTemplate !== 'undefined' && isMultipageTemplate) ? '' : 'none';
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
