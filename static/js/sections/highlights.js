// ── Highlights chips ──────────────────────────────────────────────────────
function renderHighlights() {
  const editor = document.getElementById('highlightsEditor');
  const input  = document.getElementById('hl-input');
  editor.querySelectorAll('.chip').forEach(c => c.remove());

  highlights.forEach((val, i) => {
    const chip = document.createElement('div');
    chip.className = 'chip chip-teal';

    const span = document.createElement('span');
    span.contentEditable = 'true';
    span.style.cssText = 'flex:1;outline:none;cursor:text;min-width:0';
    span.textContent = val;

    span.addEventListener('blur', () => {
      const updated = span.textContent.trim();
      if (updated) {
        highlights[i] = updated;
        document.getElementById('btnSave').disabled = document.getElementById('btnGenerate').disabled = false;
      } else {
        highlights.splice(i, 1);
        renderHighlights();
      }
    });
    span.addEventListener('click', e => e.stopPropagation());
    span.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); span.blur(); }
      if (e.key === 'Escape') { span.textContent = highlights[i]; span.blur(); }
      e.stopPropagation();
    });

    const del = document.createElement('button');
    del.className = 'chip-del';
    del.innerHTML = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    del.onclick = (e) => { e.stopPropagation(); removeHighlight(i); };

    chip.appendChild(span);
    chip.appendChild(del);
    editor.insertBefore(chip, input);
  });
}

function addHighlight() {
  const inp = document.getElementById('hl-input');
  const val = inp.value.trim();
  if (!val) return;
  highlights.push(val);
  inp.value = '';
  renderHighlights();
  inp.focus();
}

function removeHighlight(idx) {
  highlights.splice(idx, 1);
  renderHighlights();
}

// ── Generic simple lists ──────────────────────────────────────────────────
function renderSimpleList(cid, items, type, prefix) {
  const el = document.getElementById(cid);
  el.innerHTML = '';
  items.forEach((v, i) => appendListRow(el, v, type, prefix, i));
}

function appendListRow(container, value, type, prefix, idx) {
  const row = document.createElement('div');
  row.className = 'flex items-start gap-2';
  row.dataset.idx = idx;
  row.innerHTML = `<input type="${type === 'url' ? 'url' : 'text'}" data-list="${prefix}" class="fi flex-1" value="${esc(value)}"/>
    <button onclick="this.closest('[data-idx]').remove()" class="btn-dx"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>`;
  container.appendChild(row);
}

function addListItem(cid, type, prefix) {
  const el = document.getElementById(cid);
  appendListRow(el, '', type, prefix, el.children.length);
  el.lastElementChild.querySelector('input')?.focus();
}

function getListValues(cid, key) {
  return Array.from(document.getElementById(cid).querySelectorAll(`[data-list="${key}"]`))
    .map(e => e.value.trim())
    .filter(Boolean);
}
