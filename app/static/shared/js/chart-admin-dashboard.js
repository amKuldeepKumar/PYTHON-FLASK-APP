document.addEventListener("DOMContentLoaded", function () {
  const host = document.getElementById("adminDashboardPayload");
  if (!host || typeof Chart === "undefined") return;
  const chartData = JSON.parse(host.dataset.chartData || "{}");
  new Chart(document.getElementById("adminGrowthChart"), {
    type: "bar",
    data: {labels: chartData.labels, datasets:[{label:"Students", data: chartData.students, backgroundColor:"rgba(77,171,247,.55)", borderColor:"#4dabf7", borderWidth:1}]},
    options:{responsive:true, maintainAspectRatio:false, plugins:{legend:{labels:{color:'#dbe6ff'}}}, scales:{x:{ticks:{color:'#9fb3d9'}}, y:{ticks:{color:'#9fb3d9'}, beginAtZero:true}}}
  });
});
