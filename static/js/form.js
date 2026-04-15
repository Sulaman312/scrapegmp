function _deriveBernardWhyChooseCards(ai) {
  if (Array.isArray(ai.why_choose_us_cards) && ai.why_choose_us_cards.length) {
    const cards = ai.why_choose_us_cards.slice(0, 20);
    while (cards.length < 3) {
      cards.push({ icon: 'star', title: `Advantage ${cards.length + 1}`, description: '' });
    }
    return cards;
  }
  const legacy = Array.isArray(ai.features) ? ai.features : [];
  const cards = legacy.slice(0, 3).map(f => ({
    icon: f?.icon || 'star',
    title: f?.title || '',
    description: f?.description || '',
  }));
  while (cards.length < 3) {
    cards.push({ icon: 'star', title: `Advantage ${cards.length + 1}`, description: '' });
  }
  return cards;
}

function _withSequentialServiceImages(cards, images) {
  const imagePool = Array.isArray(images) ? images.filter(Boolean) : [];
  if (!imagePool.length || !Array.isArray(cards) || !cards.length) return cards;

  const cardImages = cards
    .map(c => (c?.image || '').trim())
    .filter(Boolean);
  const autoSequence = cardImages.length === 0 || new Set(cardImages).size <= 1;

  let fallbackIndex = 0;
  return cards.map((card, idx) => {
    const current = (card?.image || '').trim();
    let nextImage = current;

    if (autoSequence || !current) {
      nextImage = imagePool[idx % imagePool.length] || '';
    }

    if (!nextImage) {
      nextImage = imagePool[fallbackIndex % imagePool.length] || '';
      fallbackIndex += 1;
    }

    return {
      ...card,
      image: nextImage,
    };
  });
}

function _deriveBernardServicesCards(ai, images) {
  const imagePool = Array.isArray(images) ? images.filter(Boolean) : [];
  const fallbackImage = imagePool.length ? imagePool[0] : '';
  if (Array.isArray(ai.services_cards) && ai.services_cards.length) {
    let cards = ai.services_cards.slice(0, 20).map(c => ({
      title: c?.title || '',
      description: c?.description || '',
      image: c?.image || fallbackImage,
      link: c?.link || '#contact',
    }));
    while (cards.length < 4) {
      const nextImage = imagePool.length ? imagePool[cards.length % imagePool.length] : fallbackImage;
      cards.push({ title: `Service ${cards.length + 1}`, description: '', image: nextImage, link: '#contact' });
    }
    return _withSequentialServiceImages(cards, imagePool);
  }
  const legacy = Array.isArray(ai.features) ? ai.features : [];
  let cards = legacy.slice(3, 7).map(f => ({
    title: f?.title || '',
    description: f?.description || '',
    image: f?.image || fallbackImage,
    link: f?.link || '#contact',
  }));
  while (cards.length < 4) {
    const nextImage = imagePool.length ? imagePool[cards.length % imagePool.length] : fallbackImage;
    cards.push({ title: `Service ${cards.length + 1}`, description: '', image: nextImage, link: '#contact' });
  }
  return _withSequentialServiceImages(cards, imagePool);
}

function _deriveBernardServicesPageCards(ai, images) {
  const imagePool = Array.isArray(images) ? images.filter(Boolean) : [];
  const fallbackImage = imagePool.length ? imagePool[0] : '';
  if (Array.isArray(ai.services_page_cards) && ai.services_page_cards.length) {
    let cards = ai.services_page_cards.slice(0, 20).map(c => ({
      title: c?.title || '',
      description: c?.description || '',
      image: c?.image || fallbackImage,
      link: c?.link || '#contact',
    }));
    while (cards.length < 4) {
      const nextImage = imagePool.length ? imagePool[cards.length % imagePool.length] : fallbackImage;
      cards.push({ title: `Service ${cards.length + 1}`, description: '', image: nextImage, link: '#contact' });
    }
    return _withSequentialServiceImages(cards, imagePool);
  }
  return _withSequentialServiceImages(_deriveBernardServicesCards(ai, images), imagePool);
}

