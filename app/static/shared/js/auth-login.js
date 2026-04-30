document.addEventListener("DOMContentLoaded", function () {
  const host = document.getElementById("authLoginPayload");
  if (!host) return;
  try {
    window.AI_VOICE_PAYLOAD = JSON.parse(host.dataset.aiVoicePayload || "{}");
  } catch (_error) {
    window.AI_VOICE_PAYLOAD = {};
  }
});
