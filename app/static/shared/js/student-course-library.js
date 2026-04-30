document.addEventListener("DOMContentLoaded", function () {
  const loadingOverlay = document.querySelector(".library-loading");
  const filterForm = document.querySelector(".js-library-filter-form");

  function showLoading() {
    if (!loadingOverlay) return;
    loadingOverlay.hidden = false;
    loadingOverlay.setAttribute("aria-hidden", "false");
  }

  document.querySelectorAll(".js-confirm-action-form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      const titleInput = form.querySelector('input[name="card_title"]');
      const title = titleInput ? titleInput.value : "this course";
      if (!window.confirm(`Do you want to enroll in "${title}"?`)) {
        event.preventDefault();
        return;
      }
      showLoading();
    });
  });

  document.querySelectorAll(".js-confirm-action").forEach(function (link) {
    link.addEventListener("click", function (event) {
      const title = link.getAttribute("data-confirm-title") || "this course";
      const message = link.getAttribute("data-confirm-message") || "Do you want to continue with";
      if (!window.confirm(`${message} "${title}"?`)) {
        event.preventDefault();
        return;
      }
      showLoading();
    });
  });

  document.querySelectorAll("a.btn, .course-library-card__footer a").forEach(function (link) {
    link.addEventListener("click", function () {
      const href = link.getAttribute("href") || "";
      if (href.startsWith("#") || link.classList.contains("js-confirm-action")) {
        return;
      }
      showLoading();
    });
  });

  if (filterForm) {
    filterForm.addEventListener("submit", function () {
      showLoading();
    });
  }

  window.addEventListener("pageshow", function () {
    if (!loadingOverlay) return;
    loadingOverlay.hidden = true;
    loadingOverlay.setAttribute("aria-hidden", "true");
  });
});
