document.addEventListener("DOMContentLoaded", function () {
  const host = document.getElementById("checkoutConfig");
  if (!host) return;
  const scopeFull = document.getElementById("scopeFull");
  const scopeLevel = document.getElementById("scopeLevel");
  const levelSelect = document.getElementById("levelSelect");
  const summaryPlan = document.getElementById("summaryPlan");
  const summaryLevel = document.getElementById("summaryLevel");
  const summaryTotal = document.getElementById("summaryTotal");
  const payBtn = document.getElementById("payBtn");
  const discount = parseFloat(host.dataset.discount || "0");
  const currency = host.dataset.currency || "USD";
  const fullPrice = parseFloat(host.dataset.fullPrice || "0");
  const levelPrice = parseFloat(host.dataset.levelPrice || "0");
  const fallbackLevel = host.dataset.selectedLevel || "1";

  function render() {
    const levelMode = scopeLevel && scopeLevel.checked;
    const total = Math.max(0, (levelMode ? levelPrice : fullPrice) - discount);
    summaryPlan.textContent = levelMode ? "Single level" : "Full course";
    summaryLevel.textContent = levelMode ? `Level ${levelSelect ? levelSelect.value : fallbackLevel}` : "All levels";
    summaryTotal.textContent = total <= 0 ? "Free" : `${currency} ${total.toFixed(2)}`;
    if (payBtn) {
      payBtn.textContent = total <= 0 ? "Unlock Now" : `Pay ${currency} ${total.toFixed(2)}`;
    }
  }

  [scopeFull, scopeLevel, levelSelect].forEach((el) => el && el.addEventListener("change", render));
  render();
});
