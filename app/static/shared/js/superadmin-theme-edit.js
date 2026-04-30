document.addEventListener("DOMContentLoaded", function () {
  const host = document.getElementById("themePresetPayload");
  const presets = host ? JSON.parse(host.dataset.presets || "[]") : [];

  function applyPreset(key) {
    const preset = presets.find((item) => item.key === key);
    if (!preset) return;
    Object.entries(preset.values || {}).forEach(([field, value]) => {
      const el = document.querySelector(`[name="${field}"]`);
      if (!el) return;
      if (el.type === "checkbox") {
        el.checked = !!value;
      } else {
        el.value = value;
      }
    });
  }

  window.applyPreset = applyPreset;
});
