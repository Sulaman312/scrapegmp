function renderSocialLinks(links) {
  const urlMap = {};
  (links || []).forEach(l => {
    if (typeof l === 'string') {
      const u = l.toLowerCase();
      if (u.includes('facebook'))           urlMap['facebook']  = l;
      else if (u.includes('instagram'))     urlMap['instagram'] = l;
      else if (u.includes('linkedin'))      urlMap['linkedin']  = l;
      else if (u.includes('youtube'))       urlMap['youtube']   = l;
      else if (u.includes('twitter') || u.includes('x.com')) urlMap['twitter'] = l;
      else if (u.includes('tiktok'))        urlMap['tiktok']    = l;
      else if (u.includes('whatsapp'))      urlMap['whatsapp']  = l;
      else if (u.includes('pinterest'))     urlMap['pinterest'] = l;
    } else {
      const p = (l.platform || '').toLowerCase();
      const id = SOCIAL_PLATFORMS.find(sp => p.includes(sp.id) || sp.id.includes(p.split('/')[0].trim()))?.id || '';
      if (id) urlMap[id] = l.url || '';
    }
  });

  const el = document.getElementById('socialPlatforms');
  el.innerHTML = '';
  SOCIAL_PLATFORMS.forEach(p => {
    const row = document.createElement('div');
    row.className = 'social-row';
    row.dataset.pid = p.id;
    row.innerHTML = `
      <div class="social-icon" style="background:${p.color};color:#fff">${p.svg}</div>
      <span class="social-name">${p.name}</span>
      <input type="url" class="fi" data-social="${p.id}" value="${esc(urlMap[p.id] || '')}"
             placeholder="https://…"/>`;
    el.appendChild(row);
  });
}

function collectSocialLinks() {
  return Array.from(document.querySelectorAll('#socialPlatforms [data-social]'))
    .map(inp => ({
      platform: SOCIAL_PLATFORMS.find(p => p.id === inp.dataset.social)?.name || inp.dataset.social,
      url: inp.value.trim()
    }))
    .filter(l => l.url);
}
