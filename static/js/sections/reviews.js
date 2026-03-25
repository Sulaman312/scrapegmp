// ── Reviews ───────────────────────────────────────────────────────────────
function renderReviews(allReviews) {
  const el  = document.getElementById('reviewsList');
  const lbl = document.getElementById('reviewsCountLabel');
  const reviews = allReviews.slice(0, 15);
  const total   = allReviews.length;

  lbl.textContent = `${total} total${total > 15 ? ' · showing first 15' : ''}`;
  el.innerHTML = '';

  if (!reviews.length) {
    el.innerHTML = '<p class="text-sm text-slate-600">No reviews. Reviews are pulled automatically from Google when scraping.</p>';
    return;
  }

  reviews.forEach((r, ri) => {
    const stars  = Math.min(5, Math.round(parseFloat(r.rating || r.stars || 0)));
    const starsH = '★'.repeat(stars) + '☆'.repeat(5 - stars);
    const author = r.author_name || r.author || r.reviewer_name || r.name || 'Anonymous';
    const text   = r.text || r.content || r.review_text || '';
    const date   = r.date || r.relative_date || '';

    const card = document.createElement('div');
    card.className   = 'review-card';
    card.dataset.ri  = ri;
    card.dataset.author = author;
    card.dataset.rating = stars;
    card.dataset.text   = text;
    card.dataset.date   = date;
    card.innerHTML = `
      <div class="review-card-head">
        <div class="flex items-center gap-2">
          <span class="text-yellow-400 text-sm">${starsH}</span>
          <span class="text-xs font-semibold text-slate-300">${esc(author)}</span>
          ${date ? `<span class="text-xs text-slate-600">${esc(date)}</span>` : ''}
        </div>
      </div>
      <div class="p-3">
        <p class="text-xs text-slate-400 leading-relaxed">${esc(text)}</p>
      </div>`;
    el.appendChild(card);
  });
}

function collectReviews() {
  return Array.from(document.getElementById('reviewsList').querySelectorAll('.review-card')).map(card => ({
    author_name: card.dataset.author || 'Anonymous',
    text:        card.dataset.text   || '',
    rating:      parseFloat(card.dataset.rating) || 5,
    date:        card.dataset.date   || ''
  }));
}

// ── Keywords ──────────────────────────────────────────────────────────────
function renderKeywords() {
  const el = document.getElementById('keywordsContainer');
  el.innerHTML = '';
  reviewKeywords.forEach((kw, i) => {
    const c = document.createElement('div');
    c.className = 'kw-chip';
    c.innerHTML = `<span>${esc(kw)}</span><button onclick="removeKeyword(${i})" class="ml-1 text-indigo-400 hover:text-red-400 leading-none" style="display:inline-flex;align-items:center;background:none;border:none;cursor:pointer;padding:0"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>`;
    el.appendChild(c);
  });
}

function addKeyword() {
  const inp = document.getElementById('newKeywordInput');
  const val = inp.value.trim();
  if (val && !reviewKeywords.includes(val)) {
    reviewKeywords.push(val);
    renderKeywords();
  }
  inp.value = '';
  inp.focus();
}

function removeKeyword(idx) {
  reviewKeywords.splice(idx, 1);
  renderKeywords();
}
