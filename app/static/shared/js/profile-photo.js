(function () {
  let stream = null;

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      stream = null;
    }
  }

  async function openCamera() {
    const wrap = document.getElementById("cameraWrap");
    const video = document.getElementById("cameraVideo");
    if (!wrap || !video || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;

    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      video.srcObject = stream;
      wrap.classList.remove("d-none");
    } catch (err) {
      alert("Camera access was blocked or is not available on this device.");
    }
  }

  function capturePhoto() {
    const video = document.getElementById("cameraVideo");
    const canvas = document.getElementById("cameraCanvas");
    const field = document.getElementById("cameraImageField");
    const preview = document.getElementById("avatarPreview");
    const removeField = document.getElementById("removeAvatarField");
    if (!video || !canvas || !field || !preview) return;

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
    field.value = dataUrl;
    preview.src = dataUrl;
    if (removeField) removeField.value = "0";
    stopCamera();
    document.getElementById("cameraWrap").classList.add("d-none");
  }

  function bindFilePreview() {
    const input = document.getElementById("avatarFileInput");
    const preview = document.getElementById("avatarPreview");
    const field = document.getElementById("cameraImageField");
    const removeField = document.getElementById("removeAvatarField");
    if (!input || !preview) return;

    input.addEventListener("change", function () {
      const file = this.files && this.files[0];
      if (!file) return;
      preview.src = URL.createObjectURL(file);
      if (field) field.value = "";
      if (removeField) removeField.value = "0";
    });
  }

  function bindRemovePhoto() {
    const btn = document.getElementById("removePhotoBtn");
    const preview = document.getElementById("avatarPreview");
    const field = document.getElementById("cameraImageField");
    const removeField = document.getElementById("removeAvatarField");
    const fileInput = document.getElementById("avatarFileInput");
    if (!btn || !preview || !removeField) return;

    btn.addEventListener("click", function () {
      preview.src = "/static/shared/img/avatar-placeholder.svg";
      removeField.value = "1";
      if (field) field.value = "";
      if (fileInput) fileInput.value = "";
      stopCamera();
      const wrap = document.getElementById("cameraWrap");
      if (wrap) wrap.classList.add("d-none");
    });
  }

  function boot() {
    bindFilePreview();
    bindRemovePhoto();

    const openBtn = document.getElementById("openCameraBtn");
    const captureBtn = document.getElementById("capturePhotoBtn");
    const closeBtn = document.getElementById("closeCameraBtn");

    if (openBtn) openBtn.addEventListener("click", openCamera);
    if (captureBtn) captureBtn.addEventListener("click", capturePhoto);
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        stopCamera();
        const wrap = document.getElementById("cameraWrap");
        if (wrap) wrap.classList.add("d-none");
      });
    }

    window.addEventListener("beforeunload", stopCamera);
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
