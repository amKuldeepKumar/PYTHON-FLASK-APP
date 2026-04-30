// Phase 1 placeholder for global JS.
// Later: theme toggles, welcome audio modal triggers, etc.
console.log("Fluencify app loaded");

(function () {
  // ------------------------------------------------------
  // PHASE 7 / PHASE 11
  // Theme bridge:
  // - respects the server-selected active SuperAdmin theme
  // - avoids forcing dark mode from localStorage
  // - keeps optional local toggles opt-in only
  // ------------------------------------------------------
  const root = document.documentElement;
  const serverTheme = root.getAttribute("data-theme");
  if (serverTheme !== "light" && serverTheme !== "dark") {
    root.setAttribute("data-theme", "dark");
  }

  const themeBtn = document.getElementById("themeToggleBtn");
  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      const current = root.getAttribute("data-theme") || "dark";
      const next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);

      // Persist only when explicitly requested by markup.
      if (themeBtn.dataset.persist === "local") {
        localStorage.setItem("theme", next);
      }
    });
  }

  function togglePasswordField(input, icon, button) {
    if (!input) return;
    const show = input.getAttribute("type") === "password";
    input.setAttribute("type", show ? "text" : "password");

    if (icon) {
      icon.classList.remove("bi-eye", "bi-eye-slash");
      icon.classList.add(show ? "bi-eye" : "bi-eye-slash");
    }

    if (button) {
      button.setAttribute("aria-label", show ? "Hide password" : "Show password");
      button.setAttribute("aria-pressed", show ? "true" : "false");
      button.classList.toggle("is-visible", show);
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-password-toggle]");
    if (!button) return;

    const inputSelector = button.getAttribute("data-password-toggle");
    const iconSelector = button.getAttribute("data-password-icon");
    const input = inputSelector ? document.querySelector(inputSelector) : null;
    const icon = iconSelector ? document.querySelector(iconSelector) : button.querySelector("i");

    togglePasswordField(input, icon, button);
  });

  function wireRoleButtons(hiddenInputId) {
    const hidden = document.getElementById(hiddenInputId);
    if (!hidden) return;

    document.querySelectorAll("[data-role]").forEach((btn) => {
      btn.addEventListener("click", () => {
        hidden.value = btn.getAttribute("data-role") || "STUDENT";
        document.querySelectorAll("[data-role]").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
      });
    });
  }

  wireRoleButtons("selectedRole");
  wireRoleButtons("selectedRoleRegister");
})();
