document.addEventListener('DOMContentLoaded', function () {
    // Delete Match Logic
    document.querySelectorAll('.delete-match-btn').forEach(btn => {
        btn.addEventListener('click', async function () {
            const matchId = this.getAttribute('data-match-id');
            const password = await showPromptModal("حذف مباراة", "أدخل كلمة مرور الآدمن لحذف المباراة رقم #" + matchId + " :");
            if (!password) return;

            try {
                const formData = new FormData();
                formData.append('password', password);

                const response = await fetch(`/admin/match/${matchId}`, {
                    method: 'DELETE',
                    body: formData
                });

                const result = await response.json();
                if (result.success) {
                    showToast('تم حذف المباراة بنجاح!', 'success');
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showToast(result.detail || 'حدث خطأ.', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('حدث خطأ أثناء الاتصال بالخادم.', 'error');
            }
        });
    });

    // Share Match Logic
    document.querySelectorAll('.share-match-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const targetId = this.getAttribute('data-target');
            const captureArea = document.querySelector(targetId);

            if (captureArea) {
                // Hide interactive buttons purely for the screenshot
                const deleteBtn = captureArea.querySelector('.delete-match-btn');
                const shareBtn = captureArea.querySelector('.share-match-btn');

                if (deleteBtn) deleteBtn.style.display = 'none';
                if (shareBtn) shareBtn.style.display = 'none';

                const isDark = document.body.classList.contains("dark-mode");
                const bgColor = isDark ? "#2a2a2a" : "#ffffff"; // matches card bg more closely

                html2canvas(captureArea, {
                    backgroundColor: bgColor,
                    scale: 2,
                    useCORS: true
                }).then(canvas => {
                    // Restore buttons
                    if (deleteBtn) deleteBtn.style.display = '';
                    if (shareBtn) shareBtn.style.display = '';

                    const image = canvas.toDataURL("image/png");
                    const link = document.createElement("a");
                    link.href = image;
                    // Extract match ID from targetId (e.g. #match-15)
                    const mId = targetId.split('-')[1];
                    const leagueSlug = window.LEAGUE_SLUG || 'unknown';
                    link.download = `match_${mId}_${leagueSlug}.png`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                }).catch(err => {
                    // Restore buttons in case of error too
                    if (deleteBtn) deleteBtn.style.display = '';
                    if (shareBtn) shareBtn.style.display = '';
                    console.error("Error generating screenshot: ", err);
                    alert("❌ حدث خطأ أثناء التقاط الصورة.");
                });
            }
        });
    });
});
