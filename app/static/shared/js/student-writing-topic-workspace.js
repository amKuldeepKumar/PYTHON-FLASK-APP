document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("writingForm");
    const textarea = document.getElementById("submission_text");
    const wordCount = document.getElementById("wordCount");
    const charCount = document.getElementById("charCount");
    const paraCount = document.getElementById("paraCount");
    const timeLeft = document.getElementById("timeLeft");
    const timeUsed = document.getElementById("timeUsed");
    const timeTakenInput = document.getElementById("time_taken_seconds");

    let totalSeconds = 15 * 60;
    let usedSeconds = 0;
    let timerStopped = false;

    function formatTime(seconds) {
      const mins = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return String(mins).padStart(2, "0") + ":" + String(secs).padStart(2, "0");
    }

    function updateCounts() {
      const text = textarea.value || "";
      const words = text.trim() ? text.trim().split(/\s+/).filter(Boolean).length : 0;
      const chars = text.length;
      const paragraphs = text.trim() ? text.split(/\n+/).filter(function (p) { return p.trim(); }).length : 0;

      wordCount.textContent = words;
      charCount.textContent = chars;
      paraCount.textContent = paragraphs;
    }

    function stopTimer() {
      timerStopped = true;
      clearInterval(timer);
    }

    function tick() {
      if (timerStopped) {
        return;
      }

      timeLeft.textContent = formatTime(totalSeconds);
      timeUsed.textContent = formatTime(usedSeconds);
      timeTakenInput.value = usedSeconds;

      if (totalSeconds <= 0) {
        stopTimer();
        alert("Time is over. Your writing will now be submitted.");
        form.submit();
        return;
      }

      totalSeconds -= 1;
      usedSeconds += 1;
    }

    function blockAction(event) {
      event.preventDefault();
      return false;
    }

    ["paste", "copy", "cut", "drop"].forEach(function (eventName) {
      textarea.addEventListener(eventName, blockAction);
    });

    textarea.addEventListener("keydown", function (event) {
      const key = (event.key || "").toLowerCase();
      if ((event.ctrlKey || event.metaKey) && ["c", "v", "x", "a"].includes(key)) {
        event.preventDefault();
      }
    });

    form.addEventListener("submit", function () {
      timeTakenInput.value = usedSeconds;
      stopTimer();
    });

    textarea.addEventListener("input", updateCounts);

    updateCounts();
    const timer = setInterval(tick, 1000);
    tick();
  });
