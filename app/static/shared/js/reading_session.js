(function () {
  const app = document.getElementById('readingSessionApp');
  if (!app) return;

  const autosaveUrl = app.dataset.autosaveUrl;
  const wordSupportUrl = app.dataset.wordSupportUrl;
  const targetLanguageLabel = app.dataset.targetLanguageLabel || 'English';
  const totalQuestions = Number(app.dataset.totalQuestions || 0);

  let elapsedSeconds = Number(app.dataset.initialElapsed || 0);
  const timerSeconds = Number(app.dataset.timerSeconds || 0);

  const progressBar = document.getElementById('readingProgressBar');
  const answeredCountEl = document.getElementById('answeredCount');
  const autosaveBadge = document.getElementById('autosaveBadge');
  const timerBadge = document.getElementById('timerBadge');
  const elapsedInput = document.getElementById('elapsedSecondsInput');
  const form = document.getElementById('readingSubmitForm');
  if (!form) return;

  const csrfTokenInput = form.querySelector('input[name="csrf_token"]');
  const csrfToken = csrfTokenInput ? csrfTokenInput.value : '';

  const inputs = Array.from(
    document.querySelectorAll('input.reading-answer-input, textarea.reading-answer-input')
  );

  const readingSurface = document.getElementById('readingSurface');
  const wordSupportCard = document.getElementById('wordSupportCard');
  const wordSupportTitle = document.getElementById('wordSupportTitle');
  const wordSupportEmpty = document.getElementById('wordSupportEmpty');
  const wordSupportLoading = document.getElementById('wordSupportLoading');
  const wordSupportBody = document.getElementById('wordSupportBody');
  const wordSupportError = document.getElementById('wordSupportError');
  const wordSupportMeta = document.getElementById('wordSupportMeta');
  const wordSupportLanguageBadge = document.getElementById('wordSupportLanguageBadge');
  const wordMeaningValue = document.getElementById('wordMeaningValue');
  const wordSynonymValue = document.getElementById('wordSynonymValue');
  const wordTranslationValue = document.getElementById('wordTranslationValue');
  const toggleHelperBtn = document.getElementById('toggleHelperBtn');
  const collapseHelperBtn = document.getElementById('collapseHelperBtn');
  const helperTabs = Array.from(document.querySelectorAll('[data-helper-tab]'));
  const helperPanels = Array.from(document.querySelectorAll('[data-helper-panel]'));

  let activeWordButton = null;
  let autosaveLock = false;
  let typingTimer = null;
  let activeTypingElement = null;

  if (wordSupportLanguageBadge) {
    wordSupportLanguageBadge.textContent = targetLanguageLabel;
  }

  function collectAnswers() {
    const answers = {};
    inputs.forEach((input) => {
      if ((input.type === 'radio' || input.type === 'checkbox') && !input.checked) return;
      const key = (input.name || '').replace('answer_', '');
      answers[key] = input.value || '';
    });
    return answers;
  }

  function updateProgress() {
    const answers = collectAnswers();
    const answered = Object.values(answers).filter((v) => String(v).trim() !== '').length;
    const progress = totalQuestions ? Math.round((answered / totalQuestions) * 100) : 0;

    if (answeredCountEl) answeredCountEl.textContent = answered;
    if (progressBar) progressBar.style.width = progress + '%';

    return { answers, answered, progress };
  }

  function formatTime(total) {
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    return String(mins).padStart(2, '0') + ':' + String(secs).padStart(2, '0');
  }

  function paintTimer() {
    if (!timerBadge || !elapsedInput) return;

    if (timerSeconds > 0) {
      const remaining = Math.max(timerSeconds - elapsedSeconds, 0);
      timerBadge.textContent = formatTime(remaining);
      timerBadge.className = 'badge ' + (remaining <= 60 ? 'text-bg-danger' : 'text-bg-dark');
    } else {
      timerBadge.textContent = formatTime(elapsedSeconds);
    }

    elapsedInput.value = elapsedSeconds;
  }

  async function autosave(force) {
    if (!autosaveUrl) return;
    if (autosaveLock && !force) return;

    autosaveLock = true;
    const snapshot = updateProgress();

    try {
      if (autosaveBadge) {
        autosaveBadge.textContent = 'Saving...';
        autosaveBadge.className = 'badge text-bg-warning';
      }

      const response = await fetch(autosaveUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
          answers: snapshot.answers,
          progress: snapshot.progress,
          elapsed_seconds: elapsedSeconds,
        }),
      });

      if (!response.ok) throw new Error('save_failed');

      if (autosaveBadge) {
        autosaveBadge.textContent = 'Saved';
        autosaveBadge.className = 'badge text-bg-success';
      }
    } catch (error) {
      if (autosaveBadge) {
        autosaveBadge.textContent = 'Save issue';
        autosaveBadge.className = 'badge text-bg-danger';
      }
    } finally {
      autosaveLock = false;
    }
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function extractSentence(sourceText, word) {
    const text = String(sourceText || '').replace(/\s+/g, ' ').trim();
    if (!text || !word) return '';

    const lowerText = text.toLowerCase();
    const lowerWord = String(word).toLowerCase();
    const index = lowerText.indexOf(lowerWord);

    if (index === -1) return text.slice(0, 220);

    const starts = [
      text.lastIndexOf('.', index),
      text.lastIndexOf('?', index),
      text.lastIndexOf('!', index),
    ];

    let start = Math.max.apply(null, starts);
    start = start === -1 ? 0 : start + 1;

    const ends = [
      text.indexOf('.', index),
      text.indexOf('?', index),
      text.indexOf('!', index),
    ].filter((value) => value !== -1);

    const end = ends.length ? Math.min.apply(null, ends) + 1 : text.length;
    return text.slice(start, end).trim();
  }

  function decoratePassageWords() {
    if (!readingSurface) return;

    const rawText = readingSurface.textContent || '';
    const html = rawText.replace(/[A-Za-z][A-Za-z'-]*/g, (word) => {
      return '<span class="reading-word" data-word="' + escapeHtml(word) + '" title="Double-click for vocabulary help">' + escapeHtml(word) + '</span>';
    });

    readingSurface.innerHTML = html;
  }

  function setWordSupportState(state) {
    if (wordSupportEmpty) wordSupportEmpty.classList.toggle('d-none', state !== 'empty');
    if (wordSupportLoading) wordSupportLoading.classList.toggle('d-none', state !== 'loading');
    if (wordSupportBody) wordSupportBody.classList.toggle('d-none', state !== 'ready');
    if (wordSupportError) wordSupportError.classList.toggle('d-none', state !== 'error');
  }

  function openHelper(open) {
    if (!wordSupportCard) return;
    const collapsed = open === false;
    wordSupportCard.classList.toggle('is-collapsed', collapsed);
    if (toggleHelperBtn) {
      toggleHelperBtn.textContent = collapsed ? 'Show Helper' : 'Hide Helper';
      toggleHelperBtn.setAttribute('aria-expanded', String(!collapsed));
    }
    if (collapseHelperBtn) {
      collapseHelperBtn.textContent = collapsed ? 'Expand' : 'Collapse';
      collapseHelperBtn.setAttribute('aria-expanded', String(!collapsed));
    }
  }

  function setHelperTab(name) {
    helperTabs.forEach((tab) => {
      tab.classList.toggle('is-active', tab.dataset.helperTab === name);
    });
    helperPanels.forEach((panel) => {
      panel.classList.toggle('is-visible', panel.dataset.helperPanel === name);
    });
  }

  async function loadWordSupport(word, sourceText, trigger) {
    if (!wordSupportUrl || !word) return;

    openHelper(true);

    if (activeWordButton) activeWordButton.classList.remove('is-active');
    activeWordButton = trigger || null;
    if (activeWordButton) activeWordButton.classList.add('is-active');

    if (wordSupportTitle) wordSupportTitle.textContent = word;
    if (wordSupportError) wordSupportError.textContent = '';

    setWordSupportState('loading');

    try {
      const response = await fetch(wordSupportUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
          word: word,
          sentence: extractSentence(sourceText, word),
        }),
      });

      const payload = await response.json();
      if (!response.ok || !payload.ok) throw new Error(payload.message || 'Word support failed.');

      if (wordMeaningValue) wordMeaningValue.textContent = payload.meaning || 'Not available';
      if (wordSynonymValue) wordSynonymValue.textContent = payload.synonym || 'Not available';
      if (wordTranslationValue) wordTranslationValue.textContent = payload.translation || 'Not available';

      if (wordSupportMeta) {
        const provider = payload.provider_name ? 'Provider: ' + payload.provider_name : 'Vocabulary helper';
        const language = payload.target_language_label ? ' • Target: ' + payload.target_language_label : '';
        wordSupportMeta.textContent = provider + language;
      }

      setHelperTab('meaning');
      setWordSupportState('ready');
      if (wordSupportCard) {
        wordSupportCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    } catch (error) {
      if (wordSupportError) {
        wordSupportError.textContent = error.message || 'Word support failed.';
      }
      setWordSupportState('error');
    }
  }

  decoratePassageWords();
  openHelper(true);

  if (readingSurface) {
    readingSurface.addEventListener('dblclick', (event) => {
      const trigger = event.target.closest('.reading-word');
      if (!trigger) return;
      event.preventDefault();
      loadWordSupport(trigger.dataset.word || '', readingSurface.textContent || '', trigger);
    });
  }

  if (toggleHelperBtn) {
    toggleHelperBtn.addEventListener('click', () => {
      const isCollapsed = wordSupportCard && wordSupportCard.classList.contains('is-collapsed');
      openHelper(isCollapsed);
    });
  }

  if (collapseHelperBtn) {
    collapseHelperBtn.addEventListener('click', () => {
      const isCollapsed = wordSupportCard && wordSupportCard.classList.contains('is-collapsed');
      openHelper(isCollapsed);
    });
  }

  helperTabs.forEach((tab) => {
    tab.addEventListener('click', () => setHelperTab(tab.dataset.helperTab || 'meaning'));
  });

  if (window.innerWidth <= 991) {
    const questionPanel = document.getElementById('questionPanel');
    if (questionPanel) questionPanel.classList.add('mobile-hidden');
  }

  updateProgress();
  paintTimer();

  setInterval(() => {
    elapsedSeconds += 1;
    paintTimer();
  }, 1000);

  setInterval(() => {
    if (activeTypingElement) return;
    autosave(false);
  }, 10000);

  inputs.forEach((input) => {
    input.addEventListener('focus', () => {
      activeTypingElement = input;
    });

    input.addEventListener('blur', () => {
      activeTypingElement = null;
      autosave(false);
    });

    input.addEventListener('input', () => {
      updateProgress();
      clearTimeout(typingTimer);
      typingTimer = setTimeout(() => {
        if (!activeTypingElement) autosave(false);
      }, 1200);
    });

    input.addEventListener('change', () => {
      updateProgress();
      if (!activeTypingElement) autosave(false);
    });
  });

  form.addEventListener('submit', () => {
    if (elapsedInput) elapsedInput.value = elapsedSeconds;
  });

  window.addEventListener('beforeunload', () => {
    if (elapsedInput) elapsedInput.value = elapsedSeconds;
  });

  document.querySelectorAll('[data-view]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const passagePanel = document.getElementById('passagePanel');
      const questionPanel = document.getElementById('questionPanel');

      if (!passagePanel || !questionPanel) return;

      if (btn.dataset.view === 'passage') {
        passagePanel.classList.remove('mobile-hidden');
        questionPanel.classList.add('mobile-hidden');
      } else {
        questionPanel.classList.remove('mobile-hidden');
        passagePanel.classList.add('mobile-hidden');
      }
    });
  });
})();
