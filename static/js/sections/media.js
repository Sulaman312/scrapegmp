// ── Media Library state ───────────────────────────────────────────────────
let _imgList = [];
let _heroImg = '';
let _selPath = '';

// ── Tab switching ─────────────────────────────────────────────────────────
function switchMediaTab(tab, btn) {
  document.querySelectorAll('.media-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  const isLib = tab === 'library';
  document.getElementById('mediaTab-upload').classList.toggle('hidden', isLib);
  document.getElementById('mediaTab-library').classList.toggle('hidden', !isLib);
  document.getElementById('mediaSearchInput').classList.toggle('hidden', !isLib);
  if (isLib && _imgList.length) _refreshMediaGrid();
}

// ── Render image manager ──────────────────────────────────────────────────
function renderImageManager(images, heroImage) {
  _imgList  = images.slice();
  _heroImg  = heroImage || (images[0] || '');
  _selPath  = '';
  document.getElementById('imgTotalCount').textContent =
    `${images.length} image${images.length !== 1 ? 's' : ''}`;
  _refreshMediaGrid();
  _refreshMediaSidebar();
}

function _refreshMediaGrid() {
  const grid = document.getElementById('mediaGrid');
  grid.innerHTML = '';
  if (!_imgList.length) {
    grid.innerHTML = '<div class="media-empty">No images yet — upload some using the Upload Files tab.</div>';
    return;
  }
  _imgList.forEach(imgPath => {
    const isHero = imgPath === _heroImg;
    const cell   = document.createElement('div');
    cell.className    = 'media-cell' + (imgPath === _selPath ? ' selected' : '');
    cell.dataset.path = imgPath;
    const src = `/media/${currentBusiness}/${imgPath}`;
    cell.innerHTML = `
      <img src="${esc(src)}" loading="lazy" onerror="this.style.background='#1e293b'"/>
      <div class="mc-check"><svg viewBox="0 0 12 12"><polyline points="1.5,6 5,9.5 10.5,2.5"/></svg></div>
      ${isHero ? '<div class="mc-hero">HERO</div>' : ''}`;
    cell.addEventListener('click', () => selectMediaCell(imgPath));
    grid.appendChild(cell);
  });
}

function selectMediaCell(imgPath) {
  _selPath = imgPath;
  document.querySelectorAll('.media-cell').forEach(c => {
    c.classList.toggle('selected', c.dataset.path === imgPath);
  });
  _refreshMediaSidebar();
}

function _refreshMediaSidebar() {
  const sb = document.getElementById('mediaSidebar');
  if (!_selPath || !_imgList.includes(_selPath)) {
    sb.innerHTML = '<div class="media-sidebar-empty">Select an image<br>to view its details</div>';
    return;
  }
  const imgPath = _selPath;
  const src     = `/media/${currentBusiness}/${imgPath}`;
  const name    = imgPath.split('/').pop();
  const folder  = imgPath.split('/').slice(0, -1).join('/') || 'root';
  const isHero  = imgPath === _heroImg;
  const idx     = _imgList.indexOf(imgPath);

  sb.innerHTML = `
    <div class="media-detail-head">Attachment Details</div>
    <div class="media-detail-preview">
      <img src="${esc(src)}" onerror="this.style.background='#1e293b'"/>
    </div>
    <div class="media-detail-body">
      <div>
        <div class="media-detail-label">File Name</div>
        <div class="media-detail-name">${esc(name)}</div>
      </div>
      <div>
        <div class="media-detail-label">Folder</div>
        <div class="media-detail-path">${esc(folder)}</div>
      </div>
      <div class="media-detail-divider"></div>
      <label class="flex items-center gap-2 cursor-pointer p-2 rounded-lg transition-colors
             ${isHero ? 'bg-green-950 border border-green-800' : 'border border-slate-700 hover:border-slate-500'}">
        <input type="radio" name="heroImg" value="${esc(imgPath)}" ${isHero ? 'checked' : ''}
               onchange="_setHeroImg('${esc(imgPath)}')" class="accent-green-500 shrink-0"/>
        <span class="text-xs ${isHero ? 'text-green-400 font-semibold flex items-center gap-1' : 'text-slate-400'}">
          ${isHero ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Current Hero Image' : 'Set as Hero Image'}
        </span>
      </label>
      <div class="media-detail-divider"></div>
      <div class="media-detail-actions">
        <button onclick="_moveImg('${esc(imgPath)}',-1)" class="btn-xs w-full" ${idx === 0 ? 'disabled' : ''}><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 15l-6-6-6 6"/></svg> Move Up</button>
        <button onclick="_moveImg('${esc(imgPath)}',1)"  class="btn-xs w-full" ${idx === _imgList.length - 1 ? 'disabled' : ''}><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg> Move Down</button>
        <button onclick="_removeImg('${esc(imgPath)}')" class="btn-dx w-full mt-1"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg> Remove from site</button>
      </div>
    </div>`;
}

function _setHeroImg(imgPath) {
  _heroImg = imgPath;
  _refreshMediaGrid();
  _refreshMediaSidebar();
  _syncHeroImgPicker();
}

function _moveImg(imgPath, dir) {
  const i = _imgList.indexOf(imgPath);
  const j = i + dir;
  if (j < 0 || j >= _imgList.length) return;
  [_imgList[i], _imgList[j]] = [_imgList[j], _imgList[i]];
  _refreshMediaGrid();
  _refreshMediaSidebar();
  _syncHeroImgPicker();
}

function _removeImg(imgPath) {
  _imgList = _imgList.filter(p => p !== imgPath);
  if (_heroImg === imgPath) _heroImg = _imgList[0] || '';
  if (_selPath === imgPath) _selPath = '';
  document.getElementById('imgTotalCount').textContent =
    `${_imgList.length} image${_imgList.length !== 1 ? 's' : ''}`;
  _refreshMediaGrid();
  _refreshMediaSidebar();
  _syncHeroImgPicker();
}

function filterMediaGrid(q) {
  const lq = q.toLowerCase();
  document.querySelectorAll('.media-cell').forEach(c => {
    c.classList.toggle('media-hidden', !!lq && !c.dataset.path.toLowerCase().includes(lq));
  });
}

// ── Hero image picker (Hero section) ─────────────────────────────────────
function renderHeroImgPicker(images, heroImage) {
  const el = document.getElementById('heroImgPicker');
  if (!el) return;
  el.innerHTML = '';
  if (!images.length) {
    el.innerHTML = '<p class="text-sm text-slate-600">No images. Upload in the Gallery section.</p>';
    return;
  }
  const grid = document.createElement('div');
  grid.className = 'hero-img-grid';
  images.forEach((imgPath, idx) => {
    const isHero = heroImage ? imgPath === heroImage : idx === 0;
    const src    = `/media/${currentBusiness}/${imgPath}`;
    const name   = imgPath.split('/').pop();
    const cell   = document.createElement('div');
    cell.className    = 'hero-img-cell' + (isHero ? ' selected' : '');
    cell.dataset.path = imgPath;
    cell.innerHTML = `
      <img class="hero-img-thumb" src="${esc(src)}" loading="lazy" onerror="this.style.background='#1e293b'"/>
      <div class="hero-img-name" title="${esc(name)}">${esc(name)}</div>
      <div class="hero-img-check"><svg viewBox="0 0 11 11"><polyline points="1.5,5.5 4.5,9 9.5,1.5"/></svg></div>
      ${isHero ? '<div class="hero-img-badge">HERO</div>' : ''}`;
    cell.addEventListener('click', () => onHeroPickerCellClick(imgPath));
    grid.appendChild(cell);
  });
  el.appendChild(grid);
}

function _syncHeroImgPicker() { renderHeroImgPicker(_imgList, _heroImg); }

function onHeroPickerCellClick(imgPath) {
  _setHeroImg(imgPath);
  document.querySelectorAll('.hero-img-cell').forEach(c => {
    const h = c.dataset.path === imgPath;
    c.classList.toggle('selected', h);
    const badge = c.querySelector('.hero-img-badge');
    if (h && !badge) {
      const b = document.createElement('div');
      b.className = 'hero-img-badge';
      b.textContent = 'HERO';
      c.appendChild(b);
    } else if (!h && badge) {
      badge.remove();
    }
  });
}

function onHeroPickerChange(radio) { _setHeroImg(radio.value); }
function onHeroChange(radio)       { _setHeroImg(radio.value); }

// ── Collect helpers ───────────────────────────────────────────────────────
function collectImages()  { return _imgList.slice(); }
function getHeroImage()   { return _heroImg; }

// ── File upload ───────────────────────────────────────────────────────────
function handleFileSelect(input) { uploadFiles(Array.from(input.files)); input.value = ''; }
function handleFileDrop(e) {
  e.preventDefault();
  document.getElementById('uploadDropzone').style.borderColor = '#334155';
  uploadFiles(Array.from(e.dataTransfer.files));
}

async function uploadFiles(files) {
  if (!currentBusiness) { showToast('Select a business first', 'error'); return; }
  if (!files.length) return;

  const prog = document.getElementById('uploadProgress');
  prog.classList.remove('hidden');
  prog.innerHTML = `<div class="text-xs text-slate-400">Uploading ${files.length} file${files.length > 1 ? 's' : ''}…
    <div class="mt-1 h-1 rounded-full bg-slate-800">
      <div id="uploadBar" class="h-full bg-indigo-500 rounded-full transition-all" style="width:30%"></div>
    </div></div>`;

  const fd = new FormData();
  files.forEach(f => fd.append('files', f));
  try {
    const res  = await fetch(`/api/business/${encodeURIComponent(currentBusiness)}/upload`, { method: 'POST', body: fd });
    document.getElementById('uploadBar').style.width = '90%';
    const data = await res.json();
    if (!data.success) {
      showToast('Upload failed: ' + (data.error || 'Unknown'), 'error');
    } else {
      document.getElementById('uploadBar').style.width = '100%';
      const n = data.saved.length;
      showToast(`${n} file${n > 1 ? 's' : ''} uploaded`, 'success');
      if (data.errors.length) showToast('Skipped: ' + data.errors.join(', '), 'error');
      const existing = collectImages();
      data.saved.forEach(p => { if (!existing.includes(p)) _imgList.push(p); });
      if (!_heroImg && _imgList.length) _heroImg = _imgList[0];
      document.getElementById('imgTotalCount').textContent =
        `${_imgList.length} image${_imgList.length !== 1 ? 's' : ''}`;
      _refreshMediaGrid();
      _syncHeroImgPicker();
      const libBtn = document.getElementById('mtab-library');
      if (libBtn) switchMediaTab('library', libBtn);
    }
  } catch (e) {
    showToast('Upload error: ' + e.message, 'error');
  }
  setTimeout(() => { prog.classList.add('hidden'); prog.innerHTML = ''; }, 2000);
}
