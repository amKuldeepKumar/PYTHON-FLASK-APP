(function () {
  const API_URL = "/api/browser-notification";
  const PERMISSION_KEY = "fluencify_browser_notification_prompted";

  function canUseNotifications() {
    return ("Notification" in window);
  }

  function canUseServiceWorker() {
    return ("serviceWorker" in navigator);
  }

  async function registerServiceWorker() {
    if (!canUseServiceWorker()) return null;
    try {
      return await navigator.serviceWorker.register("/service-worker.js", { scope: "/" });
    } catch (err) {
      console.warn("Service worker registration failed", err);
      return null;
    }
  }

  function ensureEnableToast() {
    if (!canUseNotifications()) return;
    if (Notification.permission !== "default") return;
    if (localStorage.getItem(PERMISSION_KEY) === "dismissed") return;
    if (document.getElementById("notifyPermissionToast")) return;

    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <div id="notifyPermissionToast" style="position:fixed;right:16px;bottom:16px;z-index:1080;max-width:360px;">
        <div class="card shadow-lg border-0">
          <div class="card-body p-3">
            <div class="d-flex align-items-start gap-3">
              <div style="font-size:1.25rem;line-height:1;">🔔</div>
              <div class="flex-grow-1">
                <div class="fw-semibold mb-1">Enable study notifications</div>
                <div class="small text-muted mb-3">Get lesson progress updates and study-hour reminders in your browser.</div>
                <div class="d-flex gap-2">
                  <button type="button" class="btn btn-primary btn-sm" id="enableNotifyBtn">Enable</button>
                  <button type="button" class="btn btn-outline-secondary btn-sm" id="dismissNotifyBtn">Later</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>`;
    document.body.appendChild(wrap.firstElementChild);

    document.getElementById("enableNotifyBtn")?.addEventListener("click", async function () {
      await requestPermission();
      document.getElementById("notifyPermissionToast")?.remove();
    });

    document.getElementById("dismissNotifyBtn")?.addEventListener("click", function () {
      localStorage.setItem(PERMISSION_KEY, "dismissed");
      document.getElementById("notifyPermissionToast")?.remove();
    });
  }

  async function requestPermission() {
    if (!canUseNotifications()) return "denied";
    try {
      const permission = await Notification.requestPermission();
      if (permission === "granted") {
        localStorage.removeItem(PERMISSION_KEY);
        await registerServiceWorker();
      }
      return permission;
    } catch (err) {
      console.warn("Notification permission failed", err);
      return "denied";
    }
  }

  function shouldThrottle(cacheKey, minutes) {
    const storageKey = `fluencify_browser_notification_last_${cacheKey}`;
    const raw = localStorage.getItem(storageKey);
    if (!raw) return false;
    const then = Number(raw);
    if (!Number.isFinite(then)) return false;
    const diffMs = Date.now() - then;
    return diffMs < ((minutes || 120) * 60 * 1000);
  }

  function markShown(cacheKey) {
    localStorage.setItem(`fluencify_browser_notification_last_${cacheKey}`, String(Date.now()));
  }

  async function fetchPayload() {
    try {
      const res = await fetch(API_URL, { credentials: "same-origin", cache: "no-store" });
      if (!res.ok) return null;
      return await res.json();
    } catch (err) {
      console.warn("Notification payload fetch failed", err);
      return null;
    }
  }

  async function showNotification(payload) {
    if (!payload || !payload.title || !payload.body) return;
    if (Notification.permission !== "granted") return;
    if (shouldThrottle(payload.cache_key || "guest", payload.show_after_minutes || 120)) return;

    const registration = await registerServiceWorker();
    const options = {
      body: payload.body,
      icon: payload.icon || "/static/shared/img/avatar-placeholder.svg",
      badge: payload.icon || "/static/shared/img/avatar-placeholder.svg",
      tag: payload.tag || "fluencify-browser-message",
      renotify: false,
      data: { url: payload.target_url || "/" },
    };

    try {
      if (registration && registration.showNotification) {
        await registration.showNotification(payload.title, options);
      } else {
        const note = new Notification(payload.title, options);
        note.onclick = function () {
          window.location.href = payload.target_url || "/";
        };
      }
      markShown(payload.cache_key || "guest");
    } catch (err) {
      console.warn("Notification display failed", err);
    }
  }

  async function initBrowserNotifications() {
    if (!canUseNotifications()) return;
    await registerServiceWorker();
    ensureEnableToast();

    if (Notification.permission !== "granted") return;
    const payload = await fetchPayload();
    await showNotification(payload);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initBrowserNotifications();
  });
})();
