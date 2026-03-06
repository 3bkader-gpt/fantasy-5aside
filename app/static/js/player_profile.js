document.addEventListener("DOMContentLoaded", function () {
    const configEl = document.getElementById("player-page-config");
    const exportBtn = document.getElementById("export-player-card");
    if (!configEl || !exportBtn) return;

    const config = configEl.dataset;
    const leagueSlug = config.leagueSlug || "";
    const playerId = parseInt(config.playerId || "0", 10);
    const playerName = config.playerName || "player";

    exportBtn.addEventListener("click", function () {
        const cardContainer = document.getElementById("player-card-container");
        const card = document.getElementById("player-card");
        if (!cardContainer || !card) return;

        cardContainer.style.position = "fixed";
        cardContainer.style.left = "0";
        cardContainer.style.top = "0";
        cardContainer.style.zIndex = "-1";
        cardContainer.style.opacity = "1";

        html2canvas(card, {
            backgroundColor: null,
            scale: 2,
            useCORS: true,
            logging: false,
            width: 420,
        }).then(function (canvas) {
            cardContainer.style.position = "absolute";
            cardContainer.style.left = "-9999px";

            const link = document.createElement("a");
            link.download = `player_card_${playerName}.png`;
            link.href = canvas.toDataURL("image/png");
            link.click();
        }).catch(function (err) {
            cardContainer.style.position = "absolute";
            cardContainer.style.left = "-9999px";
            console.error("Card export failed:", err);
            alert("حدث خطأ أثناء إنشاء البطاقة");
        });
    });

    const deletePlayerBtn = document.getElementById("delete-player-btn");
    if (!deletePlayerBtn || !leagueSlug || !playerId) return;

    deletePlayerBtn.addEventListener("click", async function () {
        if (!confirm(`⚠️ هل أنت متأكد من حذف اللاعب "${playerName}" نهائياً؟\nسيتم مسح جميع إحصائياته من جميع المباريات والكؤوس.`)) {
            return;
        }

        const adminPassword = prompt(`يرجى إدخال كلمة سر الإدارة لتأكيد حذف "${playerName}":`);
        if (!adminPassword) return;

        try {
            const response = await fetch(`/l/${leagueSlug}/admin/player/${playerId}`, {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ admin_password: adminPassword }),
            });

            const result = await response.json();
            if (result.success) {
                alert("✅ تم حذف اللاعب بنجاح.");
                window.location.href = `/l/${leagueSlug}`;
            } else {
                alert(`❌ خطأ: ${result.detail || "تعذر حذف اللاعب."}`);
            }
        } catch (error) {
            console.error("Error deleting player:", error);
            alert("❌ حدث خطأ أثناء الاتصال بالخادم.");
        }
    });
});
