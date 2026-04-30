(function () {
  const workspace = document.getElementById("lessonWorkspace");

  const questionEl = document.getElementById("questionText");
  const speakBtn = document.getElementById("speakQuestionBtn");
  const recordBtn = document.getElementById("recordAnswerBtn");
  const responseText = document.getElementById("responseText");
  const responseMode = document.getElementById("responseMode");
  const durationSeconds = document.getElementById("durationSeconds");
  const checkBtn = document.getElementById("checkAnswerBtn");
  const skipBtn = document.getElementById("skipQuestionBtn");
  const checkForm = document.getElementById("checkForm");
  const checkResponseText = document.getElementById("checkResponseText");
  const checkResponseMode = document.getElementById("checkResponseMode");
  const checkDurationSeconds = document.getElementById("checkDurationSeconds");
  const skipForm = document.getElementById("skipForm");
  const skipResponseText = document.getElementById("skipResponseText");
  const skipResponseMode = document.getElementById("skipResponseMode");
  const skipDurationSeconds = document.getElementById("skipDurationSeconds");

  const hintPanel = document.getElementById("hintPanel");
  const synonymPanel = document.getElementById("synonymPanel");
  const translationPanel = document.getElementById("translationPanel");
  const questionTranslatePanel = document.getElementById("questionTranslatePanel");
  const answerTranslatePanel = document.getElementById("answerTranslatePanel");
  const questionTranslateToggle = document.getElementById("questionTranslateToggle");
  const answerTranslateToggle = document.getElementById("answerTranslateToggle");
  const questionTranslateState = document.getElementById("questionTranslateState");
  const answerTranslateState = document.getElementById("answerTranslateState");
  const toggleHintBtn = document.getElementById("toggleHintBtn");
  const toggleSynonymBtn = document.getElementById("toggleSynonymBtn");
  const toggleTranslationBtn = document.getElementById("toggleTranslationBtn");
  const supportToolNotice = document.getElementById("supportToolNotice");
  const supportToolCounter = document.getElementById("supportToolCounter");
  const supportToolRemaining = document.getElementById("supportToolRemaining");
  const supportToolPenalty = document.getElementById("supportToolPenalty");

  const hintInputs = [
    document.getElementById("hintUsed"),
    document.getElementById("checkHintUsed"),
    document.getElementById("skipHintUsed")
  ];

  const synonymInputs = [
    document.getElementById("synonymUsed"),
    document.getElementById("checkSynonymUsed"),
    document.getElementById("skipSynonymUsed")
  ];

  const translationInputs = [
    document.getElementById("translationUsed"),
    document.getElementById("checkTranslationUsed"),
    document.getElementById("skipTranslationUsed")
  ];

  const supportToolMap = {
    hint: { button: toggleHintBtn, panel: hintPanel, inputs: hintInputs },
    synonym: { button: toggleSynonymBtn, panel: synonymPanel, inputs: synonymInputs },
    translation: { button: toggleTranslationBtn, panel: translationPanel, inputs: translationInputs }
  };

  function setAll(inputs, value) {
    inputs.forEach(function (input) {
      if (input) {
        input.value = value ? "1" : "0";
      }
    });
  }

  function showPanel(panel, inputs) {
    if (!panel) return;
    panel.classList.remove("d-none");
    setAll(inputs, true);
  }

  function showNotice(message, isWarning) {
    if (!supportToolNotice) return;
    supportToolNotice.innerText = message || "";
    supportToolNotice.classList.remove("d-none", "alert-warning", "alert-info", "alert-danger");
    supportToolNotice.classList.add(isWarning ? "alert-warning" : "alert-info");
  }

  function updateSupportStatus(status) {
    if (!status) return;
    if (supportToolCounter) supportToolCounter.innerText = status.used;
    if (supportToolRemaining) supportToolRemaining.innerText = status.remaining;
    if (supportToolPenalty) supportToolPenalty.innerText = Math.round(status.penalty_points || 0);

    if (status.reached) {
      Object.keys(supportToolMap).forEach(function (key) {
        const config = supportToolMap[key];
        if (!config || !config.button) return;
        const alreadyUsed = config.inputs && config.inputs[0] && config.inputs[0].value === "1";
        if (!alreadyUsed) {
          config.button.disabled = true;
        }
      });
    }
  }

  function setToggleVisual(toggle, label, isActive) {
    if (toggle) {
      toggle.dataset.active = isActive ? "true" : "false";
      toggle.setAttribute("aria-pressed", isActive ? "true" : "false");
    }
    if (label) {
      label.innerText = isActive ? "ON" : "OFF";
    }
  }

  function setPanelVisible(panel, toggle, label, isVisible) {
    if (panel) {
      panel.classList.toggle("d-none", !isVisible);
    }
    setToggleVisual(toggle, label, isVisible);
  }

  function isTranslationUnlocked() {
    return Boolean(translationInputs[0] && translationInputs[0].value === "1");
  }

  function syncProgressWidths() {
    document.querySelectorAll(".js-progress-width").forEach(function (el) {
      const raw = Number(el.dataset.width || 0);
      const clamped = Math.max(0, Math.min(100, raw));
      el.style.width = clamped + "%";
      if (!el.textContent.trim() && clamped > 0) {
        el.textContent = "";
      }
    });
  }

  function openSupportTool(toolName) {
    const config = supportToolMap[toolName];
    if (!config || !config.button) return Promise.resolve(false);

    if (config.inputs && config.inputs[0] && config.inputs[0].value === "1") {
      showPanel(config.panel, config.inputs);
      return Promise.resolve(true);
    }

    const supportToolUrlTemplate = workspace?.dataset.supportToolUrlTemplate || "";
    const csrfToken = workspace?.dataset.csrfToken || "";

    return fetch(supportToolUrlTemplate.replace("__tool__", toolName), {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
      },
      body: `csrf_token=${encodeURIComponent(csrfToken)}`
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { statusCode: response.status, data: data };
        });
      })
      .then(function (result) {
        if (result.data && result.data.ok) {
          showPanel(config.panel, config.inputs);
          updateSupportStatus(result.data.status);
          showNotice("Support tool opened. This use is counted and affects scoring.", false);
          return true;
        }

        if (result.data && result.data.limit_reached) {
          updateSupportStatus(result.data.status);
          showNotice(result.data.message || "Support-tool limit reached for this lesson.", true);
          return false;
        }

        showNotice((result.data && result.data.message) || "Support tool could not be opened.", true);
        return false;
      })
      .catch(function () {
        showNotice("Support tool could not be opened.", true);
        return false;
      });
  }

  function handleTranslationToggle(which) {
    const panel = which === "question" ? questionTranslatePanel : answerTranslatePanel;
    const toggle = which === "question" ? questionTranslateToggle : answerTranslateToggle;
    const stateLabel = which === "question" ? questionTranslateState : answerTranslateState;

    if (!panel || !toggle) return;

    const currentlyVisible = !panel.classList.contains("d-none");

    if (currentlyVisible) {
      setPanelVisible(panel, toggle, stateLabel, false);
      return;
    }

    if (isTranslationUnlocked()) {
      setPanelVisible(panel, toggle, stateLabel, true);
      return;
    }

    openSupportTool("translation").then(function (opened) {
      if (!opened) return;
      setPanelVisible(panel, toggle, stateLabel, true);
    });
  }

  if (toggleHintBtn) {
    toggleHintBtn.addEventListener("click", function () {
      openSupportTool("hint");
    });
  }

  if (toggleSynonymBtn) {
    toggleSynonymBtn.addEventListener("click", function () {
      openSupportTool("synonym");
    });
  }

  if (toggleTranslationBtn) {
    toggleTranslationBtn.addEventListener("click", function () {
      openSupportTool("translation").then(function (opened) {
        if (!opened) return;
        showNotice("Translation support is ready. Use the Translate toggles beside the question and answer sections.", false);
      });
    });
  }

  if (questionTranslateToggle) {
    questionTranslateToggle.addEventListener("click", function () {
      handleTranslationToggle("question");
    });
  }

  if (answerTranslateToggle) {
    answerTranslateToggle.addEventListener("click", function () {
      handleTranslationToggle("answer");
    });
  }

  if (hintInputs[0] && hintInputs[0].value === "1") {
    showPanel(hintPanel, hintInputs);
  }

  if (synonymInputs[0] && synonymInputs[0].value === "1") {
    showPanel(synonymPanel, synonymInputs);
  }

  if (translationInputs[0] && translationInputs[0].value === "1") {
    showPanel(translationPanel, translationInputs);
  }

  setPanelVisible(questionTranslatePanel, questionTranslateToggle, questionTranslateState, false);
  setPanelVisible(answerTranslatePanel, answerTranslateToggle, answerTranslateState, false);
  syncProgressWidths();

  if (checkBtn && responseText && checkForm && checkResponseText) {
    checkBtn.addEventListener("click", function () {
      if (!responseText.value.trim()) {
        alert("Please write or speak your answer first.");
        return;
      }
      checkResponseText.value = responseText.value;
      if (checkResponseMode) checkResponseMode.value = responseMode ? responseMode.value : "typed";
      if (checkDurationSeconds) checkDurationSeconds.value = durationSeconds ? durationSeconds.value : "0";
      checkForm.submit();
    });
  }

  if (skipBtn && skipForm) {
    skipBtn.addEventListener("click", function () {
      if (skipResponseText) skipResponseText.value = responseText ? responseText.value : "";
      if (skipResponseMode) skipResponseMode.value = responseMode ? responseMode.value : "typed";
      if (skipDurationSeconds) skipDurationSeconds.value = durationSeconds ? durationSeconds.value : "0";
      skipForm.submit();
    });
  }
})();
