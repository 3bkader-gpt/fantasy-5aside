document.addEventListener('DOMContentLoaded', function () {
    const matchesConfig = document.getElementById('matches-config');
    if (matchesConfig) {
        const config = matchesConfig.dataset;
        window.LEAGUE_SLUG = config.slug || '';
        const isAdmin = config.isAdmin === 'true';
        if (isAdmin) {
            try {
                const matchesDataElement = document.getElementById('matches-data-json');
                window.MATCHES_DATA = matchesDataElement ? JSON.parse(matchesDataElement.textContent) : {};
            } catch (e) {
                console.error("Match data parsing error:", e);
                window.MATCHES_DATA = {};
            }
        }
    }

    function getCsrfHeader() {
        const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        return token ? { 'X-CSRF-Token': token } : {};
    }

    // =========================================
    // Delete Match Logic
    // =========================================
    document.querySelectorAll('.delete-match-btn').forEach(btn => {
        btn.addEventListener('click', async function () {
            const matchId = this.getAttribute('data-match-id');
            const ok = window.confirm(`⚠️ هل أنت متأكد من حذف المباراة رقم #${matchId} نهائياً؟`);
            if (!ok) return;

            try {
                const leagueSlug = window.LEAGUE_SLUG;

                const response = await fetch(`/l/${leagueSlug}/admin/match/${matchId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        ...getCsrfHeader()
                    },
                    body: JSON.stringify({})
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
            const defContribCheck = row.querySelector('.defensive-contrib-check');

            if (isGK) {
                savesInput.disabled = false;
                cleanSheetCheck.disabled = false;
                savesInput.style.opacity = '1';
                cleanSheetCheck.style.opacity = '1';
                savesInput.required = true;
                // الحارس نفسه لا يمكن اعتباره مساهمة دفاعية
                if (defContribCheck) {
                    defContribCheck.checked = false;
                }
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
                const ownGoalsInput = row.querySelector('.own-goals-input');
                if (ownGoalsInput) ownGoalsInput.value = stat.own_goals ?? 0;

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

                const defContribCheck = row.querySelector('.defensive-contrib-check');
                if (defContribCheck) {
                    defContribCheck.checked = !!stat.defensive_contribution;
                    // لا تسمح بتفعيلها على الحارس نفسه
                    if (stat.is_gk) {
                        defContribCheck.checked = false;
                    }
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
                    const defContribCheck = row.querySelector('.defensive-contrib-check');
                    let goalsConceded = 0;

                    if (isGk) {
                        goalsConceded = opponentGoals || 0;
                    }

                    const statData = {
                        player_name: playerName,
                        team: teamCode,
                        goals: parseInt(row.querySelector('.goals-input').value) || 0,
                        assists: parseInt(row.querySelector('.assists-input').value) || 0,
                        own_goals: parseInt(row.querySelector('.own-goals-input')?.value) || 0,
                        saves: parseInt(row.querySelector('.saves-input').value) || 0,
                        goals_conceded: goalsConceded,
                        is_gk: isGk,
                        clean_sheet: row.querySelector('.clean-sheet-check').checked,
                        defensive_contribution: defContribCheck ? defContribCheck.checked : false
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
                stats: stats
            };

            const leagueSlug = window.LEAGUE_SLUG;

            try {
                this.innerHTML = "جاري الحفظ... ⏳";
                this.disabled = true;

                const response = await fetch(`/l/${leagueSlug}/admin/match/${currentEditMatchId}/edit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', ...getCsrfHeader() },
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
            const matchNumber = this.getAttribute('data-match-number') || matchId;

            let action = round === 0 ? "فتح التصويت" : `إغلاق الجولة ${round}`;
            let endpoint = round === 0 ? `/api/voting/${leagueSlug}/open/${matchId}` : `/api/voting/${leagueSlug}/close/${matchId}`;

            const ok = window.confirm(`هل أنت متأكد من ${action} للمباراة رقم #${matchNumber}؟`);
            if (!ok) return;

            try {
                this.disabled = true;
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', ...getCsrfHeader() },
                    body: JSON.stringify({})
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

    // =========================================
    // Match media upload & delete
    // =========================================
    document.querySelectorAll('.upload-media-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const matchId = this.getAttribute('data-match-id');
            const input = document.querySelector(`.match-media-input[data-match-id="${matchId}"]`);
            if (input) {
                input.click();
            }
        });
    });

    document.querySelectorAll('.match-media-input').forEach(input => {
        input.addEventListener('change', async function () {
            const matchId = this.getAttribute('data-match-id');
            if (!this.files || this.files.length === 0) return;

            const formData = new FormData();
            Array.from(this.files).forEach(file => {
                formData.append('files', file);
            });

            try {
                const resp = await fetch(`/l/${window.LEAGUE_SLUG}/match/${matchId}/media`, {
                    method: 'POST',
                    headers: {
                        ...getCsrfHeader(),
                    },
                    body: formData,
                });
                const data = await resp.json();
                if (!resp.ok || !data.success) {
                    alert(data.detail || 'فشل رفع الصور. تأكد من أن الملفات صور أقل من 5MB.');
                    return;
                }
                alert('✅ تم رفع الصور بنجاح.');
                window.location.reload();
            } catch (err) {
                console.error('Error uploading media:', err);
                alert('❌ حدث خطأ أثناء الاتصال بالخادم.');
            } finally {
                this.value = '';
            }
        });
    });

    document.querySelectorAll('.delete-media-btn').forEach(btn => {
        btn.addEventListener('click', async function () {
            const mediaId = this.getAttribute('data-media-id');
            if (!confirm('⚠️ هل أنت متأكد من حذف هذه الصورة؟')) {
                return;
            }
            try {
                const resp = await fetch(`/l/${window.LEAGUE_SLUG}/media/${mediaId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        ...getCsrfHeader(),
                    },
                    body: JSON.stringify({}),
                });
                const data = await resp.json();
                if (!resp.ok || !data.success) {
                    alert(data.detail || 'تعذر حذف الصورة.');
                    return;
                }
                alert('✅ تم حذف الصورة بنجاح.');
                window.location.reload();
            } catch (err) {
                console.error('Error deleting media:', err);
                alert('❌ حدث خطأ أثناء الاتصال بالخادم.');
            }
        });
    });
});
