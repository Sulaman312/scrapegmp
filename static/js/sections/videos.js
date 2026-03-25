// ── Video Library state ────────────────────────────────────────────────────
let _videoList = []; // array of filenames, e.g. ["0001.mp4", "demo.webm"]

// ── Tab switching ──────────────────────────────────────────────────────────
function switchVideoTab(tab, btn) {
  document.querySelectorAll('.vid-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  const isLib = tab === 'library';
  document.getElementById('vidTab-upload').classList.toggle('hidden', isLib);
  document.getElementById('vidTab-library').classList.toggle('hidden', !isLib);
  if (isLib) {
    // When opening the Library tab, always ensure we have the latest
    // list of videos from the backend for the currently selected
    // business. This avoids any stale state issues when switching
    // companies or reloading the page.
    _ensureVideosLoaded().then(() => _refreshVideoGrid());
  }
}

// ── Render video manager (called from populateForm) ────────────────────────
function renderVideoManager(videoFiles) {
  _videoList = (videoFiles || []).slice();
  _updateVideoCount();
  _refreshVideoGrid();
}

function _updateVideoCount() {
  const el = document.getElementById('vidTotalCount');
  if (el) el.textContent = `${_videoList.length} video${_videoList.length !== 1 ? 's' : ''}`;
}

// ── Build the video grid ───────────────────────────────────────────────────
function _refreshVideoGrid() {
  const grid = document.getElementById('videoGrid');
  if (!grid) return;

  // If the local cache is empty but the currently loaded business
  // has videos in its JSON payload, hydrate from that to avoid any
  // ordering / caching issues between scripts.
  if ((!_videoList || !_videoList.length) && typeof currentData === 'object' && currentData) {
    const fromJson = currentData._video_list || currentData.videos || [];
    if (fromJson && fromJson.length) {
      _videoList = fromJson.slice();
      _updateVideoCount();
    }
  }

  if (!_videoList.length) {
    grid.innerHTML = `
<div class="vid-empty">
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"
       style="color:#475569;margin:0 auto 12px;display:block">
    <polygon points="5 3 19 12 5 21 5 3"/>
  </svg>
  <div style="font-size:13px;color:#64748b;margin-bottom:4px">No videos yet</div>
  <div style="font-size:12px;color:#475569">Upload videos using the Upload tab above.</div>
</div>`;
    return;
  }

  grid.innerHTML = _videoList.map(fname => _buildVideoCard(fname)).join('');
}

// ── Ensure videos are loaded from the server for current business ──────────
async function _ensureVideosLoaded() {
  if (!currentBusiness) return;
  try {
    // Use dedicated videos endpoint so we always reflect the files
    // that actually exist on disk, independent of enriched_data.json.
    const res = await fetch(`/api/business/${encodeURIComponent(currentBusiness)}/videos`);
    if (!res.ok) return;
    const data = await res.json();
    const list = data.files || [];
    if (Array.isArray(list)) {
      _videoList = list.slice();
      _updateVideoCount();
    }
  } catch (e) {
    // Silent failure; grid will just show "No videos yet"
  }
}

// ── Build a single video card (thumbnail click toggles play/pause) ─────────
function _buildVideoCard(filename) {
  const src = `/media/${encodeURIComponent(currentBusiness)}/videos/${encodeURIComponent(filename)}`;
  return `
<div class="vid-card">
  <div class="vid-thumb" onclick="var v=this.querySelector('video'); if(v) { v.paused ? v.play() : v.pause(); }" title="Click to play or pause">
    <video src="${esc(src)}" preload="metadata" muted playsinline controls
           onloadedmetadata="this.currentTime=0.1"></video>
    <div class="vid-play-overlay">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
        <polygon points="5 3 19 12 5 21 5 3"/>
      </svg>
    </div>
  </div>
  <div class="vid-info">
    <span class="vid-filename" title="${esc(filename)}">${esc(filename)}</span>
    <button class="vid-del-btn" onclick="deleteVideo('${escAttr(filename)}')" title="Delete video">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="3 6 5 6 21 6"/>
        <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
        <path d="M10 11v6M14 11v6"/>
        <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/>
      </svg>
    </button>
  </div>
</div>`;
}

// ── Upload handlers ────────────────────────────────────────────────────────
function handleVideoSelect(input) {
  uploadVideos(Array.from(input.files));
  input.value = '';
}

function handleVideoDrop(e) {
  e.preventDefault();
  document.getElementById('vidDropzone').classList.remove('drag-over');
  uploadVideos(Array.from(e.dataTransfer.files));
}

async function uploadVideos(files) {
  if (!currentBusiness) { showToast('Select a business first', 'error'); return; }

  const videoFiles = files.filter(f => /\.(mp4|mov|webm|avi)$/i.test(f.name));
  if (!videoFiles.length) {
    showToast('Please select video files (MP4, MOV, WebM)', 'error');
    return;
  }

  const prog = document.getElementById('vidUploadProgress');
  prog.classList.remove('hidden');
  prog.innerHTML = `
<div class="text-xs text-slate-400">
  Uploading ${videoFiles.length} video${videoFiles.length > 1 ? 's' : ''}…
  <div class="mt-1 h-1 rounded-full bg-slate-800">
    <div id="vidUploadBar" class="h-full bg-green-600 rounded-full transition-all" style="width:20%"></div>
  </div>
</div>`;

  const fd = new FormData();
  videoFiles.forEach(f => fd.append('files', f));

  try {
    const res = await fetch(
      `/api/business/${encodeURIComponent(currentBusiness)}/videos/upload`,
      { method: 'POST', body: fd }
    );
    const bar = document.getElementById('vidUploadBar');
    if (bar) bar.style.width = '90%';
    const data = await res.json();

    if (!data.success) {
      showToast('Upload failed: ' + (data.error || 'Unknown'), 'error');
    } else {
      if (bar) bar.style.width = '100%';
      const n = data.saved.length;
      if (n) showToast(`${n} video${n > 1 ? 's' : ''} uploaded`, 'success');
      if (data.errors && data.errors.length) showToast('Skipped: ' + data.errors.join(', '), 'error');

      // Add newly saved files to the list (avoid duplicates)
      data.saved.forEach(fname => {
        if (!_videoList.includes(fname)) _videoList.push(fname);
      });
      _updateVideoCount();

      // Switch to library tab to show the result
      const libBtn = document.getElementById('vtab-library');
      if (libBtn) switchVideoTab('library', libBtn);

      // Keep the visibility panel in sync
      if (currentData) {
        currentData._has_videos = _videoList.length > 0;
        currentData._video_list = _videoList.slice();
        renderVisibilityToggles();
      }
    }
  } catch (e) {
    showToast('Upload error: ' + e.message, 'error');
  }

  setTimeout(() => { prog.classList.add('hidden'); prog.innerHTML = ''; }, 2500);
}

// ── Delete a video ─────────────────────────────────────────────────────────
async function deleteVideo(filename) {
  if (!confirm(`Delete "${filename}"?\n\nThis will permanently remove the file.`)) return;

  try {
    const res = await fetch(
      `/api/business/${encodeURIComponent(currentBusiness)}/videos/${encodeURIComponent(filename)}`,
      { method: 'DELETE' }
    );
    const data = await res.json();

    if (data.success) {
      _videoList = _videoList.filter(f => f !== filename);
      _updateVideoCount();
      _refreshVideoGrid();

      // Keep visibility panel in sync
      if (currentData) {
        currentData._has_videos = _videoList.length > 0;
        currentData._video_list = _videoList.slice();
        renderVisibilityToggles();
      }
      showToast('Video deleted', 'success');
    } else {
      showToast('Delete failed: ' + (data.error || 'Unknown'), 'error');
    }
  } catch (e) {
    showToast('Delete error: ' + e.message, 'error');
  }
}
