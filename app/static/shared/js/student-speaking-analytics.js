document.addEventListener("DOMContentLoaded", function () {
  const host = document.getElementById("studentSpeakingAnalyticsPayload");
  if (!host || typeof Chart === "undefined") return;
  const chartData = JSON.parse(host.dataset.chartData || "{}");

  new Chart(document.getElementById("scoreTrendChart"), {
    type: "line",
    data: {
      labels: chartData.score_history.labels,
      datasets: [
        {label: "Score", data: chartData.score_history.scores, borderColor: "#4dabf7", backgroundColor: "rgba(77,171,247,.18)", tension: .35, fill: true},
        {label: "Relevance %", data: chartData.score_history.relevance, borderColor: "#74c0fc", backgroundColor: "rgba(116,192,252,.08)", tension: .35, yAxisID: "y1"}
      ]
    },
    options: {responsive:true, maintainAspectRatio:false, plugins:{legend:{labels:{color:'#dbe6ff'}}}, scales:{x:{ticks:{color:'#9fb3d9'}}, y:{beginAtZero:true, max:10, ticks:{color:'#9fb3d9'}}, y1:{beginAtZero:true, max:100, position:'right', grid:{drawOnChartArea:false}, ticks:{color:'#9fb3d9'}}}}
  });

  new Chart(document.getElementById("timeSpentChart"), {
    type: "bar",
    data: {
      labels: chartData.time_history.labels,
      datasets: [
        {label: "Minutes spent", data: chartData.time_history.minutes, backgroundColor: "rgba(77,171,247,.55)", borderColor: "#4dabf7", borderWidth: 1},
        {label: "Words", data: chartData.time_history.words, type: "line", borderColor: "#ffd43b", backgroundColor: "rgba(255,212,59,.14)", tension: .35, yAxisID: "y1"}
      ]
    },
    options: {responsive:true, maintainAspectRatio:false, plugins:{legend:{labels:{color:'#dbe6ff'}}}, scales:{x:{ticks:{color:'#9fb3d9'}}, y:{beginAtZero:true, ticks:{color:'#9fb3d9'}}, y1:{beginAtZero:true, position:'right', grid:{drawOnChartArea:false}, ticks:{color:'#9fb3d9'}}}}
  });
});
