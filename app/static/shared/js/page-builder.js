(function () {
  const form = document.getElementById('pageStudioForm');
  if (!form) return;

  const sectionsField = document.getElementById('sectionsJsonField');
  const faqField = document.getElementById('faqJsonField');
  const linksField = document.getElementById('linksJsonField');
  const sectionsWrap = document.getElementById('sectionsBuilder');
  const faqWrap = document.getElementById('faqBuilder');
  const linksWrap = document.getElementById('linksBuilder');

  const safeParse = (value) => {
    if (!value) return [];
    try { const parsed = JSON.parse(value); return Array.isArray(parsed) ? parsed : []; } catch { return []; }
  };

  let sections = safeParse(sectionsWrap?.dataset.initial);
  let faqs = safeParse(faqWrap?.dataset.initial);
  let links = safeParse(linksWrap?.dataset.initial);

  const uid = () => Math.random().toString(36).slice(2, 10);
  const field = (label, value, key, placeholder = '', type = 'text') => `
    <div>
      <label class="form-label">${label}</label>
      <input type="${type}" class="form-control form-control-dark js-field" data-key="${key}" value="${value || ''}" placeholder="${placeholder}">
    </div>`;
  const textarea = (label, value, key, placeholder = '', rows = 3) => `
    <div>
      <label class="form-label">${label}</label>
      <textarea class="form-control form-control-dark js-field" data-key="${key}" rows="${rows}" placeholder="${placeholder}">${value || ''}</textarea>
    </div>`;

  function sync() {
    if (sectionsField) sectionsField.value = JSON.stringify(sections, null, 2);
    if (faqField) faqField.value = JSON.stringify(faqs, null, 2);
    if (linksField) linksField.value = JSON.stringify(links, null, 2);
  }

  function updateItem(arr, index, key, value) {
    arr[index][key] = value;
    sync();
  }

  function move(arr, index, dir) {
    const target = index + dir;
    if (target < 0 || target >= arr.length) return arr;
    [arr[index], arr[target]] = [arr[target], arr[index]];
    return arr;
  }

  function defaultSection() {
    return {
      id: uid(), type: 'content', name: 'New section', title: '', subtitle: '', body: '',
      bg_color: '#0f172a', text_color: '#ffffff', background_image: '', container: 'boxed',
      parallax: false, padding: 'md', course_count: 6, show_contact_form: false, slides: []
    };
  }

  function defaultFaq() { return { id: uid(), question: '', answer: '' }; }
  function defaultLink() { return { id: uid(), label: '', url: '' }; }
  function defaultSlide() { return { title: '', subtitle: '', image: '', cta_text: '', cta_url: '' }; }

  function renderSections() {
    if (!sectionsWrap) return;
    sectionsWrap.innerHTML = '';
    sections.forEach((section, index) => {
      section.slides = Array.isArray(section.slides) ? section.slides : [];
      const card = document.createElement('div');
      card.className = 'builder-card';
      card.innerHTML = `
        <div class="builder-card-header">
          <div class="builder-card-title"><span class="order-chip">#${index + 1}</span> ${section.name || section.title || 'Section'} <span class="section-preview-tag">${section.type || 'content'}</span></div>
          <div class="builder-card-actions">
            <button type="button" class="btn btn-sm btn-ghost js-up">Up</button>
            <button type="button" class="btn btn-sm btn-ghost js-down">Down</button>
            <button type="button" class="btn btn-sm btn-action btn-action-danger js-remove">Remove</button>
          </div>
        </div>
        <div class="builder-card-body">
          <div class="builder-mini-grid three">
            ${field('Internal section name', section.name, 'name', 'Hero section')}
            <div>
              <label class="form-label">Section type</label>
              <select class="form-select form-control-dark js-field" data-key="type">
                ${['content','banner_slider','course_slider','features','cta','faq_block','contact_block'].map(opt => `<option value="${opt}" ${section.type === opt ? 'selected' : ''}>${opt}</option>`).join('')}
              </select>
            </div>
            ${field('Background image', section.background_image, 'background_image', 'https://...')}
          </div>
          <div class="builder-mini-grid">
            ${field('Title', section.title, 'title', 'Section title')}
            ${field('Subtitle', section.subtitle, 'subtitle', 'Subtitle or eyebrow')}
          </div>
          <div class="builder-mini-grid">
            <div>
              <label class="form-label">Background color</label>
              <input type="color" class="form-control form-control-color js-field" data-key="bg_color" value="${section.bg_color || '#0f172a'}">
            </div>
            <div>
              <label class="form-label">Text color</label>
              <input type="color" class="form-control form-control-color js-field" data-key="text_color" value="${section.text_color || '#ffffff'}">
            </div>
          </div>
          ${textarea('Body / description', section.body, 'body', 'Use this for marketing copy, section details, or banner text.', 4)}
          <div class="builder-mini-grid three">
            <div>
              <label class="form-label">Width</label>
              <select class="form-select form-control-dark js-field" data-key="container">
                ${['boxed','wide','full'].map(opt => `<option value="${opt}" ${section.container === opt ? 'selected' : ''}>${opt}</option>`).join('')}
              </select>
            </div>
            <div>
              <label class="form-label">Padding</label>
              <select class="form-select form-control-dark js-field" data-key="padding">
                ${['sm','md','lg','xl'].map(opt => `<option value="${opt}" ${section.padding === opt ? 'selected' : ''}>${opt}</option>`).join('')}
              </select>
            </div>
            ${field('Courses to show', section.course_count, 'course_count', '6', 'number')}
          </div>
          <div class="builder-mini-grid">
            ${field('CTA text', section.cta_text, 'cta_text', 'Explore now')}
            ${field('CTA URL', section.cta_url, 'cta_url', '/courses')}
          </div>
          <div class="form-check form-switch mt-3">
            <input class="form-check-input js-field" type="checkbox" data-key="parallax" ${section.parallax ? 'checked' : ''}>
            <label class="form-check-label">Enable parallax style for this section</label>
          </div>
          <div class="form-check form-switch mt-2">
            <input class="form-check-input js-field" type="checkbox" data-key="show_contact_form" ${section.show_contact_form ? 'checked' : ''}>
            <label class="form-check-label">Show contact-form card inside this section</label>
          </div>
          <div class="inner-repeater">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <strong>Slider items</strong>
              <button type="button" class="btn btn-sm btn-ghost js-add-slide">Add slide</button>
            </div>
            <div class="slide-stack js-slides"></div>
            <div class="helper-text">Use slides for banner sliders or feature carousels. SuperAdmin manages this data only.</div>
          </div>
        </div>`;

      card.querySelectorAll('.js-field').forEach(el => {
        el.addEventListener('input', () => updateItem(sections, index, el.dataset.key, el.type === 'checkbox' ? el.checked : el.value));
        el.addEventListener('change', () => updateItem(sections, index, el.dataset.key, el.type === 'checkbox' ? el.checked : el.value));
      });
      card.querySelector('.js-up').addEventListener('click', () => { move(sections, index, -1); renderSections(); sync(); });
      card.querySelector('.js-down').addEventListener('click', () => { move(sections, index, 1); renderSections(); sync(); });
      card.querySelector('.js-remove').addEventListener('click', () => { sections.splice(index, 1); renderSections(); sync(); });
      card.querySelector('.js-add-slide').addEventListener('click', () => { section.slides.push(defaultSlide()); renderSections(); sync(); });
      const slidesWrap = card.querySelector('.js-slides');
      section.slides.forEach((slide, slideIndex) => {
        const row = document.createElement('div');
        row.className = 'builder-card';
        row.innerHTML = `<div class="builder-card-body">
          <div class="builder-mini-grid">
            ${field('Slide title', slide.title, 'title')}
            ${field('Slide image', slide.image, 'image', 'https://...')}
          </div>
          ${textarea('Slide subtitle', slide.subtitle, 'subtitle', '', 2)}
          <div class="builder-mini-grid">
            ${field('CTA text', slide.cta_text, 'cta_text')}
            ${field('CTA URL', slide.cta_url, 'cta_url', '/contact')}
          </div>
          <div class="builder-card-actions mt-2">
            <button type="button" class="btn btn-sm btn-ghost js-slide-up">Up</button>
            <button type="button" class="btn btn-sm btn-ghost js-slide-down">Down</button>
            <button type="button" class="btn btn-sm btn-action btn-action-danger js-slide-remove">Remove slide</button>
          </div>
        </div>`;
        row.querySelectorAll('.js-field').forEach(el => {
          el.addEventListener('input', () => { section.slides[slideIndex][el.dataset.key] = el.value; sync(); });
        });
        row.querySelector('.js-slide-up').addEventListener('click', () => { move(section.slides, slideIndex, -1); renderSections(); sync(); });
        row.querySelector('.js-slide-down').addEventListener('click', () => { move(section.slides, slideIndex, 1); renderSections(); sync(); });
        row.querySelector('.js-slide-remove').addEventListener('click', () => { section.slides.splice(slideIndex, 1); renderSections(); sync(); });
        slidesWrap.appendChild(row);
      });
      sectionsWrap.appendChild(card);
    });
  }

  function renderSimpleBuilder(wrap, arr, type) {
    if (!wrap) return;
    wrap.innerHTML = '';
    arr.forEach((item, index) => {
      const card = document.createElement('div');
      card.className = 'builder-card';
      if (type === 'faq') {
        card.innerHTML = `<div class="builder-card-header"><div class="builder-card-title"><span class="order-chip">#${index + 1}</span> FAQ item</div><div class="builder-card-actions"><button type="button" class="btn btn-sm btn-ghost js-up">Up</button><button type="button" class="btn btn-sm btn-ghost js-down">Down</button><button type="button" class="btn btn-sm btn-action btn-action-danger js-remove">Remove</button></div></div><div class="builder-card-body">${field('Question', item.question, 'question')}${textarea('Answer', item.answer, 'answer', '', 4)}</div>`;
      } else {
        card.innerHTML = `<div class="builder-card-header"><div class="builder-card-title"><span class="order-chip">#${index + 1}</span> Related link</div><div class="builder-card-actions"><button type="button" class="btn btn-sm btn-ghost js-up">Up</button><button type="button" class="btn btn-sm btn-ghost js-down">Down</button><button type="button" class="btn btn-sm btn-action btn-action-danger js-remove">Remove</button></div></div><div class="builder-card-body"><div class="builder-mini-grid">${field('Label', item.label, 'label', 'Apply now')}${field('URL', item.url, 'url', '/contact')}</div></div>`;
      }
      card.querySelectorAll('.js-field').forEach(el => {
        el.addEventListener('input', () => { item[el.dataset.key] = el.value; sync(); });
      });
      card.querySelector('.js-up').addEventListener('click', () => { move(arr, index, -1); renderAll(); sync(); });
      card.querySelector('.js-down').addEventListener('click', () => { move(arr, index, 1); renderAll(); sync(); });
      card.querySelector('.js-remove').addEventListener('click', () => { arr.splice(index, 1); renderAll(); sync(); });
      wrap.appendChild(card);
    });
  }

  function renderAll() {
    renderSections();
    renderSimpleBuilder(faqWrap, faqs, 'faq');
    renderSimpleBuilder(linksWrap, links, 'link');
  }

  document.getElementById('addSectionBtn')?.addEventListener('click', () => { sections.push(defaultSection()); renderAll(); sync(); });
  document.getElementById('addFaqBtn')?.addEventListener('click', () => { faqs.push(defaultFaq()); renderAll(); sync(); });
  document.getElementById('addLinkBtn')?.addEventListener('click', () => { links.push(defaultLink()); renderAll(); sync(); });

  renderAll();
  sync();
})();
