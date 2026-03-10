document.addEventListener("DOMContentLoaded", function () {
    const sortTabs = document.querySelectorAll(".tab-btn[data-sort]");
    const scopeTabs = document.querySelectorAll("#scope-tabs .tab-btn");
    const tbody = document.getElementById("leaderboard-body");

    if (!tbody) return;

    function getActiveScope() {
        return tbody.getAttribute("data-active-scope") || "current";
    }

    function updateRowVisibleValues(row) {
        const scope = getActiveScope();
        const getVal = (metric) => row.getAttribute(`data-${metric}-${scope}`) || "0";

        const matchesCell = row.querySelector(".matches-cell");
        const pointsCell = row.querySelector(".points-cell");
        const goalsCell = row.querySelector(".goals-cell");
        const assistsCell = row.querySelector(".assists-cell");
        const savesCell = row.querySelector(".saves-cell");
        const csCell = row.querySelector(".cs-cell");

        if (matchesCell) matchesCell.textContent = getVal("matches");
        if (pointsCell) pointsCell.querySelector("strong").textContent = getVal("points");
        if (goalsCell) goalsCell.textContent = getVal("goals");
        if (assistsCell) assistsCell.textContent = getVal("assists");
        if (savesCell) savesCell.textContent = getVal("saves");
        if (csCell) csCell.textContent = getVal("clean-sheets");
    }

    function sortAndRender(sortMetric) {
        const scope = getActiveScope();
        const rows = Array.from(tbody.querySelectorAll("tr"));

        rows.forEach(updateRowVisibleValues);

        rows.sort((a, b) => {
            const key = sortMetric === "points" ? "points" : sortMetric;
            const attr = `data-${key}-${scope}`;
            const valA = parseInt(a.getAttribute(attr)) || 0;
            const valB = parseInt(b.getAttribute(attr)) || 0;

            if (valB === valA && key !== "points") {
                const pointsA = parseInt(a.getAttribute(`data-points-${scope}`)) || 0;
                const pointsB = parseInt(b.getAttribute(`data-points-${scope}`)) || 0;
                return pointsB - pointsA;
            }
            return valB - valA;
        });

        tbody.innerHTML = "";
        let visibleRank = 0;

        rows.forEach((row) => {
            const savesAttr = `data-saves-${scope}`;
            const csAttr = `data-clean-sheets-${scope}`;
            const saves = parseInt(row.getAttribute(savesAttr)) || 0;
            const cleanSheets = parseInt(row.getAttribute(csAttr)) || 0;

            let isVisible = true;
            if (sortMetric === "saves") {
                if (saves === 0 && cleanSheets === 0) {
                    isVisible = false;
                }
            }

            if (isVisible) {
                visibleRank++;
                row.style.display = "";

                const rankText = visibleRank;
                const rankTitles = { 1: "المركز الأول", 2: "المركز الثاني", 3: "المركز الثالث" };
                const rankPrefix =
                    rankText === 1 ? '<span title="' + rankTitles[1] + '">🥇</span>' : rankText === 2 ? '<span title="' + rankTitles[2] + '">🥈</span>' : rankText === 3 ? '<span title="' + rankTitles[3] + '">🥉</span>' : "";

                const rankCell = row.querySelector(".rank-col");
                if (rankCell) {
                    const trendSpan = rankCell.querySelector(".trend-indicator");
                    const trendHtml = trendSpan ? trendSpan.outerHTML : "";
                    rankCell.innerHTML = `${trendHtml} ${rankText} ${rankPrefix}`;
                }

                const nameCell = row.querySelector("td[data-label='اللاعب']");
                if (nameCell) {
                    const existingCrown = nameCell.querySelector(".crown");
                    if (existingCrown) existingCrown.remove();
                    if (rankText === 1 && sortMetric === "points" && scope === "current") {
                        nameCell.insertAdjacentHTML("beforeend", '<span class="crown" title="صاحب المركز الأول (بطل الترتيب)">👑</span>');
                    }
                }
            } else {
                row.style.display = "none";
            }

            tbody.appendChild(row);
        });
    }

    // Sorting tabs
    if (sortTabs.length > 0) {
        sortTabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                sortTabs.forEach((t) => t.classList.remove("active"));
                tab.classList.add("active");
                const sortMetric = tab.getAttribute("data-sort") || "points";
                sortAndRender(sortMetric);
            });
        });
    }

    // Scope tabs
    if (scopeTabs.length > 0) {
        scopeTabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                const scope = tab.getAttribute("data-scope") || "current";
                tbody.setAttribute("data-active-scope", scope);
                scopeTabs.forEach((t) => t.classList.remove("active"));
                tab.classList.add("active");

                const activeSortTab =
                    Array.from(sortTabs).find((t) => t.classList.contains("active")) || sortTabs[0];
                const sortMetric = activeSortTab
                    ? activeSortTab.getAttribute("data-sort") || "points"
                    : "points";
                sortAndRender(sortMetric);
            });
        });
    }

    if (sortTabs.length > 0) {
        const defaultSort = sortTabs[0].getAttribute("data-sort") || "points";
        sortAndRender(defaultSort);
    }

    // Share Leaderboard Logic
    const shareBtn = document.getElementById("share-leaderboard");
    const captureArea = document.getElementById("capture-area");

    if (shareBtn && captureArea) {
        // Resolve CSS variable colors to inline styles so html2canvas can render them
        function resolveVarColors(root) {
            var els = [root].concat(Array.from(root.querySelectorAll('*')));
            var saved = [];
            for (var i = 0; i < els.length; i++) {
                var el = els[i];
                var cs = window.getComputedStyle(el);
                saved.push({ el: el, color: el.style.color, bg: el.style.backgroundColor, bc: el.style.borderColor, bgi: el.style.backgroundImage });
                el.style.color = cs.color;
                el.style.backgroundColor = cs.backgroundColor;
                el.style.borderColor = cs.borderColor;
                var bgImg = cs.backgroundImage;
                if (bgImg && bgImg !== 'none') el.style.backgroundImage = bgImg;
            }
            return saved;
        }
        function restoreStyles(saved) {
            for (var i = 0; i < saved.length; i++) {
                var s = saved[i];
                s.el.style.color = s.color;
                s.el.style.backgroundColor = s.bg;
                s.el.style.borderColor = s.bc;
                s.el.style.backgroundImage = s.bgi;
            }
        }

        shareBtn.addEventListener("click", () => {
            const originalDisplay = shareBtn.style.display;
            const originalText = shareBtn.textContent;
            shareBtn.style.display = "none"; // Hide button from canvas
            shareBtn.classList.add("btn-loading");
            shareBtn.disabled = true;
            shareBtn.textContent = "جاري التقاط الصورة...";

            const isDark = document.body.classList.contains("dark-mode");
            const bgColor = isDark ? "#020617" : "#f8fafc";

            const doCapture = () => {
                captureArea.scrollIntoView({ behavior: "instant", block: "start" });
                var saved = resolveVarColors(captureArea);
                return html2canvas(captureArea, {
                    backgroundColor: bgColor,
                    scale: 2,
                    useCORS: true,
                    logging: false,
                    windowWidth: captureArea.scrollWidth,
                    windowHeight: captureArea.scrollHeight
                }).then(function (canvas) { restoreStyles(saved); return canvas; })
                  .catch(function (err) { restoreStyles(saved); throw err; });
            };

            Promise.resolve()
                .then(() => document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve())
                .then(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))))
                .then(() => new Promise(r => setTimeout(r, 150)))
                .then(doCapture)
                .then(canvas => {
                shareBtn.style.display = originalDisplay;
                shareBtn.classList.remove("btn-loading");
                shareBtn.disabled = false;
                shareBtn.textContent = originalText;

                const image = canvas.toDataURL("image/png");
                const link = document.createElement("a");
                link.href = image;
                link.download = `leaderboard.png`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }).catch(err => {
                shareBtn.style.display = originalDisplay;
                shareBtn.classList.remove("btn-loading");
                shareBtn.disabled = false;
                shareBtn.textContent = originalText;
                console.error("Error generating screenshot: ", err);
                alert("❌ حدث خطأ أثناء التقاط الصورة.");
            });
        });
    }

    // Card stagger animations (banners + table rows)
    if (window.FantasyMotion) {
        window.FantasyMotion.cardStaggerIn(".banner-card", 0.05);
        window.FantasyMotion.cardStaggerIn("#leaderboard-body tr", 0.02);
    }
});
