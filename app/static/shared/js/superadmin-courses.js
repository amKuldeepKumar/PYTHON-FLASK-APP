(function () {
  const freeToggle = document.getElementById("freeCourseToggle");
  const premium = document.getElementById("premiumCourseToggle");
  const accessType = document.getElementById("courseAccessType");
  const prices = document.querySelectorAll(".price-input");
  if (!freeToggle || !premium || !accessType) return;

  function sync() {
    const isFree = freeToggle.checked || accessType.value === "free";
    if (isFree) {
      freeToggle.checked = true;
      accessType.value = "free";
      premium.checked = false;
      prices.forEach((el) => { el.value = "0.00"; });
    } else {
      freeToggle.checked = false;
      accessType.value = "paid";
      premium.checked = true;
    }
  }

  freeToggle.addEventListener("change", sync);
  premium.addEventListener("change", function () {
    if (premium.checked) {
      freeToggle.checked = false;
      accessType.value = "paid";
    } else {
      accessType.value = "free";
    }
    sync();
  });
  accessType.addEventListener("change", function () {
    freeToggle.checked = accessType.value === "free";
    premium.checked = accessType.value === "paid";
    sync();
  });
  sync();
})();
