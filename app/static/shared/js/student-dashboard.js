document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
    new bootstrap.Tooltip(el);
  });

  const dayCells = Array.from(document.querySelectorAll(".day-cell:not(.is-future)"));
  const detailPanel = document.getElementById("calendarDetailPanel");
  if (!dayCells.length || !detailPanel) {
    return;
  }

  const title = detailPanel.querySelector(".calendar-detail-title");
  const copy = detailPanel.querySelector(".calendar-detail-copy");

  function selectDay(cell) {
    dayCells.forEach(function (item) {
      item.classList.remove("is-selected");
      item.setAttribute("aria-pressed", "false");
    });

    cell.classList.add("is-selected");
    cell.setAttribute("aria-pressed", "true");

    if (title) {
      title.textContent = cell.dataset.dateLabel || "Selected day";
    }

    if (copy) {
      copy.textContent = cell.dataset.tooltip || "No activity summary is available for this day yet.";
    }
  }

  dayCells.forEach(function (cell) {
    cell.addEventListener("click", function () {
      selectDay(cell);
    });

    cell.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectDay(cell);
      }
    });
  });

  const initialCell = dayCells.find(function (cell) {
    return cell.classList.contains("i4") || cell.classList.contains("i3");
  }) || dayCells.find(function (cell) {
    return cell.classList.contains("is-present");
  }) || dayCells.find(function (cell) {
    return !cell.classList.contains("out");
  });

  if (initialCell) {
    selectDay(initialCell);
  }
});
