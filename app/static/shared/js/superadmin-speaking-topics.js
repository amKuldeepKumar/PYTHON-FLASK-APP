(function () {
  const accessType = document.getElementById("accessType");
  const couponEnabled = document.getElementById("couponEnabled");
  const pricingFields = document.querySelectorAll(".pricing-field");
  const couponFields = document.querySelectorAll(".coupon-field");
  const priceField = document.getElementById("priceField");
  const discountPriceField = document.getElementById("discountPriceField");
  const couponCodeField = document.getElementById("couponCodeField");
  const couponDiscountTypeField = document.getElementById("couponDiscountTypeField");
  const couponDiscountValueField = document.getElementById("couponDiscountValueField");
  const couponValidFromField = document.getElementById("couponValidFromField");
  const couponValidUntilField = document.getElementById("couponValidUntilField");
  if (!accessType || !couponEnabled) return;

  function showElements(elements, visible) {
    elements.forEach((el) => { el.style.display = visible ? "" : "none"; });
  }

  function clearCouponFields() {
    if (couponCodeField) couponCodeField.value = "";
    if (couponDiscountTypeField) couponDiscountTypeField.value = "";
    if (couponDiscountValueField) couponDiscountValueField.value = "";
    if (couponValidFromField) couponValidFromField.value = "";
    if (couponValidUntilField) couponValidUntilField.value = "";
  }

  function syncForm() {
    const type = accessType.value;
    const couponChecked = couponEnabled.checked;
    if (type === "free") {
      showElements(pricingFields, true);
      showElements(couponFields, false);
      if (priceField) priceField.value = "0";
      if (discountPriceField) discountPriceField.value = "";
      couponEnabled.checked = false;
      clearCouponFields();
    } else if (type === "paid") {
      showElements(pricingFields, true);
      showElements(couponFields, couponChecked);
      if (!couponChecked) clearCouponFields();
    } else if (type === "coupon") {
      showElements(pricingFields, true);
      showElements(couponFields, true);
      couponEnabled.checked = true;
    } else {
      showElements(pricingFields, true);
      showElements(couponFields, false);
    }
  }

  accessType.addEventListener("change", syncForm);
  couponEnabled.addEventListener("change", syncForm);
  syncForm();
})();
