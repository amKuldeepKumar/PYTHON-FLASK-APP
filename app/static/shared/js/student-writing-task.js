(function () {
  const input = document.getElementById('submission_text');
  const form = document.getElementById('writingTaskForm');
  if (!input || !form) return;

  const wordCount = document.getElementById('wordCount');
  const charCount = document.getElementById('charCount');
  const paragraphCount = document.getElementById('paragraphCount');
  const lengthStatus = document.getElementById('lengthStatus');
  const lengthHint = document.getElementById('lengthHint');
  const integrityHint = document.getElementById('integrityHint');
  const submitBtn = document.getElementById('writingSubmitBtn');
  const pasteCountInput = document.getElementById('pasteCount');
  const largestPasteInput = document.getElementById('largestPasteChars');
  const focusLossInput = document.getElementById('focusLossCount');
  const draftSecondsInput = document.getElementById('draftSeconds');
  const minWords = parseInt(input.dataset.minWords || '0', 10) || 0;
  const maxWords = parseInt(input.dataset.maxWords || '0', 10) || 0;
  const storageKey = `writing-draft:${input.dataset.courseId || '0'}:${input.dataset.taskId || '0'}`;

  let pasteCount = 0;
  let largestPasteChars = 0;
  let focusLossCount = 0;
  let draftSeconds = 0;

  function getWords(value) {
    return (value.match(/\b[\w'-]+\b/g) || []).length;
  }

  function getParagraphs(value) {
    return value.split(/\n+/).map((p) => p.trim()).filter(Boolean).length;
  }

  function saveDraft() {
    try {
      window.localStorage.setItem(storageKey, input.value || '');
    } catch (e) {}
  }

  function restoreDraft() {
    try {
      const saved = window.localStorage.getItem(storageKey);
      if (saved && !input.value.trim()) input.value = saved;
    } catch (e) {}
  }

  function updateHiddenFields() {
    if (pasteCountInput) pasteCountInput.value = String(pasteCount);
    if (largestPasteInput) largestPasteInput.value = String(largestPasteChars);
    if (focusLossInput) focusLossInput.value = String(focusLossCount);
    if (draftSecondsInput) draftSecondsInput.value = String(draftSeconds);
  }

  function updateCounts() {
    const value = input.value || '';
    const words = getWords(value.trim());
    const paragraphs = getParagraphs(value);

    if (wordCount) wordCount.textContent = words;
    if (charCount) charCount.textContent = value.trim().length;
    if (paragraphCount) paragraphCount.textContent = paragraphs;

    if (!lengthStatus || !lengthHint) return;

    if (minWords > 0 && words < minWords) {
      lengthStatus.textContent = 'Below target';
      const remaining = minWords - words;
      lengthHint.textContent = `Write ${remaining} more word${remaining === 1 ? '' : 's'} to reach the minimum target.`;
      return;
    }

    if (maxWords > 0 && words > maxWords) {
      const overflow = words - maxWords;
      lengthStatus.textContent = 'Above limit';
      lengthHint.textContent = `You are ${overflow} word${overflow === 1 ? '' : 's'} above the maximum limit.`;
      return;
    }

    if (minWords > 0 || maxWords > 0) {
      lengthStatus.textContent = 'Within target';
      if (minWords > 0 && maxWords > 0) {
        lengthHint.textContent = `Great. Your answer is inside the ${minWords}-${maxWords} word target range.`;
      } else if (minWords > 0) {
        lengthHint.textContent = `Great. You have reached the minimum target of ${minWords} words.`;
      } else {
        lengthHint.textContent = `Great. You are within the maximum limit of ${maxWords} words.`;
      }
      return;
    }

    lengthStatus.textContent = 'Ready';
    lengthHint.textContent = 'Write clearly according to the topic requirement, then submit for evaluation.';
  }

  restoreDraft();
  updateCounts();
  updateHiddenFields();

  input.addEventListener('input', () => {
    saveDraft();
    updateCounts();
  });

  input.addEventListener('paste', (event) => {
    const pasted = (event.clipboardData || window.clipboardData)?.getData('text') || '';
    pasteCount += 1;
    largestPasteChars = Math.max(largestPasteChars, pasted.length);
    updateHiddenFields();
    if (integrityHint) {
      integrityHint.textContent = pasted.length > 120
        ? 'Large pasted text detected. The submission will still be checked, but it may be flagged for review.'
        : 'Paste detected. Review the final answer carefully before submitting.';
    }
  });

  window.addEventListener('blur', () => {
    focusLossCount += 1;
    updateHiddenFields();
  });

  window.setInterval(() => {
    draftSeconds += 1;
    updateHiddenFields();
  }, 1000);

  form.addEventListener('submit', () => {
    updateHiddenFields();
    saveDraft();
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Evaluating...';
    }
  });
})();
