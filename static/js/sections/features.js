// ── Icon categories ───────────────────────────────────────────────────────
const ICON_CATS = {
  "Popular":            ["star","favorite","thumb_up","check_circle","verified","emoji_events","grade","local_fire_department","bolt","rocket_launch"],
  "Business":           ["business","work","store","storefront","trending_up","analytics","bar_chart","attach_money","payments","account_balance","credit_card","savings","handshake","groups","person","people","support_agent","campaign","lightbulb","settings"],
  "Food & Drink":       ["restaurant","local_cafe","local_bar","fastfood","cake","dinner_dining","breakfast_dining","coffee","local_pizza","ramen_dining","bakery_dining","lunch_dining","set_meal","brunch_dining","wine_bar","liquor","icecream","cookie"],
  "Transport":          ["directions_car","local_taxi","two_wheeler","flight","train","directions_bus","directions_boat","electric_car","garage","local_shipping","delivery_dining","pedal_bike","moped","airport_shuttle"],
  "Health & Fitness":   ["local_hospital","medical_services","healing","fitness_center","health_and_safety","spa","self_improvement","monitor_heart","medication","vaccines","psychology","directions_run","sports","sports_gymnastics"],
  "Home & Place":       ["home","apartment","villa","hotel","bed","weekend","bathtub","kitchen","yard","landscape","roofing","real_estate_agent","location_city","cottage","cabin"],
  "Technology":         ["smartphone","computer","wifi","memory","code","devices","headphones","camera","tv","tablet","laptop","print","scanner","router","electrical_services","developer_mode","terminal"],
  "Communication":      ["phone","email","chat","message","forum","notifications","send","share","language","public","connect_without_contact","mail","sms","call"],
  "Creative & Media":   ["palette","brush","photo_camera","image","music_note","movie","theater_comedy","auto_stories","menu_book","edit","design_services","architecture","draw","style","format_paint"],
  "Location & Maps":    ["location_on","map","place","near_me","explore","directions","navigation","my_location","satellite","travel_explore"],
  "Nature & Environment":["nature","local_florist","eco","park","water","wb_sunny","air","thermostat","energy_savings_leaf","grass","forest","recycling","agriculture"],
  "Education":          ["school","science","biotech","psychology","calculate","functions","history_edu","library_books","class","quiz","model_training","emoji_objects"],
  "Security":           ["security","lock","lock_open","shield","verified_user","admin_panel_settings","vpn_lock","key","fingerprint","policy"],
  "Shopping":           ["shopping_cart","local_mall","shopping_bag","sell","discount","new_releases","redeem","inventory_2","category","label"],
  "Time & Schedule":    ["access_time","schedule","calendar_today","date_range","alarm","timer","update","event","event_available","pending_actions"],
};

let _pickerTarget = null;

function _getFeatureLimit() {
  return (typeof getSelectedTemplateId === 'function' && getSelectedTemplateId() === 'facade') ? 5 : 20;
}

function _updateFeatureAddState() {
  const btn = document.querySelector('#panel-features .btn-add');
  if (!btn) return;
  const count = document.querySelectorAll('.feature-card').length;
  const limit = _getFeatureLimit();
  btn.disabled = count >= limit;
  btn.style.opacity = btn.disabled ? '0.55' : '';
  btn.style.cursor = btn.disabled ? 'not-allowed' : '';
  btn.textContent = count >= limit ? `Max ${limit} Features Reached` : '+ Add Feature Card';
}

// ── Feature cards ─────────────────────────────────────────────────────────
function renderFeatures(features) {
  const el = document.getElementById('featuresList');
  el.innerHTML = '';
  const limit = _getFeatureLimit();
  features.slice(0, limit).forEach((f, i) => appendFeatureCard(el, f, i));
  _updateFeatureAddState();
}

