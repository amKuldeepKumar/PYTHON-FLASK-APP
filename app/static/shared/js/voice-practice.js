(function () {
  const card = document.getElementById('voicePracticeCard');
  const speakBtn = document.getElementById('speakQuestionBtn');
  const recordBtn = document.getElementById('recordAnswerBtn');
  const questionEl = document.getElementById('questionText');
  const responseText = document.getElementById('responseText');
  const responseMode = document.getElementById('responseMode');
  const durationSeconds = document.getElementById('durationSeconds');
  const statusEl = document.getElementById('voicePracticeStatus');
  const browserSttUsed = document.getElementById('browserSttUsed');

  if (!card || !questionEl || !speakBtn || !recordBtn) return;

  const autoPlayQuestion = card.dataset.autoPlayQuestion === '1';
  const autoStartListening = card.dataset.autoStartListening === '1';
  const beepEnabled = card.dataset.beepEnabled === '1';
  const voiceLang = card.dataset.voiceLang || 'en-IN';
  const playbackRate = Number(card.dataset.playbackRate || '1') || 1;
  const voicePitch = Number(card.dataset.voicePitch || '1') || 1;
  const voiceGender = (card.dataset.voiceGender || 'female').toLowerCase();
  const preferredVoiceName = (card.dataset.voiceName || '').trim().toLowerCase();
  const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;

  let recognition = null;
  let startedAt = null;
  let autoFlowTriggered = false;
  let stopRequested = false;
  let pendingInteractionReplay = false;
  let interactionBound = false;
  let questionPlaybackInProgress = false;
  let questionPlaybackCompleted = false;

  function setStatus(message) {
    if (statusEl) statusEl.textContent = message || '';
  }

  function setRecordButtonLabel(listening) {
    recordBtn.textContent = listening ? 'Stop Speaking' : 'Start Speaking';
  }

  function bindInteractionReplay() {
    if (interactionBound) return;
    interactionBound = true;

    const retryPlayback = function () {
      if (!pendingInteractionReplay) return;
      pendingInteractionReplay = false;
      playQuestionAndMaybeListen(true);
    };

    ['click', 'keydown', 'touchstart'].forEach(function (eventName) {
      document.addEventListener(eventName, retryPlayback, { once: true });
    });
  }


  function pickVoice() {
    if (!('speechSynthesis' in window)) return null;
    const voices = window.speechSynthesis.getVoices() || [];
    if (!voices.length) return null;

    const targetLang = (voiceLang || 'en-IN').toLowerCase();
    const langPrefix = targetLang.split('-')[0];
    const desiredGenderWords = voiceGender === 'male'
      ? ['male', 'man', 'david', 'daniel', 'alex', 'guy', 'aaron', 'fred']
      : ['female', 'woman', 'zira', 'susan', 'samantha', 'karen', 'victoria', 'heera', 'raveena'];

    let candidates = voices.filter(function (voice) {
      return (voice.lang || '').toLowerCase() === targetLang;
    });
    if (!candidates.length) {
      candidates = voices.filter(function (voice) {
        return (voice.lang || '').toLowerCase().startsWith(langPrefix);
      });
    }
    if (!candidates.length) candidates = voices.slice();

    if (preferredVoiceName) {
      const exact = candidates.find(function (voice) {
        return (voice.name || '').toLowerCase() === preferredVoiceName;
      });
      if (exact) return exact;
    }

    const genderHit = candidates.find(function (voice) {
      const name = (voice.name || '').toLowerCase();
      return desiredGenderWords.some(function (word) { return name.includes(word); });
    });
    if (genderHit) return genderHit;

    const localHit = candidates.find(function (voice) { return voice.localService; });
    return localHit || candidates[0] || null;
  }

  function playBeep() {
    return new Promise((resolve) => {
      if (!beepEnabled) {
        resolve();
        return;
      }
      try {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) {
          resolve();
          return;
        }
        const ctx = new Ctx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.value = 880;
        gain.gain.value = 0.0001;
        osc.connect(gain);
        gain.connect(ctx.destination);
        const now = ctx.currentTime;
        gain.gain.exponentialRampToValueAtTime(0.12, now + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.22);
        osc.start(now);
        osc.stop(now + 0.24);
        osc.onended = function () {
          ctx.close().catch(function () {});
          resolve();
        };
      } catch (err) {
        resolve();
      }
    });
  }

  function ensureRecognition() {
    if (!SpeechRecognitionCtor) return null;
    if (recognition) return recognition;
    recognition = new SpeechRecognitionCtor();
    recognition.lang = voiceLang;
    recognition.interimResults = true;
    recognition.continuous = true;
    recognition.onresult = function (event) {
      let full = '';
      for (let i = 0; i < event.results.length; i += 1) {
        full += event.results[i][0].transcript + ' ';
      }
      if (responseText) responseText.value = full.trim();
      if (responseMode) responseMode.value = 'spoken';
      if (browserSttUsed) browserSttUsed.value = '1';
    };
    recognition.onend = function () {
      if (startedAt && durationSeconds) {
        durationSeconds.value = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
      }
      startedAt = null;
      setRecordButtonLabel(false);
      if (stopRequested) {
        setStatus('Speech recording stopped.');
      } else {
        setStatus('Speech recording finished. Review your answer or speak again.');
      }
      stopRequested = false;
    };
    recognition.onerror = function (event) {
      startedAt = null;
      setRecordButtonLabel(false);
      setStatus('Speech recognition error: ' + (event.error || 'unknown'));
    };
    return recognition;
  }

  function startListening(autoTriggered) {
    const engine = ensureRecognition();
    if (!engine) {
      recordBtn.disabled = true;
      recordBtn.textContent = 'Speech not supported';
      setStatus('Speech recognition is not supported in this browser.');
      return;
    }
    if (startedAt) return;
    try {
      stopRequested = false;
      startedAt = Date.now();
      engine.lang = voiceLang;
      if (browserSttUsed) browserSttUsed.value = '1';
      engine.start();
      setRecordButtonLabel(true);
      setStatus(autoTriggered ? 'Listening started automatically after the question.' : 'Listening started. Speak your answer now.');
    } catch (err) {
      startedAt = null;
      setRecordButtonLabel(false);
      setStatus('Could not start speech recognition. Please try again.');
    }
  }

  async function playQuestionAndMaybeListen(manualTrigger) {
    const text = (questionEl.textContent || '').trim();
    if (!text) return;
    if (questionPlaybackInProgress) return;

    if (!('speechSynthesis' in window)) {
      setStatus('Question playback is not supported in this browser. Starting answer capture after the beep.');
      questionPlaybackCompleted = true;
      if (autoStartListening) {
        await playBeep();
        startListening(true);
      }
      return;
    }

    window.speechSynthesis.cancel();
    if (typeof window.speechSynthesis.resume === 'function') {
      try { window.speechSynthesis.resume(); } catch (err) {}
    }
    questionPlaybackInProgress = true;
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = voiceLang;
    utter.rate = playbackRate;
    utter.pitch = voicePitch;
    const selectedVoice = pickVoice();
    if (selectedVoice) {
      utter.voice = selectedVoice;
      if (selectedVoice.lang) utter.lang = selectedVoice.lang;
    }
    utter.onstart = function () {
      questionPlaybackInProgress = true;
      questionPlaybackCompleted = false;
      setStatus('Reading the question...');
    };
    utter.onend = async function () {
      questionPlaybackInProgress = false;
      questionPlaybackCompleted = true;
      setStatus('Question finished.');
      await playBeep();
      if (autoStartListening) {
        startListening(true);
      } else {
        setStatus('Question finished. Press Start Speaking when you are ready.');
      }
    };
    utter.onerror = function () {
      questionPlaybackInProgress = false;
      if (manualTrigger) {
        questionPlaybackCompleted = true;
        setStatus('Question playback failed in this browser. Starting answer capture after the beep.');
        if (autoStartListening) {
          playBeep().then(function () {
            startListening(true);
          });
        }
        return;
      }
      pendingInteractionReplay = true;
      bindInteractionReplay();
      setStatus('Automatic question playback was blocked. Tap anywhere or press Play Question once to continue the guided speaking flow.');
    };
    window.speechSynthesis.speak(utter);
  }

  speakBtn.addEventListener('click', function () {
    playQuestionAndMaybeListen(true);
  });

  if (SpeechRecognitionCtor) {
    recordBtn.addEventListener('click', function () {
      if (!startedAt) {
        if (questionPlaybackInProgress) {
          setStatus('Question is still being read. Listening will start after the beep.');
          return;
        }
        if (!questionPlaybackCompleted) {
          playQuestionAndMaybeListen(true);
          return;
        }
        startListening(false);
      } else {
        stopRequested = true;
        ensureRecognition().stop();
      }
    });
  } else {
    recordBtn.disabled = true;
    recordBtn.textContent = 'Speech not supported';
    setStatus('Speech recognition is not supported in this browser.');
  }

  if ('speechSynthesis' in window) {
    if (typeof window.speechSynthesis.onvoiceschanged !== 'undefined') {
      window.speechSynthesis.onvoiceschanged = function () { pickVoice(); };
    }
    window.speechSynthesis.getVoices();
  }

  window.addEventListener('load', function () {
    if (!autoPlayQuestion || autoFlowTriggered) return;
    autoFlowTriggered = true;
    setTimeout(function () {
      playQuestionAndMaybeListen(false);
    }, 700);
  });
})();
