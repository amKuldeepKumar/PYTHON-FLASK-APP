document.addEventListener("DOMContentLoaded", function () {
  const btn = document.getElementById("sidebarCollapseBtn");
  const shell = document.getElementById("workspaceShell");
  const sidebar = document.getElementById("appSidebar");

  if (!shell) return;

  function closeMobileSidebar() {
    document.body.classList.remove("mobile-sidebar-open");
    shell.classList.remove("mobile-sidebar-open");
  }

  function toggleSidebar() {
    if (window.innerWidth < 992) {
      document.body.classList.toggle("mobile-sidebar-open");
      shell.classList.toggle("mobile-sidebar-open");
      return;
    }
    shell.classList.toggle("sidebar-collapsed");
    closeMobileSidebar();
  }

  closeMobileSidebar();

  if (btn) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      toggleSidebar();
    });
  }

  document.addEventListener("click", function (event) {
    if (window.innerWidth >= 992) return;
    if (!shell.classList.contains("mobile-sidebar-open")) return;
    if (sidebar && sidebar.contains(event.target)) return;
    if (btn && btn.contains(event.target)) return;
    closeMobileSidebar();
  });

  window.addEventListener("resize", function () {
    if (window.innerWidth >= 992) {
      closeMobileSidebar();
    }
  });
});