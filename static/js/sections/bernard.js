// ── Bernard Template Specific Controls ──────────────────────────────────
let bernardBullets = [];

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

// Toggle Bernard-specific fields based on template selection
function toggleBernardFields(template) {
  const isBernard = template === 'bernard';

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
