function updateFooterPreview(biz, social) {
  const b       = biz || {};
  const bizName = b.name || '';
  const _fpSVG = p => {
    const q = (p || '').toLowerCase();
    if (q.includes('facebook'))  return '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z"/></svg>';
    if (q.includes('instagram')) return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5"/><path d="M16 11.37A4 4 0 1112.63 8 4 4 0 0116 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>';
    if (q.includes('linkedin'))  return '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-4 0v7h-4v-7a6 6 0 016-6zM2 9h4v12H2z"/><circle cx="4" cy="4" r="2"/></svg>';
    if (q.includes('youtube'))   return '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M22.54 6.42a2.78 2.78 0 00-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46a2.78 2.78 0 00-1.95 1.96A29 29 0 001 12a29 29 0 00.46 5.33 2.78 2.78 0 001.95 1.77C5.12 19.56 12 19.56 12 19.56s6.88 0 8.59-.46a2.78 2.78 0 001.95-1.95A29 29 0 0023 12a29 29 0 00-.46-5.58z"/><polygon points="9.75 15.02 15.5 12 9.75 8.98" fill="#fff"/></svg>';
    if (q.includes('twitter') || q.includes(' x')) return '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.737l7.73-8.835L1.254 2.25H8.08l4.261 5.632zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>';
    if (q.includes('tiktok'))    return '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.34 6.34 0 106.34 6.34V8.75a8.12 8.12 0 004.77 1.52V6.82a4.85 4.85 0 01-1-.13z"/></svg>';
    if (q.includes('whatsapp'))  return '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>';
    return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>';
  };

  const iconHtml = (social || []).slice(0, 5).map(lk => {
    const url = typeof lk === 'string' ? lk : (lk.url || '');
    const ico = typeof lk === 'object' ? _fpSVG(lk.platform) : _fpSVG('');
    return `<a href="${esc(url)}" target="_blank" style="display:flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:8px;background:#1e293b;border:1px solid #334155;color:#94a3b8;text-decoration:none">${ico}</a>`;
  }).join('');

  const nd = document.getElementById('fp-name-display');
  if (nd) nd.textContent = bizName || '(name from Contact & Hours)';

  const sp = document.getElementById('fp-social-preview');
  if (sp) sp.innerHTML = iconHtml || '<span class="text-xs text-slate-600">No social links yet — add them in Contact &amp; Hours.</span>';

  setf('foot-address', b.address || '');
  setf('foot-phone',   b.phone   || '');
  setf('foot-email',   b.email   || '');
  setf('foot-website', b.website || '');

  const n = document.getElementById('fp-name');    if (n) n.textContent = bizName;
  const tl = document.getElementById('fp-tagline'); if (tl) tl.textContent = getf('ai-footer_tagline') || '';
  const s  = document.getElementById('fp-social');  if (s) s.innerHTML = iconHtml;
  const pa = document.getElementById('fp-prev-addr');  if (pa) pa.textContent = b.address || '';
  const pp = document.getElementById('fp-prev-phone'); if (pp) pp.textContent = b.phone   || '';
  const pe = document.getElementById('fp-prev-email'); if (pe) pe.textContent = b.email   || '';
  const c  = document.getElementById('fp-copyright');
  if (c) c.textContent = getf('ai-footer_copyright') || (bizName ? `© ${new Date().getFullYear()} ${bizName}. All rights reserved.` : '');
}

function liveFooterPreview() {
  if (!currentData) return;
  const bizName = (currentData.business || {}).name || '';
  const tl = document.getElementById('fp-tagline');
  if (tl) tl.textContent = getf('ai-footer_tagline') || '';
  const c = document.getElementById('fp-copyright');
  if (c) c.textContent = getf('ai-footer_copyright') || (bizName ? `© ${new Date().getFullYear()} ${bizName}. All rights reserved.` : '');
}

function syncField(srcId, dstId) {
  const src = document.getElementById(srcId);
  const dst = document.getElementById(dstId);
  if (src && dst) dst.value = src.value;
  document.getElementById('btnSave').disabled = document.getElementById('btnGenerate').disabled = false;
  const pa = document.getElementById('fp-prev-addr');  if (pa) pa.textContent = getf('foot-address') || '';
  const pp = document.getElementById('fp-prev-phone'); if (pp) pp.textContent = getf('foot-phone')   || '';
  const pe = document.getElementById('fp-prev-email'); if (pe) pe.textContent = getf('foot-email')   || '';
}
