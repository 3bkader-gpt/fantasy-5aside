document.addEventListener("DOMContentLoaded", function () {
    // Theme setup
    const THEME_KEY = "fantasy_theme";
    const toggleBtn = document.getElementById("theme-toggle");

    if (toggleBtn) {
        if (localStorage.getItem(THEME_KEY) === "dark") {
            document.body.classList.add("dark-mode");
            toggleBtn.textContent = "☀️";
            toggleBtn.setAttribute("aria-label", "تبديل الوضع النهاري");
            toggleBtn.setAttribute("title", "تبديل الوضع النهاري");
        } else {
            toggleBtn.textContent = "🌙";
            toggleBtn.setAttribute("aria-label", "تبديل الوضع الليلي");
            toggleBtn.setAttribute("title", "تبديل الوضع الليلي");
        }

        toggleBtn.addEventListener("click", () => {
            document.body.classList.toggle("dark-mode");
            const isDark = document.body.classList.contains("dark-mode");
            localStorage.setItem(THEME_KEY, isDark ? "dark" : "light");
            toggleBtn.textContent = isDark ? "☀️" : "🌙";
            toggleBtn.setAttribute("aria-label", isDark ? "تبديل الوضع النهاري" : "تبديل الوضع الليلي");
            toggleBtn.setAttribute("title", isDark ? "تبديل الوضع النهاري" : "تبديل الوضع الليلي");
        });
    }

    // Table setup (Auto-wrap all tables to guarantee mobile responsiveness)
    const tables = document.querySelectorAll("table");
    tables.forEach(table => {
        if (!table.parentElement.classList.contains("table-responsive")) {
            const wrapper = document.createElement("div");
            wrapper.className = "table-responsive";
            table.parentNode.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        }
    });

    const copyLeagueLinkBtn = document.getElementById("copy-league-link-btn");
    if (copyLeagueLinkBtn) {
        copyLeagueLinkBtn.addEventListener("click", copyLeagueLink);
    }

    document.querySelectorAll("#open-rules-modal-link, #footer-rules-link").forEach((el) => {
        el.addEventListener("click", showRulesModal);
    });

    document.querySelectorAll(".close-rules-modal-btn").forEach((btn) => {
        btn.addEventListener("click", closeRulesModal);
    });

    // Mobile Nav "المزيد" sheet
    const navMoreBtn = document.getElementById("nav-more-btn");
    const navSheet = document.getElementById("nav-sheet");
    if (navMoreBtn && navSheet) {
        const openSheet = () => {
            navSheet.classList.add("active");
            navSheet.removeAttribute("aria-hidden");
            navMoreBtn.setAttribute("aria-expanded", "true");
        };
        const closeSheet = () => {
            navSheet.classList.remove("active");
            navSheet.setAttribute("aria-hidden", "true");
            navMoreBtn.setAttribute("aria-expanded", "false");
        };
        navMoreBtn.addEventListener("click", openSheet);
        navSheet.querySelector(".nav-sheet-backdrop")?.addEventListener("click", closeSheet);
        navSheet.querySelector(".close-nav-sheet-btn")?.addEventListener("click", closeSheet);
        navSheet.querySelector(".nav-sheet-rules-link")?.addEventListener("click", (e) => {
            e.preventDefault();
            closeSheet();
            showRulesModal(e);
        });
    }
});

// Global UI functions
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function showPromptModal(title, message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('global-modal');
        if (!modal) {
            // fallback if modal HTML is missing for some reason
            return resolve(prompt(`${title}\n${message}`));
        }

        const titleEl = document.getElementById('modal-title');
        const bodyEl = document.getElementById('modal-body');
        const confirmBtn = document.getElementById('modal-confirm-btn');
        const cancelBtn = document.getElementById('modal-cancel-btn');

        titleEl.textContent = title;
        bodyEl.innerHTML = `<p class="mb-1">${message}</p><input type="password" id="modal-input" class="form-control">`;
        modal.classList.add('active');

        setTimeout(() => {
            const input = document.getElementById('modal-input');
            if (input) input.focus();
        }, 100);

        const cleanup = () => {
            modal.classList.remove('active');
            confirmBtn.onclick = null;
            cancelBtn.onclick = null;
        };

        confirmBtn.onclick = () => {
            const input = document.getElementById('modal-input');
            const val = input ? input.value : null;
            cleanup();
            resolve(val);
        };

        cancelBtn.onclick = () => {
            cleanup();
            resolve(null);
        };
    });
}

// Rules Modal Functions
function showRulesModal(event) {
    if (event) event.preventDefault();
    const modal = document.getElementById('rules-modal');
    if (modal) {
        modal.classList.add('active');
    }
}

function closeRulesModal() {
    const modal = document.getElementById('rules-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}

// Close modals when clicking outside their content
document.addEventListener("DOMContentLoaded", function () {
    const overlays = document.querySelectorAll('.modal-overlay');
    overlays.forEach(overlay => {
        overlay.addEventListener('click', function (e) {
            if (e.target === this) {
                this.classList.remove('active');
            }
        });
    });
});
// Copy League Link Function
function copyLeagueLink() {
    const url = window.location.href;
    navigator.clipboard.writeText(url).then(() => {
        showToast("تم نسخ رابط الدوري بنجاح! شاركه مع فريقك 🚀", "success");
    }).catch(err => {
        showToast("عذراً، حدث خطأ أثناء نسخ الرابط", "error");
    });
}
