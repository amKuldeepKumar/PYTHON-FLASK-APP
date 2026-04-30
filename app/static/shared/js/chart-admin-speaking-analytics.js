document.addEventListener("DOMContentLoaded", function () {
  const host = document.getElementById("adminSpeakingAnalyticsPayload");
  if (!host || typeof Chart === "undefined") return;
  const scopeChartData = JSON.parse(host.dataset.scopeChart || "{}");
  new Chart(document.getElementById("scopeSpeakingChart"), {
    type: "bar",
    data: {labels: scopeChartData.labels, datasets:[{label:"Average score", data: scopeChartData.avg_scores, backgroundColor:"rgba(77,171,247,.55)", borderColor:"#4dabf7", borderWidth:1},{label:"Attempts", data: scopeChartData.attempts, type:"line", borderColor:"#ffd43b", backgroundColor:"rgba(255,212,59,.12)", tension:.3, yAxisID:"y1"}]},
    options: {responsive:true, maintainAspectRatio:false, plugins:{legend:{labels:{color:'#dbe6ff'}}}, scales:{x:{ticks:{color:'#9fb3d9'}}, y:{beginAtZero:true, max:10, ticks:{color:'#9fb3d9'}}, y1:{beginAtZero:true, position:'right', grid:{drawOnChartArea:false}, ticks:{color:'#9fb3d9'}}}}
  });

  if (host.dataset.selectedChart) {
    const selectedChartData = JSON.parse(host.dataset.selectedChart || "{}");
    const selectedCanvas = document.getElementById("selectedStudentChart");
    if (selectedCanvas) {
      new Chart(selectedCanvas, {
        type: "line",
        data: {
          labels: selectedChartData.score_history.labels,
          datasets: [
            {label: "Score", data: selectedChartData.score_history.scores, borderColor: "#4dabf7", backgroundColor: "rgba(77,171,247,.16)", tension: .35, fill: true},
            {label: "Relevance %", data: selectedChartData.score_history.relevance, borderColor: "#74c0fc", backgroundColor: "rgba(116,192,252,.08)", tension: .35, yAxisID: "y1"}
          ]
        },
        options: {responsive:true, maintainAspectRatio:false, plugins:{legend:{labels:{color:'#dbe6ff'}}}, scales:{x:{ticks:{color:'#9fb3d9'}}, y:{beginAtZero:true, max:10, ticks:{color:'#9fb3d9'}}, y1:{beginAtZero:true, max:100, position:'right', grid:{drawOnChartArea:false}, ticks:{color:'#9fb3d9'}}}}
      });
    }
  }
});
