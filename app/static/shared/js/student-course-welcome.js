(function () {
  let audioContext = null;
  let typingTimer = null;

  function speak(message) {
    if (!('speechSynthesis' in window) || !message) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(message);
      utterance.lang = 'en-IN';
      utterance.rate = 0.96;
      utterance.pitch = 1.02;
      const avatar = document.getElementById('courseWelcomeAvatar');
      utterance.onstart = function () {
        avatar?.classList.add('is-speaking');
      };
      utterance.onend = function () {
        avatar?.classList.remove('is-speaking');
      };
      window.speechSynthesis.speak(utterance);
    } catch (err) {
      console.error('Course welcome speech failed', err);
    }
  }

  function playTypeClick() {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    if (!audioContext) audioContext = new AudioCtx();
    const now = audioContext.currentTime;
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    oscillator.type = 'square';
    oscillator.frequency.value = 1800;
    gain.gain.value = 0.012;
    oscillator.connect(gain);
    gain.connect(audioContext.destination);
    oscillator.start(now);
    oscillator.stop(now + 0.025);
  }

  function typeWords(target, text) {
    if (!target) return;
    const words = String(text || '').split(/\s+/).filter(Boolean);
    let index = 0;
    target.textContent = '';
    window.clearTimeout(typingTimer);

    function step() {
      if (index >= words.length) return;
      target.textContent += (index ? ' ' : '') + words[index];
      playTypeClick();
      index += 1;
      target.scrollTop = target.scrollHeight;
      typingTimer = window.setTimeout(step, index < 12 ? 150 : 115);
    }

    step();
  }

  document.addEventListener('DOMContentLoaded', function () {
    const root = document.getElementById('courseWelcomeScreen');
    if (!root) return;

    const message = root.dataset.message || '';
    const typingTarget = document.getElementById('courseWelcomeTyping');
    const replay = document.getElementById('courseWelcomeReplay');

    typeWords(typingTarget, message);
    window.setTimeout(function () {
      speak(message);
    }, 550);

    replay?.addEventListener('click', function () {
      speak(message);
      typeWords(typingTarget, message);
    });
  });
})();
