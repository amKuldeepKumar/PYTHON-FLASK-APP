(function () {
  const selectAll = document.getElementById("selectAllQuestions");
  const checkboxes = Array.from(document.querySelectorAll(".question-checkbox"));
  const selectedCount = document.getElementById("selectedCount");
  const bulkDeleteBtn = document.getElementById("bulkDeleteBtn");

  function updateSelectionState() {
    const checked = checkboxes.filter((cb) => cb.checked).length;
    if (selectedCount) selectedCount.textContent = checked;
    if (bulkDeleteBtn) bulkDeleteBtn.disabled = checked === 0;
    if (selectAll) {
      selectAll.checked = checked > 0 && checked === checkboxes.length;
      selectAll.indeterminate = checked > 0 && checked < checkboxes.length;
    }
  }

  if (selectAll) {
    selectAll.addEventListener("change", function () {
      checkboxes.forEach((cb) => { cb.checked = selectAll.checked; });
      updateSelectionState();
    });
  }

  checkboxes.forEach((cb) => cb.addEventListener("change", updateSelectionState));
  updateSelectionState();

  window.confirmBulkDelete = function () {
    const checked = checkboxes.filter((cb) => cb.checked).length;
    if (!checked) {
      alert("Select at least one question to delete.");
      return false;
    }
    return confirm(`Delete ${checked} selected question${checked === 1 ? "" : "s"}?`);
  };
})();
