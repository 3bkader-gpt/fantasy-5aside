document.addEventListener('DOMContentLoaded', function () {

    // =========================================
    // Delete Match Logic
    // =========================================
    document.querySelectorAll('.delete-match-btn').forEach(btn => {
        btn.addEventListener('click', async function () {
            const matchId = this.getAttribute('data-match-id');
            const password = await showPromptModal("حذف مباراة", "أدخل كلمة مرور الآدمن لحذف المباراة رقم #" + matchId + " :");
            if (!password) return;

            try {
                const leagueSlug = window.LEAGUE_SLUG;

                const response = await fetch(`/l/${leagueSlug}/admin/match/${matchId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ admin_password: password })
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

    // =========================================
    // Share Match Logic
    // =========================================
    document.querySelectorAll('.share-match-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const targetId = this.getAttribute('data-target');
            const captureArea = document.querySelector(targetId);

            if (captureArea) {
                const deleteBtn = captureArea.querySelector('.delete-match-btn');
                const shareBtn = captureArea.querySelector('.share-match-btn');
                const editBtn = captureArea.querySelector('.edit-match-btn');

                if (deleteBtn) deleteBtn.style.display = 'none';
                if (shareBtn) shareBtn.style.display = 'none';
                if (editBtn) editBtn.style.display = 'none';

                const isDark = document.body.classList.contains("dark-mode");
                const bgColor = isDark ? "#2a2a2a" : "#ffffff";

                html2canvas(captureArea, {
                    backgroundColor: bgColor,
                    scale: 2,
                    useCORS: true
                }).then(canvas => {
                    if (deleteBtn) deleteBtn.style.display = '';
                    if (shareBtn) shareBtn.style.display = '';
                    if (editBtn) editBtn.style.display = '';

                    const image = canvas.toDataURL("image/png");
                    const link = document.createElement("a");
                    link.href = image;
                    const mId = targetId.split('-')[1];
                    const leagueSlug = window.LEAGUE_SLUG || 'unknown';
                    link.download = `match_${mId}_${leagueSlug}.png`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                }).catch(err => {
                    if (deleteBtn) deleteBtn.style.display = '';
                    if (shareBtn) shareBtn.style.display = '';
                    if (editBtn) editBtn.style.display = '';
                    console.error("Error generating screenshot: ", err);
                    alert("❌ حدث خطأ أثناء التقاط الصورة.");
                });
            }
        });
    });

    // =========================================
    // Edit Match Logic
    // =========================================
    const editModal = document.getElementById('editMatchModal');
    const closeEditModalBtn = editModal ? editModal.querySelector('.close-modal') : null;
    let currentEditMatchId = null;

    if (closeEditModalBtn) {
        closeEditModalBtn.addEventListener('click', () => {
            if (editModal) editModal.classList.remove('active');
        });
    }

    // Helper: Create a new player row in the edit modal
    function addEditPlayerRow(team) {
        const template = document.getElementById('edit-player-row-template');
        const row = template.content.cloneNode(true).querySelector('tr');

        row.querySelector('.is-gk-check').addEventListener('change', function () {
            const isGK = this.checked;
            const savesInput = row.querySelector('.saves-input');
            const cleanSheetCheck = row.querySelector('.clean-sheet-check');

            if (isGK) {
                savesInput.disabled = false;
                cleanSheetCheck.disabled = false;
                savesInput.style.opacity = '1';
                cleanSheetCheck.style.opacity = '1';
                savesInput.required = true;
            } else {
                savesInput.disabled = true;
                cleanSheetCheck.disabled = true;
                savesInput.style.opacity = '0.5';
                cleanSheetCheck.style.opacity = '0.5';
                savesInput.value = '0';
                cleanSheetCheck.checked = false;
                savesInput.required = false;
            }
        });

        row.querySelector('.remove-row-btn').addEventListener('click', function () {
            this.closest('tr').remove();
        });

        row.querySelector('.swap-row-btn').addEventListener('click', function () {
            const tr = this.closest('tr');
            const currentTbody = tr.parentElement;
            const targetTbodyId = currentTbody.id === 'edit-team-a-body' ? 'edit-team-b-body' : 'edit-team-a-body';
            document.getElementById(targetTbodyId).appendChild(tr);
        });

        document.getElementById(`edit-team-${team}-body`).appendChild(row);
        return document.getElementById(`edit-team-${team}-body`).lastElementChild;
    }

    // Bind Edit Match Buttons — reads from window.MATCHES_DATA (injected by Jinja template)
    document.querySelectorAll('.edit-match-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const matchId = this.getAttribute('data-match-id');
            const matchData = window.MATCHES_DATA ? window.MATCHES_DATA[matchId] : null;

            if (!matchData) {
                alert('تعذر تحميل بيانات المباراة للتعديل.');
                return;
            }

            currentEditMatchId = matchId;
            document.getElementById('edit-match-id-display').textContent = `#${matchId}`;

            // Populate Team Names
            document.getElementById('edit_team_a_name').value = matchData.team_a_name;
            document.getElementById('edit_team_b_name').value = matchData.team_b_name;
            document.querySelector('.team-a-label').textContent = matchData.team_a_name;
            document.querySelector('.team-b-label').textContent = matchData.team_b_name;

            // Clear existing rows
            document.getElementById('edit-team-a-body').innerHTML = '';
            document.getElementById('edit-team-b-body').innerHTML = '';

            // Populate Stats from pre-loaded data
            (matchData.stats || []).forEach(stat => {
                const teamKey = (stat.team || 'A').toLowerCase();
                const row = addEditPlayerRow(teamKey);

                row.querySelector('.player-name-input').value = stat.player_name || '';
                row.querySelector('.goals-input').value = stat.goals ?? 0;
                row.querySelector('.assists-input').value = stat.assists ?? 0;

                if (stat.is_gk) {
                    row.querySelector('.is-gk-check').checked = true;

                    const savesInput = row.querySelector('.saves-input');
                    savesInput.disabled = false;
                    savesInput.style.opacity = '1';
                    savesInput.value = stat.saves ?? 0;

                    const cleanSheetCheck = row.querySelector('.clean-sheet-check');
                    cleanSheetCheck.disabled = false;
                    cleanSheetCheck.style.opacity = '1';
                    cleanSheetCheck.checked = !!stat.clean_sheet;
                } else {
                    row.querySelector('.saves-input').disabled = true;
                    row.querySelector('.clean-sheet-check').disabled = true;
                }
            });

            document.getElementById('edit_admin_password').value = '';
            if (editModal) editModal.classList.add('active');
        });
    });

    // Handle adding new rows
    const editAddA = document.getElementById('edit-add-player-a-btn');
    const editAddB = document.getElementById('edit-add-player-b-btn');
    if (editAddA) editAddA.addEventListener('click', () => addEditPlayerRow('a'));
    if (editAddB) editAddB.addEventListener('click', () => addEditPlayerRow('b'));

    // Dynamic Team Name Updates
    const editTeamANameInput = document.getElementById('edit_team_a_name');
    const editTeamBNameInput = document.getElementById('edit_team_b_name');
    if (editTeamANameInput) {
        editTeamANameInput.addEventListener('input', function () {
            document.querySelector('.team-a-label').textContent = this.value || "فريق أ";
        });
    }
    if (editTeamBNameInput) {
        editTeamBNameInput.addEventListener('input', function () {
            document.querySelector('.team-b-label').textContent = this.value || "فريق ب";
        });
    }

    // Save Edit functionality
    const saveEditBtn = document.getElementById('save-edit-match-btn');
    if (saveEditBtn) {
        saveEditBtn.addEventListener('click', async function () {
            const adminPassword = document.getElementById('edit_admin_password').value;
            if (!adminPassword) {
                alert("يرجى إدخال كلمة سر الإدارة");
                return;
            }

            const teamAName = document.getElementById('edit_team_a_name').value.trim() || 'فريق أ';
            const teamBName = document.getElementById('edit_team_b_name').value.trim() || 'فريق ب';

            const stats = [];

            const rowsA = Array.from(document.querySelectorAll(`#edit-team-a-body tr`));
            const rowsB = Array.from(document.querySelectorAll(`#edit-team-b-body tr`));

            const teamAGoalsTotal = rowsA.reduce((sum, row) => {
                return sum + (parseInt(row.querySelector('.goals-input').value) || 0);
            }, 0);
            const teamBGoalsTotal = rowsB.reduce((sum, row) => {
                return sum + (parseInt(row.querySelector('.goals-input').value) || 0);
            }, 0);

            const collectStats = (rows, teamCode, opponentGoals) => {
                rows.forEach(row => {
                    const playerName = row.querySelector('.player-name-input').value.trim();
                    if (!playerName) return;

                    const isGk = row.querySelector('.is-gk-check').checked;
                    let goalsConceded = 0;

                    if (isGk) {
                        goalsConceded = opponentGoals || 0;
                    }

                    const statData = {
                        player_name: playerName,
                        team: teamCode,
                        goals: parseInt(row.querySelector('.goals-input').value) || 0,
                        assists: parseInt(row.querySelector('.assists-input').value) || 0,
                        saves: parseInt(row.querySelector('.saves-input').value) || 0,
                        goals_conceded: goalsConceded,
                        is_gk: isGk,
                        clean_sheet: row.querySelector('.clean-sheet-check').checked
                    };
                    stats.push(statData);
                });
            };

            collectStats(rowsA, 'A', teamBGoalsTotal);
            collectStats(rowsB, 'B', teamAGoalsTotal);

            if (stats.length === 0) {
                alert("يجب إضافة لاعبين");
                return;
            }

            const payload = {
                team_a_name: teamAName,
                team_b_name: teamBName,
                team_a_score: 0,
                team_b_score: 0,
                stats: stats,
                admin_password: adminPassword
            };

            const leagueSlug = window.LEAGUE_SLUG;

            try {
                this.innerHTML = "جاري الحفظ... ⏳";
                this.disabled = true;

                const response = await fetch(`/l/${leagueSlug}/admin/match/${currentEditMatchId}/edit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const result = await response.json();
                if (response.ok) {
                    showToast('تم حفظ التعديلات بنجاح!', 'success');
                    setTimeout(() => location.reload(), 1000);
                } else {
                    showToast(result.detail || 'حدث خطأ أثناء الحفظ', 'error');
                }
            } catch (error) {
                showToast('خطأ في الاتصال بالخادم', 'error');
            } finally {
                this.innerHTML = "💾 حفظ التعديلات";
                this.disabled = false;
            }
        });
    }

    // =========================================
    // Voting Round Control Logic
    // =========================================
    document.querySelectorAll('.voting-btn').forEach(btn => {
        btn.addEventListener('click', async function () {
            const matchId = this.getAttribute('data-match-id');
            const round = parseInt(this.getAttribute('data-round'));
            const leagueSlug = window.LEAGUE_SLUG;

            let action = round === 0 ? "فتح التصويت" : `إغلاق الجولة ${round}`;
            let endpoint = round === 0 ? `/api/voting/${leagueSlug}/open/${matchId}` : `/api/voting/${leagueSlug}/close/${matchId}`;

            const password = await showPromptModal(action, `أدخل كلمة مرور الآدمن لـ ${action} للمباراة رقم #${matchId}:`);
            if (!password) return;

            try {
                this.disabled = true;
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ admin_password: password })
                });

                const result = await response.json();
                if (response.ok) {
                    showToast(result.message || 'تمت العملية بنجاح!', 'success');
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showToast(result.detail || 'حدث خطأ.', 'error');
                    this.disabled = false;
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('حدث خطأ أثناء الاتصال بالخادم.', 'error');
                this.disabled = false;
            }
        });
    });
    // Initialize voting button colors
    document.querySelectorAll('.voting-btn').forEach(btn => {
        const isOpen = btn.getAttribute('data-is-open') === 'true';
        btn.style.backgroundColor = isOpen ? '#f39c12' : '#27ae60';
    });
});
