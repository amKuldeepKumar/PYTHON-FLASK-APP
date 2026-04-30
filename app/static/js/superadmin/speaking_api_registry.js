/* =========================================================
   Speaking API Registry
   Loads selected provider row into the editor form
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector("#provider-editor-form");
  if (!form) return;

  function findField(name) {
    return (
      form.querySelector(`[name="provider-${name}"]`) ||
      form.querySelector(`[name="${name}"]`)
    );
  }

  function setValue(name, value) {
    const field = findField(name);
    if (field) field.value = value || "";
  }

  function setChecked(name, value) {
    const field = findField(name);
    if (field) field.checked = String(value) === "1";
  }

  document.querySelectorAll(".js-load-provider").forEach(function (button) {
    button.addEventListener("click", function () {
      setValue("provider_id", button.dataset.providerId);
      setValue("provider_kind", button.dataset.providerKind);
      setValue("name", button.dataset.name);
      setValue("provider_type", button.dataset.providerType);
      setValue("official_website", button.dataset.officialWebsite);
      setValue("api_base_url", button.dataset.apiBaseUrl);
      setValue("model_name", button.dataset.modelName);
      setValue("usage_scope", button.dataset.usageScope);
      setValue("pricing_note", button.dataset.pricingNote);
      setValue("notes", button.dataset.notes);
      setValue("fallback_provider_id", button.dataset.fallbackProviderId);
      setValue("config_json", button.dataset.configJson);

      setChecked("is_enabled", button.dataset.isEnabled);
      setChecked("supports_test", button.dataset.supportsTest);

      window.scrollTo({
        top: form.getBoundingClientRect().top + window.pageYOffset - 100,
        behavior: "smooth"
      });
    });
  });
});