function appendFeatureCard(container, feature, idx) {
  const card = document.createElement('div');
  card.className   = 'feature-card';
  card.dataset.fi  = idx;

  const icoName = feature.icon || '';
  const isMat   = /^[a-z][a-z0-9_]{1,49}$/.test(icoName);
  const btnInner = isMat
    ? `<span class="material-symbols-outlined">${esc(icoName)}</span>`
    : (icoName
        ? `<span style="font-size:1.4rem">${esc(icoName)}</span>`
      : `<span class="material-symbols-outlined" style="opacity:.4">add_circle_outline</span>`);

  card.innerHTML = `
    <div class="feature-card-head">
      <div class="flex items-center gap-3">
        <button type="button" class="icon-btn" data-feature="icon" data-icon="${esc(icoName)}" onclick="openIconPicker(this)" title="Click to pick icon">
          ${btnInner}
        </button>
        <span class="text-xs font-bold text-slate-500 uppercase tracking-wider">Feature ${idx + 1}</span>
      </div>
      <button onclick="removeFeatureCard(this)" class="btn-dx">Remove</button>
    </div>
    <div class="p-3 space-y-2">
      <div><label class="fl">Title</label><input type="text" data-feature="title" class="fi" value="${esc(feature.title || '')}" placeholder="Feature title"/></div>
      <div><label class="fl">Description</label><textarea data-feature="description" class="fi" rows="3" placeholder="Brief description…">${esc(feature.description || '')}</textarea></div>
    </div>`;
  container.appendChild(card);
}

function addFeature() {
  const el = document.getElementById('featuresList');
  if (el.children.length >= _getFeatureLimit()) {
    showToast(`You can select up to ${_getFeatureLimit()} features for this template.`, 'info');
    _updateFeatureAddState();
    return;
  }
  appendFeatureCard(el, { icon: '', title: '', description: '' }, el.children.length);
  el.lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  _updateFeatureAddState();
}

function removeFeatureCard(btn) {
  btn.closest('.feature-card').remove();
  document.querySelectorAll('.feature-card').forEach((c, i) => {
    c.dataset.fi = i;
    c.querySelector('.text-xs.font-bold').textContent = `Feature ${i + 1}`;
  });
  _updateFeatureAddState();
}

function collectFeatures() {
  return Array.from(document.querySelectorAll('.feature-card')).map(c => ({
    icon:        (c.querySelector('[data-feature="icon"]').dataset.icon || '').trim(),
    title:       c.querySelector('[data-feature="title"]').value.trim(),
    description: c.querySelector('[data-feature="description"]').value.trim(),
  })).filter(f => f.title || f.description);
}

// ── Icon picker ───────────────────────────────────────────────────────────
function openIconPicker(btn) {
  _pickerTarget = btn;
  const current = btn.dataset.icon || '';

  const overlay = document.createElement('div');
  overlay.className = 'icon-picker-modal';
  overlay.id = 'iconPickerModal';
  overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };

  let gridRows = '';
  for (const [cat, icons] of Object.entries(ICON_CATS)) {
    gridRows += `<div class="icon-cat-label">${cat}</div>`;
    icons.forEach(ic => {
      gridRows += `<div class="icon-cell${ic === current ? ' selected' : ''}" data-name="${ic}" onclick="selectIcon('${ic}')" title="${ic}">
        <span class="material-symbols-outlined">${ic}</span>
      </div>`;
    });
  }

  overlay.innerHTML = `
    <div class="icon-picker-box">
      <div class="icon-picker-head">
        <span class="material-symbols-outlined" style="color:#16a34a">grid_view</span>
        <span style="font-weight:700;color:#f1f5f9;font-size:.95rem">Pick an Icon</span>
        <input class="icon-picker-search" id="icoSearch" placeholder="Search icons…" oninput="filterIcons(this.value)" autocomplete="off"/>
        <button class="icon-picker-close" onclick="document.getElementById('iconPickerModal').remove()" title="Close"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
      </div>
      <div class="icon-grid" id="iconGrid">${gridRows}</div>
    </div>`;
  document.body.appendChild(overlay);
  setTimeout(() => overlay.querySelector('#icoSearch').focus(), 80);
}

function selectIcon(name) {
  if (!_pickerTarget) return;
  _pickerTarget.dataset.icon = name;
  _pickerTarget.innerHTML = `<span class="material-symbols-outlined">${name}</span>`;
  document.getElementById('iconPickerModal')?.remove();
  _pickerTarget = null;
}

function filterIcons(q) {
  const grid = document.getElementById('iconGrid');
  if (!grid) return;
  const term = q.toLowerCase().trim();
  let visible = 0;
  grid.querySelectorAll('.icon-cell').forEach(cell => {
    const show = !term || cell.dataset.name.includes(term);
    cell.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  grid.querySelectorAll('.icon-cat-label').forEach(l => { l.style.display = term ? 'none' : ''; });
}
