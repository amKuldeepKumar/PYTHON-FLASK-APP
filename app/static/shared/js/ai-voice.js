(function () {
  const FluencifyVoice = {
    utterance: null,
    hasAutoPlayed: false,

    root() {
      return document.getElementById("aiVoicePanel");
    },

    getVoiceMode() {
      const root = this.root();
      if (!root) return "once";
      const mode = (root.dataset.voiceMode || "once").toLowerCase();
      return mode === "mute" ? "muted" : mode;
    },

    getAccent() {
      const root = this.root();
      if (!root) return "en-IN";
      return root.dataset.accent || "en-IN";
    },

    getMessage() {
      const root = this.root();
      if (!root) return "";
      return root.dataset.message || "";
    },

    getPreferredVoiceName() {
      const root = this.root();
      if (!root) return "";
      return root.dataset.voiceName || "";
    },

    getVoiceGender() {
      const root = this.root();
      if (!root) return "female";
      return (root.dataset.voiceGender || "female").toLowerCase();
    },

    getVoicePitch() {
      const root = this.root();
      if (!root) return 1;
      const value = Number(root.dataset.voicePitch || "1");
      return Number.isFinite(value) ? value : 1;
    },

    getPlaybackRate() {
      const root = this.root();
      if (!root) return 1;
      const value = Number(root.dataset.playbackRate || "1");
      return Number.isFinite(value) ? value : 1;
    },

    stop() {
      try {
        window.speechSynthesis.cancel();
      } catch (e) {}
    },

    pickVoice(accent, preferredName, gender) {
      const voices = window.speechSynthesis.getVoices() || [];
      if (!voices.length) return null;

      const targetLang = (accent || "en-IN").toLowerCase();
      const langPrefix = targetLang.split("-")[0];
      const preferred = (preferredName || "").trim().toLowerCase();
      const isMale = gender === "male";
      const genderWords = isMale
        ? ["male", "man", "david", "daniel", "alex", "guy", "aaron", "fred"]
        : ["female", "woman", "zira", "susan", "samantha", "karen", "victoria", "heera", "raveena"];

      let candidates = voices.filter(v => (v.lang || "").toLowerCase() === targetLang);
      if (!candidates.length) {
        candidates = voices.filter(v => (v.lang || "").toLowerCase().startsWith(langPrefix));
      }
      if (!candidates.length) candidates = voices.slice();

      if (preferred) {
        const exact = candidates.find(v => (v.name || "").toLowerCase() === preferred);
        if (exact) return exact;
      }

      const genderMatch = candidates.find(v => {
        const name = (v.name || "").toLowerCase();
        return genderWords.some(word => name.includes(word));
      });
      if (genderMatch) return genderMatch;

      const local = candidates.find(v => v.localService);
      return local || candidates[0] || null;
    },

    speak(text, manual = false) {
      if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
        console.warn("Speech synthesis not supported in this browser.");
        return;
      }

      if (!text || !text.trim()) return;

      const mode = this.getVoiceMode();
      if (!manual && mode === "muted") return;

      this.stop();

      const utterance = new SpeechSynthesisUtterance(text);
      const accent = this.getAccent();
      const preferredName = this.getPreferredVoiceName();
      const voiceGender = this.getVoiceGender();

      utterance.lang = accent;
      utterance.rate = this.getPlaybackRate();
      utterance.pitch = this.getVoicePitch();
      utterance.volume = 1;

      const selectedVoice = this.pickVoice(accent, preferredName, voiceGender);
      if (selectedVoice) {
        utterance.voice = selectedVoice;
        if (selectedVoice.lang) utterance.lang = selectedVoice.lang;
      }

      this.utterance = utterance;
      window.speechSynthesis.speak(utterance);
    },

    autoplayOnce() {
      const root = this.root();
      if (!root) return;

      const mode = this.getVoiceMode();
      if (mode === "muted") return;
      if (this.hasAutoPlayed) return;

      const text = this.getMessage();
      if (!text) return;

      this.hasAutoPlayed = true;
      setTimeout(() => {
        this.speak(text, false);
      }, 700);
    },

    async setMode(mode) {
      const root = this.root();
      if (!root) return;

      const normalized = mode === "mute" ? "muted" : mode;
      const saveUrl = root.dataset.saveUrl;
      root.dataset.voiceMode = normalized;

      if (!saveUrl) return;

      try {
        const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content")
          || document.querySelector('input[name="csrf_token"]')?.value
          || "";

        await fetch(saveUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf
          },
          body: JSON.stringify({ welcome_voice_mode: normalized })
        });
      } catch (err) {
        console.error("Failed to save welcome voice mode:", err);
      }
    },

    bind() {
      const replayBtn = document.getElementById("replayWelcomeBtn");
      const onceBtn = document.getElementById("listenOnceBtn");
      const muteBtn = document.getElementById("muteForeverBtn");
      const root = this.root();
      if (!root) return;

      if (replayBtn) {
        replayBtn.addEventListener("click", () => {
          this.speak(this.getMessage(), true);
          const status = document.getElementById("voiceStatusText");
          if (status) status.textContent = "Welcome voice replayed.";
        });
      }

      if (onceBtn) {
        onceBtn.addEventListener("click", async () => {
          await this.setMode("once");
          this.speak(this.getMessage(), true);
          const status = document.getElementById("voiceStatusText");
          if (status) status.textContent = "Welcome voice set to play once.";
        });
      }

      if (muteBtn) {
        muteBtn.addEventListener("click", async () => {
          this.stop();
          await this.setMode("muted");
          const status = document.getElementById("voiceStatusText");
          if (status) status.textContent = "Welcome voice muted for future logins.";
        });
      }

      const firstInteractionPlay = () => {
        const mode = this.getVoiceMode();
        if (mode !== "muted" && !window.__fluencifyVoiceFirstPlayed) {
          window.__fluencifyVoiceFirstPlayed = true;
          this.speak(this.getMessage(), false);
        }
        document.removeEventListener("click", firstInteractionPlay);
      };
      document.addEventListener("click", firstInteractionPlay, { once: true });
    },

    init() {
      this.bind();
      if ("speechSynthesis" in window) {
        if (typeof window.speechSynthesis.onvoiceschanged !== "undefined") {
          window.speechSynthesis.onvoiceschanged = () => {
            window.speechSynthesis.getVoices();
          };
        }
        window.speechSynthesis.getVoices();
      }
      this.autoplayOnce();
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    FluencifyVoice.init();
  });
})();
