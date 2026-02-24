document.addEventListener("DOMContentLoaded", function () {
    const tabs = document.querySelectorAll(".tab-btn");
    const tbody = document.getElementById("leaderboard-body");

    if (tabs.length === 0 || !tbody) return;

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            // Update active state
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");

            // Get sort metric
            const sortMetric = tab.getAttribute("data-sort");

            // Sort rows
            const rows = Array.from(tbody.querySelectorAll("tr"));
            rows.sort((a, b) => {
                const valA = parseInt(a.getAttribute(`data-${sortMetric}`)) || 0;
                const valB = parseInt(b.getAttribute(`data-${sortMetric}`)) || 0;
                // If sorting by metric is tied, sort by points implicitly (optional fallback)
                if (valB === valA && sortMetric !== 'points') {
                    const pointsA = parseInt(a.getAttribute('data-points')) || 0;
                    const pointsB = parseInt(b.getAttribute('data-points')) || 0;
                    return pointsB - pointsA;
                }
                return valB - valA;
            });

            // Re-append sorted rows and update ranks dynamically
            tbody.innerHTML = "";
            rows.forEach((row, index) => {
                const rankText = index + 1;
                const rankPrefix = rankText === 1 ? '🥇' : rankText === 2 ? '🥈' : rankText === 3 ? '🥉' : '';

                // Update the visible rank column
                const rankCell = row.querySelector(".rank-col");
                if (rankCell) {
                    rankCell.innerHTML = `${rankText} ${rankPrefix}`;
                }

                // Keep the crown logic only for the first row
                const nameLink = row.querySelector("td[data-label='اللاعب']");
                if (nameLink) {
                    const existingCrown = nameLink.querySelector(".crown");
                    if (existingCrown) existingCrown.remove();
                    if (rankText === 1 && sortMetric === 'points') {
                        nameLink.insertAdjacentHTML('beforeend', '<span class="crown">👑</span>');
                    }
                }

                tbody.appendChild(row);
            });
        });
    });

    // Share Leaderboard Logic
    const shareBtn = document.getElementById("share-leaderboard");
    const captureArea = document.getElementById("capture-area");

    if (shareBtn && captureArea) {
        shareBtn.addEventListener("click", () => {
            const originalDisplay = shareBtn.style.display;
            shareBtn.style.display = "none"; // Hide button from canvas

            const isDark = document.body.classList.contains("dark-mode");
            const bgColor = isDark ? "#121212" : "#f4f7f6";

            html2canvas(captureArea, {
                backgroundColor: bgColor,
                scale: 2,
                useCORS: true
            }).then(canvas => {
                shareBtn.style.display = originalDisplay; // Restore button

                const image = canvas.toDataURL("image/png");
                const link = document.createElement("a");
                link.href = image;
                link.download = `leaderboard.png`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }).catch(err => {
                shareBtn.style.display = originalDisplay;
                console.error("Error generating screenshot: ", err);
                alert("❌ حدث خطأ أثناء التقاط الصورة.");
            });
        });
    }
});
