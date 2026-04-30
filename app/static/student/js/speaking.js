(function () {
  const timerEl = document.getElementById('sessionTimer');
  const startBtn = document.getElementById('startBtn');
  const stopBtn = document.getElementById('stopBtn');
  const resetBtn = document.getElementById('resetBtn');
  const submitBtn = document.getElementById('submitBtn');
  const durationInput = document.getElementById('durationSecondsInput');
  const micDot = document.getElementById('micDot');
  const micStatus = document.getElementById('micStatus');
  const micStatusPill = document.getElementById('micStatusPill');
  const transcriptText = document.getElementById('transcriptText');
  const transcriptWordCount = document.getElementById('transcriptWordCount');
  const transcriptCharCount = document.getElementById('transcriptCharCount');
  const speechBtn = document.getElementById('speechToTextBtn');
  const speechStatus = document.getElementById('speechToTextStatus');
  const clearTranscriptBtn = document.getElementById('clearTranscriptBtn');
  const audioFileInput = document.getElementById('audioFileInput');
  const browserSttUsed = document.getElementById('browserSttUsed');
  const form = document.getElementById('speakingSubmitForm');
  const listeningBanner = document.getElementById('listeningBanner');
  const stopReviewPanel = document.getElementById('stopReviewPanel');
  const reviewTranscriptPreview = document.getElementById('reviewTranscriptPreview');
  const reviewMeta = document.getElementById('reviewMeta');
  const submitNowBtn = document.getElementById('submitNowBtn');
  const keepEditingBtn = document.getElementById('keepEditingBtn');
  const autoSubmitToggle = document.getElementById('autoSubmitToggle');
  const timingGuideText = document.getElementById('timingGuideText');
  const config = window.SPEAKING_SESSION_CONFIG || {};
  const sessionConfigRoot = document.getElementById('speakingSessionConfig');
  const sessionStorageKey = sessionConfigRoot?.dataset.sessionKey || `speaking-session-${window.location.pathname}`;

  if (!timerEl || !startBtn || !stopBtn || !resetBtn || !durationInput) return;

  let elapsedSeconds = 0;
  let timerId = null;
  let mediaStream = null;
  let running = false;
  let recognition = null;
  let isRecognizing = false;
  let recorder = null;
  let recorderChunks = [];
  let finalTranscript = transcriptText ? (transcriptText.value || '').trim() : '';
  const targetSeconds = Number(config.targetSeconds || config.estimatedSeconds || 60);
  const minSeconds = Number(config.minSeconds || Math.max(10, Math.round(targetSeconds * 0.5)));
  const maxSeconds = Number(config.maxSeconds || Math.max(targetSeconds, Math.round(targetSeconds * 1.5)));


  function saveDraftState() {
    if (!window.sessionStorage) return;
    const payload = {
      elapsedSeconds,
      transcriptText: transcriptText ? transcriptText.value : '',
      browserSttUsed: browserSttUsed ? browserSttUsed.value : '0',
      autoSubmit: autoSubmitToggle ? !!autoSubmitToggle.checked : false,
    };
    try {
      window.sessionStorage.setItem(sessionStorageKey, JSON.stringify(payload));
    } catch (error) {}
  }

  function restoreDraftState() {
    if (!window.sessionStorage) return;
    try {
      const raw = window.sessionStorage.getItem(sessionStorageKey);
      if (!raw) return;
      const payload = JSON.parse(raw);
      elapsedSeconds = Number(payload.elapsedSeconds || 0);
      if (transcriptText && payload.transcriptText && !transcriptText.value.trim()) {
        transcriptText.value = payload.transcriptText;
        finalTranscript = payload.transcriptText.trim();
      }
      if (browserSttUsed && payload.browserSttUsed) browserSttUsed.value = payload.browserSttUsed;
      if (autoSubmitToggle) autoSubmitToggle.checked = !!payload.autoSubmit;
    } catch (error) {}
  }

  function clearDraftState() {
    if (!window.sessionStorage) return;
    try {
      window.sessionStorage.removeItem(sessionStorageKey);
    } catch (error) {}
  }

  function formatTime(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }

  function render() {
    timerEl.textContent = formatTime(elapsedSeconds);
    durationInput.value = String(elapsedSeconds);
    updateTimingGuide();
    saveDraftState();
  }


  function updateTimingGuide() {
    if (!timingGuideText) return;
    let text = `Aim for ${targetSeconds} seconds. Minimum ${minSeconds} seconds, maximum ${maxSeconds} seconds.`;
    if (elapsedSeconds < minSeconds) {
      text = `Keep going — minimum ${minSeconds} sec required. ${Math.max(0, minSeconds - elapsedSeconds)} sec left to unlock submit.`;
    } else if (elapsedSeconds < targetSeconds) {
      text = `Good pace. Target time is ${targetSeconds} sec. ${Math.max(0, targetSeconds - elapsedSeconds)} sec left to hit target.`;
    } else if (elapsedSeconds <= maxSeconds) {
      text = `Target reached. You can stop and submit now, or continue until ${maxSeconds} sec max.`;
    } else {
      text = `Maximum time reached.`;
    }
    timingGuideText.textContent = text;
  }

  function renderTranscriptStats() {
    if (!transcriptText) return;
    const text = transcriptText.value.trim();
    const words = text ? text.split(/\\s+/).filter(Boolean).length : 0;
    const chars = text.length;
    if (transcriptWordCount) transcriptWordCount.textContent = `${words} words`;
    if (transcriptCharCount) transcriptCharCount.textContent = `${chars} chars`;
  }

  function setMicState(label, state) {
    if (micStatus) micStatus.textContent = label;
    if (micDot) micDot.classList.toggle('live', state === 'live');
    if (micStatusPill) {
      micStatusPill.classList.remove('ready', 'live', 'stopped');
      micStatusPill.classList.add(state || 'ready');
    }
    if (listeningBanner) listeningBanner.classList.toggle('show', state === 'live');
  }

  function setSpeechStatus(message) {
    if (speechStatus) speechStatus.textContent = message;
  }

  function syncTranscriptFromEditor() {
    if (!transcriptText) return;
    finalTranscript = transcriptText.value.trim();
    renderTranscriptStats();
    saveDraftState();
  }

  function hideStopReview() {
    if (stopReviewPanel) stopReviewPanel.classList.remove('show');
  }

  function showStopReview() {
    if (!stopReviewPanel) return;
    const transcriptValue = transcriptText ? transcriptText.value.trim() : '';
    const wordCount = transcriptValue ? transcriptValue.split(/\s+/).filter(Boolean).length : 0;
    const hasAudio = !!(audioFileInput && audioFileInput.files && audioFileInput.files.length);
    if (!transcriptValue && !hasAudio) {
      stopReviewPanel.classList.remove('show');
      return;
    }
    if (reviewTranscriptPreview) {
      reviewTranscriptPreview.textContent = transcriptValue || 'Audio captured. Submit now to transcribe and score your answer.';
    }
    if (reviewMeta) {
      reviewMeta.textContent = `${wordCount} words • ${Number(durationInput.value || 0)} sec`;
    }
    stopReviewPanel.classList.add('show');
  }

  function submitFormNow() {
    if (!form) return;
    form.requestSubmit ? form.requestSubmit() : form.submit();
  }

  async function requestMicrophone() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setMicState('Browser mode', 'ready');
      setSpeechStatus('Mic access is not supported in this browser.');
      return null;
    }
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (window.MediaRecorder) {
        recorderChunks = [];
        recorder = new MediaRecorder(mediaStream);
        recorder.ondataavailable = function (event) {
          if (event.data && event.data.size > 0) recorderChunks.push(event.data);
        };
        recorder.onstop = function () {
          if (!audioFileInput || !recorderChunks.length || typeof DataTransfer === 'undefined') return;
          const blob = new Blob(recorderChunks, { type: recorder.mimeType || 'audio/webm' });
          const ext = blob.type.includes('ogg') ? 'ogg' : blob.type.includes('mp4') ? 'mp4' : 'webm';
          const file = new File([blob], `speaking-session.${ext}`, { type: blob.type || 'audio/webm' });
          const dt = new DataTransfer();
          dt.items.add(file);
          audioFileInput.files = dt.files;
        };
      }
      setMicState('Listening…', 'live');
      return mediaStream;
    } catch (error) {
      setMicState('Permission blocked', 'stopped');
      setSpeechStatus('Mic permission was blocked.');
      return null;
    }
  }

  function buildRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return null;
    const instance = new SR();
    instance.continuous = true;
    instance.interimResults = true;
    instance.lang = 'en-US';

    instance.onstart = function () {
      isRecognizing = true;
      if (speechBtn) speechBtn.textContent = 'Stop Voice to Text';
      setMicState('Listening…', 'live');
      setSpeechStatus('Listening and filling transcript...');
      if (browserSttUsed) browserSttUsed.value = '1';
    };

    instance.onerror = function (event) {
      const errorCode = event && event.error ? event.error : 'unknown error';
      setSpeechStatus(`Speech recognition issue: ${errorCode}`);
    };

    instance.onend = function () {
      isRecognizing = false;
      if (speechBtn) speechBtn.textContent = 'Start Voice to Text';
      if (running) {
        setSpeechStatus('Mic stopped. Review transcript before submitting.');
      }
    };

    instance.onresult = function (event) {
      let latestFinal = finalTranscript;
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const segment = (event.results[i][0] && event.results[i][0].transcript) || '';
        if (event.results[i].isFinal) {
          latestFinal = `${latestFinal} ${segment}`.trim();
        } else {
          interim += `${segment} `;
        }
      }
      finalTranscript = latestFinal.trim();
      if (transcriptText) {
        transcriptText.value = `${finalTranscript} ${interim}`.trim();
      }
      renderTranscriptStats();
    };

    return instance;
  }

  async function startTimer() {
    if (running) return;
    running = true;
    startBtn.disabled = true;
    stopBtn.disabled = false;
    if (submitBtn) submitBtn.disabled = false;

    await requestMicrophone();
    if (recorder && recorder.state === 'inactive') recorder.start();
    if (!recognition) recognition = buildRecognition();
    if (recognition && !isRecognizing) {
      try {
        recognition.start();
      } catch (error) {
        setSpeechStatus('Could not start browser speech-to-text. You can still record and submit audio.');
      }
    }

    timerId = window.setInterval(() => {
      elapsedSeconds += 1;
      render();
      if (elapsedSeconds >= maxSeconds) {
        setSpeechStatus(`Maximum time of ${maxSeconds} seconds reached. Stopping automatically.`);
        stopTimer();
      }
    }, 1000);
  }

  function stopTimer() {
    if (!running) return;
    running = false;
    startBtn.disabled = false;
    stopBtn.disabled = true;
    window.clearInterval(timerId);
    timerId = null;

    if (recognition && isRecognizing) {
      try {
        recognition.stop();
      } catch (error) {}
    }
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
    }

    syncTranscriptFromEditor();
    if (autoSubmitToggle && autoSubmitToggle.checked) {
      setMicState('Submitting…', 'stopped');
      setSpeechStatus('Stopped. Submitting your answer now...');
      window.setTimeout(submitFormNow, 250);
      return;
    }
    setMicState('Stopped', 'stopped');
    setSpeechStatus('Stopped. Review transcript before submitting.');
    showStopReview();
  }

  function resetTimer() {
    stopTimer();
    elapsedSeconds = 0;
    render();
    if (transcriptText) transcriptText.value = '';
    finalTranscript = '';
    if (audioFileInput) audioFileInput.value = '';
    if (browserSttUsed) browserSttUsed.value = '0';
    if (submitBtn) submitBtn.disabled = false;
    renderTranscriptStats();
    clearDraftState();
    setMicState('Ready', 'ready');
    setSpeechStatus('Session reset. Timer, transcript, and audio cleared.');
    hideStopReview();
    if (reviewTranscriptPreview) reviewTranscriptPreview.textContent = 'Your transcript will appear here after you stop.';
    if (reviewMeta) reviewMeta.textContent = '0 words • 0 sec';
  }

  startBtn.addEventListener('click', startTimer);
  stopBtn.addEventListener('click', stopTimer);
  resetBtn.addEventListener('click', resetTimer);

  if (speechBtn) {
    speechBtn.addEventListener('click', async function () {
      if (isRecognizing || running) {
        stopTimer();
        return;
      }
      await startTimer();
    });
  }

  if (clearTranscriptBtn && transcriptText) {
    clearTranscriptBtn.addEventListener('click', function () {
      transcriptText.value = '';
      finalTranscript = '';
      if (browserSttUsed) browserSttUsed.value = '0';
      renderTranscriptStats();
      setSpeechStatus('Transcript cleared.');
      hideStopReview();
    });
  }

  if (transcriptText) {
    transcriptText.addEventListener('input', function () {
      syncTranscriptFromEditor();
      hideStopReview();
    });
  }

  if (submitNowBtn) {
    submitNowBtn.addEventListener('click', function () {
      syncTranscriptFromEditor();
      submitFormNow();
    });
  }

  if (keepEditingBtn) {
    keepEditingBtn.addEventListener('click', function () {
      hideStopReview();
      if (transcriptText) transcriptText.focus();
      setSpeechStatus('You can edit the transcript and submit when ready.');
    });
  }

  if (form) {
    form.addEventListener('submit', function (event) {
      syncTranscriptFromEditor();
      const transcriptValue = transcriptText ? transcriptText.value.trim() : '';
      const wordCount = transcriptValue ? transcriptValue.split(/\s+/).filter(Boolean).length : 0;
      const hasAudio = !!(audioFileInput && audioFileInput.files && audioFileInput.files.length);

      if (!transcriptValue && !hasAudio) {
        event.preventDefault();
        window.alert('Speak, type, or attach audio before submitting.');
        return;
      }

      if (wordCount > 0 && wordCount < 3 && !hasAudio) {
        event.preventDefault();
        window.alert('Speak or type at least 3 words, or attach audio before submitting.');
        return;
      }

      const effectiveSeconds = Number(durationInput.value || 0);
      if (effectiveSeconds < minSeconds) {
        event.preventDefault();
        window.alert(`Please speak for at least ${minSeconds} seconds before submitting.`);
        return;
      }
      if (effectiveSeconds > maxSeconds) {
        event.preventDefault();
        window.alert(`This prompt allows up to ${maxSeconds} seconds only.`);
        return;
      }

      if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Submitting...'; }
      clearDraftState();
    });
  }

  restoreDraftState();
  render();
  renderTranscriptStats();
  updateTimingGuide();
  setMicState('Ready', 'ready');
  setSpeechStatus(window.SpeechRecognition || window.webkitSpeechRecognition ? 'Browser STT ready. Best in Chrome.' : 'Browser STT not supported. Type transcript or upload audio.');
})();