// ── Populate form from data ───────────────────────────────────────────────
function populateForm(data) {
  const biz   = data.business || {};
  const ai    = data.ai       || {};
  const theme = data.theme    || {};

  // Template
  const selectedTemplate = data.template || 'default';
  setf('template-select', selectedTemplate);

  // Hero
  setf('ai-brand_short_name', ai.brand_short_name || biz.name || '');
  setf('ai-tagline',        ai.tagline);
  setf('ai-hero_subtitle',  ai.hero_subtitle);
  setf('ai-cta_primary',    ai.cta_primary);
  setf('ai-cta_secondary',  ai.cta_secondary);
  setf('ai-cta_primary_url',  ai.cta_primary_url  || ai.cta_link || biz.website || '');
  setf('ai-cta_secondary_url', ai.cta_secondary_url || ai.cta_link || biz.website || '');

  // Features
  renderFeatures(ai.features || []);
  setf('ai-services_small_text', ai.services_small_text);
  setf('ai-services_heading', ai.services_heading);
  setf('ai-why_choose_us_heading', ai.why_choose_us_heading);
  if (typeof renderBernardServicesCards === 'function') {
    renderBernardServicesCards(_deriveBernardServicesCards(ai, data.images || []));
  }
  if (typeof renderBernardWhyChooseCards === 'function') {
    renderBernardWhyChooseCards(_deriveBernardWhyChooseCards(ai));
  }
  if (typeof renderBernardServicesPageCards === 'function') {
    renderBernardServicesPageCards(_deriveBernardServicesPageCards(ai, data.images || []));
  }

  // Values
  renderSimpleList('valuesList', (ai.values || []).slice(0, 5), 'text', 'value');

  // Gallery
  renderImageManager(data.images || [], theme.hero_image || '');
  renderHeroImgPicker(data.images || [], theme.hero_image || '');
  if (typeof renderValuesImgPicker === 'function') {
    renderValuesImgPicker(data.images || [], theme.values_image || '');
  }
  if (typeof renderCompanyImagePickers === 'function') {
    renderCompanyImagePickers(data.images || [], theme.company_image_1 || '', theme.company_image_2 || '');
  }
  renderWhyChooseUsImageSelect(data.images || [], theme.why_choose_us_image || '');

  // Videos
  renderVideoManager(data._video_list || data.videos || []);
  // Make sure we always hydrate from the latest API data if the
  // videos module is loaded, so any existing files on disk show up
  // in the Library tab even on first load.
  if (typeof _ensureVideosLoaded === 'function') {
    _ensureVideosLoaded().then(() => {
      if (typeof _refreshVideoGrid === 'function') _refreshVideoGrid();
    });
  }

  // About
  setf('ai-about_paragraph', ai.about_paragraph);
  const aboutText = (ai.about_paragraph || '').trim();
  const aboutMid = Math.floor(aboutText.length / 2);
  let aboutSplitAt = aboutText.indexOf(' ', aboutMid);
  if (aboutSplitAt === -1) aboutSplitAt = aboutMid;
  const aboutLeftFallback = (aboutText.slice(0, aboutSplitAt).trim() || aboutText);
  const aboutRightFallback = (aboutText.slice(aboutSplitAt).trim() || aboutText);
  setf('ai-about_story_left', ai.about_story_left || (data.about || {}).story_left || aboutLeftFallback);
  setf('ai-about_story_right', ai.about_story_right || (data.about || {}).story_right || aboutRightFallback);
  setf('f-description',      biz.description);
  const saved = (data.about || {}).highlights || [];
  if (saved.length) {
    highlights = [...saved];
  } else {
    const ap = (ai.about_paragraph || '').trim();
    highlights = (data.website_data || {}).paragraphs || [];
    highlights = highlights.filter(p => p && p.trim().length > 40 && p.trim() !== ap).slice(0, 4);
  }
  renderHighlights();
  renderSimpleList('aboutAttrsList', data.about_attrs || [], 'text', 'attr');

  // Bernard-specific fields
  bernardBullets = ai.about_bullet_points || [];
  if (typeof renderBernardBullets === 'function') {
    renderBernardBullets();
  }
  setf('raw-years_of_experience', (data._raw || {}).years_of_experience || 0);

  // Toggle Bernard fields based on template
  if (typeof toggleBernardFields === 'function') {
    toggleBernardFields(selectedTemplate);
  }

  // Reviews
  reviewKeywords = [...(data.review_keywords || [])];
  renderKeywords();
  renderReviews(data.reviews || []);

  // Contact
  ['name', 'place_type', 'phone', 'email', 'website', 'price_range', 'rating', 'reviews_count',
    'address', 'latitude', 'longitude', 'google_maps_url'].forEach(k => setf('f-' + k, biz[k]));
  renderHours(biz.hours || {});
  renderSocialLinks(data.social_links || []);

  // CTA
  const ctaHeadingFallback = ((data.website_data || {}).headings || []).filter(h => h && h.length > 5)[8] || ai.tagline || '';
  setf('ai-cta_heading',   ai.cta_heading   || ctaHeadingFallback);
  setf('ai-cta_subtitle',  ai.cta_subtitle  || ai.hero_subtitle || '');
  setf('ai-cta_btn_label', ai.cta_btn_label || ai.cta_primary   || '');
  setf('ai-cta_link',      ai.cta_link      || biz.website      || '');
  setf('ai-cta_banner_btn_label', ai.cta_banner_btn_label || '');
  setf('ai-cta_banner_btn_link',  ai.cta_banner_btn_link  || '');

  // Footer
  const footerTaglineFallback = ai.about_paragraph || ai.hero_subtitle || '';
  setf('ai-footer_tagline',   ai.footer_tagline  || footerTaglineFallback);
  const autoCopyright = `© ${new Date().getFullYear()} ${biz.name || ''}. All rights reserved.`;
  setf('ai-footer_copyright', ai.footer_copyright || autoCopyright);
  updateFooterPreview(biz, data.social_links || []);

  // SEO
  setf('ai-seo_title',       ai.seo_title);
  setf('ai-seo_description', ai.seo_description);
  ['ai-seo_title', 'ai-seo_description'].forEach(id =>
    document.getElementById(id).dispatchEvent(new Event('input'))
  );

  // Services Page
  setf('ai-services_page_seo_title', ai.services_page_seo_title);
  setf('ai-services_page_seo_description', ai.services_page_seo_description);
  setf('ai-services_page_hero_title', ai.services_page_hero_title);
  setf('ai-services_page_hero_subtitle', ai.services_page_hero_subtitle);
  setf('ai-services_page_small_text', ai.services_page_small_text);
  setf('ai-services_page_heading', ai.services_page_heading);
  setf('ai-services_page_description', ai.services_page_description);
  setf('ai-services_cta_heading', ai.services_cta_heading);
  setf('ai-services_cta_text', ai.services_cta_text);
  setf('ai-services_cta_button', ai.services_cta_button);

  // Contact Page
  setf('ai-contact_page_seo_title', ai.contact_page_seo_title);
  setf('ai-contact_page_seo_description', ai.contact_page_seo_description);
  setf('ai-contact_page_hero_title', ai.contact_page_hero_title);
  setf('ai-contact_page_hero_subtitle', ai.contact_page_hero_subtitle);
  setf('ai-contact_page_small_text', ai.contact_page_small_text);
  setf('ai-contact_page_heading', ai.contact_page_heading);
  setf('ai-contact_page_description', ai.contact_page_description);

  // Colors
  setColorPair('color1',    theme.color1    || DEF.color1);
  setColorPair('color2',    theme.color2    || DEF.color2);
  setColorPair('color3',    theme.color3    || DEF.color3);
  setColorPair('cta',       theme.cta_color || DEF.color1);
  setColorPair('hero_dark', theme.hero_dark || DEF.hero_dark);
  updateColorPreviews();
  syncAllCtaControls();

  // Logo-based colors
  if (typeof loadLogoColors === 'function') {
    loadLogoColors(data.logo_colors || null);
  }

  document.getElementById('btnPreview').style.display = (data.has_website !== false) ? '' : 'none';

  // Section visibility
  renderVisibilityToggles();
}

