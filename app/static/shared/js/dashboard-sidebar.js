document.addEventListener("DOMContentLoaded", function () {
    const body = document.body;
    const shell = document.getElementById("workspaceShell");
    const sidebar = document.getElementById("appSidebar");
    const toggleBtn = document.getElementById("sidebarCollapseBtn");
    const menuToggles = document.querySelectorAll(".js-menu-toggle");

    if (!shell) return;

    let backdrop = document.querySelector(".sidebar-backdrop");
    if (!backdrop) {
        backdrop = document.createElement("div");
        backdrop.className = "sidebar-backdrop";
        document.body.appendChild(backdrop);
    }

    function closeMobileSidebar() {
        body.classList.remove("mobile-sidebar-open");
        shell.classList.remove("mobile-sidebar-open");
    }

    function openMobileSidebar() {
        body.classList.add("mobile-sidebar-open");
        shell.classList.add("mobile-sidebar-open");
    }

    function toggleSidebar() {
        if (window.innerWidth < 992) {
            if (shell.classList.contains("mobile-sidebar-open") || body.classList.contains("mobile-sidebar-open")) {
                closeMobileSidebar();
            } else {
                openMobileSidebar();
            }
        } else {
            shell.classList.toggle("sidebar-collapsed");
            closeMobileSidebar();
        }
    }

    closeMobileSidebar();

    if (toggleBtn) {
        toggleBtn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            toggleSidebar();
        });
    }

    if (backdrop) {
        backdrop.addEventListener("click", function () {
            closeMobileSidebar();
        });
    }

    document.addEventListener("click", function (event) {
        if (window.innerWidth >= 992) return;
        if (!shell.classList.contains("mobile-sidebar-open") && !body.classList.contains("mobile-sidebar-open")) return;
        if (sidebar && sidebar.contains(event.target)) return;
        if (toggleBtn && toggleBtn.contains(event.target)) return;
        if (backdrop && backdrop.contains(event.target)) return;
        closeMobileSidebar();
    });

    window.addEventListener("resize", function () {
        if (window.innerWidth >= 992) {
            closeMobileSidebar();
        }
    });

    menuToggles.forEach(function (toggle) {
        toggle.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();

            const group = this.closest(".menu-group");
            if (!group) return;

            const isOpen = group.classList.contains("open");

            document.querySelectorAll(".menu-group.open").forEach(function (item) {
                if (item !== group) {
                    item.classList.remove("open");
                    const btn = item.querySelector(".js-menu-toggle");
                    if (btn) btn.setAttribute("aria-expanded", "false");
                }
            });

            if (isOpen) {
                group.classList.remove("open");
                this.setAttribute("aria-expanded", "false");
            } else {
                group.classList.add("open");
                this.setAttribute("aria-expanded", "true");
            }
        });
    });
});