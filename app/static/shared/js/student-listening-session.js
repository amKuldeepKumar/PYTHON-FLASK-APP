(() => {
  const root = document.getElementById('listeningSessionConfig');
  if (!root) return;

  const audio = document.getElementById('listeningAudio');
  const playBtn = document.getElementById('playBtn');
  const pauseBtn = document.getElementById('pauseBtn');
  const resumeBtn = document.getElementById('resumeBtn');
  const restartBtn = document.getElementById('restartBtn');
  const rateSelect = document.getElementById('rateSelect');
  const captionToggleBtn = document.getElementById('captionToggleBtn');
  const captionState = document.getElementById('captionState');
  const scriptCard = document.getElementById('scriptCard');
  const audioStatus = document.getElementById('audioStatus');
  const audioModeBadge = document.getElementById('audioModeBadge');
  const audioHelpText = document.getElementById('audioHelpText');
  const timerValue = document.getElementById('timerValue');
  const replayRemainingValue = document.getElementById('replayRemainingValue');
  const form = document.getElementById('listeningSubmitForm');
  const timeSpentInput = document.getElementById('listeningTimeSpent');
  const replayCountInput = document.getElementById('listeningReplayCount');
  const playCountInput = document.getElementById('listeningPlayCount');
  const startedAudioInput = document.getElementById('listeningStartedAudio');

  const replayLimit = parseInt(root.dataset.replayLimit || '2', 10);
  const estimatedSeconds = parseInt(root.dataset.estimatedSeconds || '60', 10);
  const captionLocked = (root.dataset.captionLocked || '0') === '1';
  const scriptText = (root.dataset.scriptText || '').trim();
  let captionVisible = (root.dataset.captionDefault || 'off') === 'on';
  let playCount = 0;
  let replayCount = 0;
  let timeSpent = 0;
  let timerHandle = null;
  let speechMode = false;
  let speechPaused = false;
  let currentUtterance = null;

  const updateMetrics = () => {
    if (timeSpentInput) timeSpentInput.value = String(timeSpent);
    if (replayCountInput) replayCountInput.value = String(replayCount);
    if (playCountInput) playCountInput.value = String(playCount);
    if (startedAudioInput) startedAudioInput.value = playCount > 0 ? '1' : '0';
    if (timerValue) timerValue.textContent = String(Math.max(0, estimatedSeconds - timeSpent));
    if (replayRemainingValue) replayRemainingValue.textContent = String(Math.max(0, replayLimit - replayCount));
  };

  const setCaptionState = () => {
    if (!scriptCard || !captionState || !captionToggleBtn) return;
    scriptCard.classList.toggle('is-captions-hidden', !captionVisible);
    captionState.textContent = captionVisible ? 'Captions visible' : 'Captions hidden';
    captionToggleBtn.textContent = captionVisible ? 'Hide Captions' : 'Show Captions';
    captionToggleBtn.disabled = captionLocked;
  };

  const startTimer = () => {
    if (timerHandle) return;
    timerHandle = window.setInterval(() => {
      timeSpent += 1;
      updateMetrics();
    }, 1000);
  };

  const stopTimer = () => {
    if (!timerHandle) return;
    window.clearInterval(timerHandle);
    timerHandle = null;
  };

  const setStatus = (value, help = '') => {
    if (audioStatus) audioStatus.textContent = value;
    if (audioHelpText && help) audioHelpText.textContent = help;
  };

  const setMode = (value) => {
    speechMode = value === 'device';
    if (!audioModeBadge) return;
    if (value === 'device') audioModeBadge.textContent = 'Device voice fallback';
    else if (value === 'backend') audioModeBadge.textContent = 'Backend audio';
    else audioModeBadge.textContent = 'Audio unavailable';
  };

  const applyRate = (utterance = null) => {
    const rate = parseFloat(rateSelect?.value || '1');
    const normalized = Number.isFinite(rate) ? rate : 1;
    if (audio && !speechMode) audio.playbackRate = normalized;
    if (utterance) utterance.rate = Math.max(0.7, Math.min(1.2, normalized));
  };

  const stopSpeech = () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    currentUtterance = null;
    speechPaused = false;
    stopTimer();
  };

  const playSpeech = () => {
    if (!scriptText || !('speechSynthesis' in window)) {
      setMode('none');
      setStatus('Audio unavailable', 'Server audio is missing and device speech is not available.');
      return;
    }
    stopSpeech();
    currentUtterance = new SpeechSynthesisUtterance(scriptText);
    applyRate(currentUtterance);
    currentUtterance.onstart = () => { startTimer(); setMode('device'); setStatus('Playing', 'Playing with device voice fallback.'); };
    currentUtterance.onend = () => { stopTimer(); setStatus('Completed', 'Listening completed. You can replay if attempts are left.'); };
    currentUtterance.onerror = () => { stopTimer(); setStatus('Playback failed', 'Device speech could not start.'); };
    window.speechSynthesis.speak(currentUtterance);
  };

  const playAudio = async (isReplay = false) => {
    if (isReplay && replayCount >= replayLimit) {
      setStatus('Replay limit reached', 'No more replays are available on this screen.');
      if (restartBtn) restartBtn.disabled = true;
      return;
    }
    if (isReplay) replayCount += 1;
    playCount += 1;
    updateMetrics();

    if (speechMode || !audio) {
      playSpeech();
      if (restartBtn && replayCount >= replayLimit) restartBtn.disabled = true;
      return;
    }

    try {
      if (isReplay) audio.currentTime = 0;
      applyRate();
      await audio.play();
      setMode('backend');
      setStatus('Playing', 'Listening audio is playing from the server.');
      if (restartBtn && replayCount >= replayLimit) restartBtn.disabled = true;
    } catch (err) {
      setStatus('Server audio failed', 'Switching to device voice fallback.');
      playSpeech();
      if (restartBtn && replayCount >= replayLimit) restartBtn.disabled = true;
    }
  };

  if (audio) {
    audio.addEventListener('play', () => { startTimer(); setMode('backend'); setStatus('Playing', 'Listening audio is playing from the server.'); });
    audio.addEventListener('pause', () => { if (!audio.ended) { stopTimer(); setStatus('Paused', 'Use Resume to continue.'); } });
    audio.addEventListener('ended', () => { stopTimer(); setStatus('Completed', 'Listening completed. You can replay if attempts are left.'); });
    audio.addEventListener('error', () => {
      setMode('device');
      setStatus('Server audio missing', scriptText ? 'Backend audio could not load. Device voice fallback is ready.' : 'No playable audio was generated for this lesson.');
    });
  } else if (scriptText) {
    setMode('device');
    setStatus('Fallback ready', 'Backend audio is missing, but device speech can still play the script.');
  } else {
    setMode('none');
    [playBtn, pauseBtn, resumeBtn, restartBtn, rateSelect].forEach((node) => { if (node) node.disabled = true; });
    setStatus('Audio unavailable', 'No audio source is available for this lesson yet.');
  }

  if (playBtn) playBtn.addEventListener('click', () => playAudio(false));

  if (pauseBtn) pauseBtn.addEventListener('click', () => {
    if (speechMode) {
      if ('speechSynthesis' in window) {
        window.speechSynthesis.pause();
        speechPaused = true;
        stopTimer();
        setStatus('Paused', 'Device voice paused. Use Resume to continue.');
      }
      return;
    }
    if (audio) audio.pause();
  });

  if (resumeBtn) resumeBtn.addEventListener('click', async () => {
    if (speechMode) {
      if ('speechSynthesis' in window && speechPaused) {
        window.speechSynthesis.resume();
        speechPaused = false;
        startTimer();
        setStatus('Playing', 'Resumed device voice playback.');
      } else {
        playSpeech();
      }
      return;
    }
    try {
      if (audio) await audio.play();
    } catch (err) {
      setStatus('Resume blocked', 'Could not resume server audio.');
    }
  });

  if (restartBtn) restartBtn.addEventListener('click', () => playAudio(true));
  if (rateSelect) rateSelect.addEventListener('change', () => applyRate(currentUtterance));

  if (captionToggleBtn) captionToggleBtn.addEventListener('click', () => {
    if (captionLocked) return;
    captionVisible = !captionVisible;
    setCaptionState();
  });

  if (form) form.addEventListener('submit', (event) => {
    updateMetrics();
    if (playCount === 0) {
      event.preventDefault();
      setStatus('Play the audio first', 'The student must play the listening at least once before submitting.');
      window.alert('Please play the listening audio at least once before submitting.');
    }
  });

  updateMetrics();
  setCaptionState();
})();