// ── Collect form data ─────────────────────────────────────────────────────
function collectFormData() {
  const aiCurrent = (currentData && currentData.ai) ? currentData.ai : {};
  const hours = {};
  document.querySelectorAll('[data-hours]').forEach(el => {
    const v = el.value.trim();
    if (v) hours[el.dataset.hours] = v;
  });

  const theme = {
    color1:    getColorVal('color1')   || DEF.color1,
    color2:    getColorVal('color2')   || DEF.color2,
    color3:    getColorVal('color3')   || DEF.color3,
    cta_color: getColorVal('cta')      || getColorVal('color1') || DEF.color1,
    hero_dark: getColorVal('hero_dark')|| DEF.hero_dark,
    hero_image: getHeroImage(),
    why_choose_us_image: getf('theme-why_choose_us_image') || '',
  };
  if (typeof getValuesImage === 'function') {
    theme.values_image = getValuesImage();
  }
  if (typeof getCompanyStoryImages === 'function') {
    Object.assign(theme, getCompanyStoryImages());
  }

  const payload = {
    template: getf('template-select') || 'default',
    language: (currentData && currentData.language) ? currentData.language : 'fr',
    business: {
      name:          getf('f-name'),
      place_type:    getf('f-place_type'),
      phone:         getf('f-phone'),
      email:         getf('f-email'),
      website:       getf('f-website'),
      price_range:   getf('f-price_range'),
      rating:        toFloat(getf('f-rating')),
      reviews_count: toInt(getf('f-reviews_count')),
      address:       getf('f-address'),
      description:   getf('f-description'),
      latitude:      getf('f-latitude')  || (currentData.business || {}).latitude,
      longitude:     getf('f-longitude') || (currentData.business || {}).longitude,
      google_maps_url: getf('f-google_maps_url'),
      plus_code:     (currentData.business || {}).plus_code || '',
      hours,
    },
    ai: {
      brand_short_name:  getf('ai-brand_short_name'),
      tagline:          getf('ai-tagline'),
      hero_subtitle:    getf('ai-hero_subtitle'),
      cta_primary:      getf('ai-cta_primary'),
      cta_primary_url:  getf('ai-cta_primary_url'),
      cta_secondary:    getf('ai-cta_secondary'),
      cta_secondary_url: getf('ai-cta_secondary_url'),
      about_paragraph:  getf('ai-about_paragraph'),
      about_story_left: getf('ai-about_story_left'),
      about_story_right: getf('ai-about_story_right'),
      seo_title:        getf('ai-seo_title'),
      seo_description:  getf('ai-seo_description'),
      features:         collectFeatures(),
      services_cards: typeof collectBernardServicesCards === 'function'
        ? collectBernardServicesCards()
        : (_deriveBernardServicesCards(aiCurrent, (currentData && currentData.images) || []) || []),
      services_page_cards: typeof collectBernardServicesPageCards === 'function'
        ? collectBernardServicesPageCards()
        : (_deriveBernardServicesPageCards(aiCurrent, (currentData && currentData.images) || []) || []),
      why_choose_us_cards: typeof collectBernardWhyChooseCards === 'function'
        ? collectBernardWhyChooseCards()
        : (_deriveBernardWhyChooseCards(aiCurrent) || []),
      services_small_text: getf('ai-services_small_text'),
      services_heading: getf('ai-services_heading'),
      why_choose_us_heading: getf('ai-why_choose_us_heading'),
      cta_heading:      getf('ai-cta_heading'),
      cta_subtitle:     getf('ai-cta_subtitle'),
      cta_btn_label:    getf('ai-cta_btn_label'),
      cta_link:         getf('ai-cta_link'),
      cta_banner_btn_label: getf('ai-cta_banner_btn_label'),
      cta_banner_btn_link:  getf('ai-cta_banner_btn_link'),
      footer_tagline:   getf('ai-footer_tagline'),
      footer_copyright: getf('ai-footer_copyright'),
      values:           getListValues('valuesList', 'value').slice(0, 5),
      about_bullet_points: bernardBullets,
      // Services Page fields
      services_page_seo_title: getf('ai-services_page_seo_title') || aiCurrent.services_page_seo_title || '',
      services_page_seo_description: getf('ai-services_page_seo_description') || aiCurrent.services_page_seo_description || '',
      services_page_hero_title: getf('ai-services_page_hero_title') || aiCurrent.services_page_hero_title || '',
      services_page_hero_subtitle: getf('ai-services_page_hero_subtitle') || aiCurrent.services_page_hero_subtitle || '',
      services_page_small_text: getf('ai-services_page_small_text') || aiCurrent.services_page_small_text || '',
      services_page_heading: getf('ai-services_page_heading') || aiCurrent.services_page_heading || '',
      services_page_description: getf('ai-services_page_description') || aiCurrent.services_page_description || '',
      services_cta_heading: getf('ai-services_cta_heading') || aiCurrent.services_cta_heading || '',
      services_cta_text: getf('ai-services_cta_text') || aiCurrent.services_cta_text || '',
      services_cta_button: getf('ai-services_cta_button') || aiCurrent.services_cta_button || '',
      // Contact Page fields
      contact_page_seo_title: getf('ai-contact_page_seo_title') || aiCurrent.contact_page_seo_title || '',
      contact_page_seo_description: getf('ai-contact_page_seo_description') || aiCurrent.contact_page_seo_description || '',
      contact_page_hero_title: getf('ai-contact_page_hero_title') || aiCurrent.contact_page_hero_title || '',
      contact_page_hero_subtitle: getf('ai-contact_page_hero_subtitle') || aiCurrent.contact_page_hero_subtitle || '',
      contact_page_small_text: getf('ai-contact_page_small_text') || aiCurrent.contact_page_small_text || '',
      contact_page_heading: getf('ai-contact_page_heading') || aiCurrent.contact_page_heading || '',
      contact_page_description: getf('ai-contact_page_description') || aiCurrent.contact_page_description || '',
    },
    _raw: {
      years_of_experience: toInt(getf('raw-years_of_experience')) || 0,
    },
    website_data:    currentData.website_data    || {},
    theme,
    images:          collectImages(),
    reviews:         collectReviews(),
    review_keywords: reviewKeywords,
    qa:              currentData.qa              || [],
    updates:         currentData.updates         || [],
    popular_times:   currentData.popular_times   || {},
    about:           { ...((currentData.about) || {}), highlights },
    about_attrs:     getListValues('aboutAttrsList', 'attr'),
    social_links:    collectSocialLinks(),
    web_results:        currentData.web_results        || [],
    related_places:     currentData.related_places     || [],
    section_visibility: currentData.section_visibility || {},
  };

  // Preserve video helper fields so section visibility logic keeps
  // treating the Videos section as having content after autosaves.
  if (currentData && typeof currentData._has_videos !== 'undefined') {
    payload._has_videos = currentData._has_videos;
  }
  if (currentData && Array.isArray(currentData._video_list)) {
    payload._video_list = currentData._video_list.slice();
  }
  if (currentData && Array.isArray(currentData.videos)) {
    payload.videos = currentData.videos.slice();
  }

  return payload;
}

function renderWhyChooseUsImageSelect(images, selected) {
  const select = document.getElementById('theme-why_choose_us_image');
  if (!select) return;
  const list = Array.isArray(images) ? images.slice() : [];
  const autoFallback = list[2] || list[0] || '';
  const current = selected || autoFallback;

  const options = ['<option value="">Auto-select</option>']
    .concat(list.map(p => `<option value="${escAttr(p)}">${esc(p.split('/').pop())}</option>`))
    .join('');

  select.innerHTML = options;
  select.value = list.includes(current) ? current : '';
}
