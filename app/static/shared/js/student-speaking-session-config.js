document.addEventListener("DOMContentLoaded", function () {
  const host = document.getElementById("speakingSessionConfig");
  if (!host) return;
  window.SPEAKING_SESSION_CONFIG = {
    estimatedSeconds: parseInt(host.dataset.estimatedSeconds || "0", 10),
    targetSeconds: parseInt(host.dataset.targetSeconds || "0", 10),
    minSeconds: parseInt(host.dataset.minSeconds || "0", 10),
    maxSeconds: parseInt(host.dataset.maxSeconds || "0", 10),
  };
});
