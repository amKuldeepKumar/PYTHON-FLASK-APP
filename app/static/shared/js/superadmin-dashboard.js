document.addEventListener("DOMContentLoaded", function () {
  document.body.classList.remove("mobile-sidebar-open");
  const shell = document.getElementById("workspaceShell");
  if (shell) shell.classList.remove("mobile-sidebar-open");

  const host = document.getElementById("superadminDashboardPayload");
  let chartData = {};
  try {
    chartData = JSON.parse(host?.dataset.chartData || "{}");
  } catch (_error) {
    chartData = {labels: [], students: [], staff: [], role_labels: [], role_values: []};
  }

  const growthCanvas = document.getElementById("growthChart");
  if (growthCanvas && typeof Chart !== "undefined") {
    new Chart(growthCanvas, {
      type: "line",
      data: {
        labels: chartData.labels || [],
        datasets: [
          {label: "Students", data: chartData.students || [], borderColor: "#4dabf7", backgroundColor: "rgba(77,171,247,.18)", tension: 0.35, fill: true},
          {label: "Staff", data: chartData.staff || [], borderColor: "#82c91e", backgroundColor: "rgba(130,201,30,.12)", tension: 0.35, fill: true}
        ]
      },
      options: {responsive: true, maintainAspectRatio: false, plugins: {legend: {labels: {color: "#334155"}}}, scales: {x: {ticks: {color: "#64748b"}}, y: {beginAtZero: true, ticks: {color: "#64748b"}}}}
    });
  }

  const roleCanvas = document.getElementById("roleChart");
  if (roleCanvas && typeof Chart !== "undefined") {
    new Chart(roleCanvas, {
      type: "doughnut",
      data: {labels: chartData.role_labels || [], datasets: [{data: chartData.role_values || [], backgroundColor: ["#4dabf7", "#82c91e", "#ffd43b", "#ff922b", "#f06595"]}]},
      options: {responsive: true, maintainAspectRatio: false, plugins: {legend: {labels: {color: "#334155"}}}}
    });
  }
});
