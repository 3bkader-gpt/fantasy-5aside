document.addEventListener('DOMContentLoaded', function () {
    const teamABody = document.getElementById('team-a-body');
    const teamBBody = document.getElementById('team-b-body');
    const template = document.getElementById('player-row-template');
    const teamASelect = document.getElementById('team_a_select');
    const teamBSelect = document.getElementById('team_b_select');
    const teamANameInput = document.getElementById('team_a_name');
    const teamBNameInput = document.getElementById('team_b_name');

    // Function to add a new row
    function addPlayerRow(targetBody, player = null) {
        if (!template) return;
        const clone = template.content.cloneNode(true);
        const tr = clone.querySelector('tr');

        if (player) {
            tr.querySelector('.player-name-input').value = player.name;
            if (player.default_is_gk) {
                tr.querySelector('.is-gk-check').checked = true;
            }
        }

        // Remove
        clone.querySelector('.remove-row-btn').addEventListener('click', function () {
            this.closest('tr').remove();
        });

        // Swap
        clone.querySelector('.swap-row-btn').addEventListener('click', function () {
            const currentRow = this.closest('tr');
            if (currentRow.parentElement.id === 'team-a-body') {
                teamBBody.appendChild(currentRow);
            } else {
                teamABody.appendChild(currentRow);
            }
        });

        // GK logic
        const gkCheck = clone.querySelector('.is-gk-check');
        const savesInput = clone.querySelector('.saves-input');
        const cleanSheetCheck = clone.querySelector('.clean-sheet-check');

        gkCheck.addEventListener('change', function () {
            const isGK = this.checked;
            savesInput.disabled = !isGK;
            cleanSheetCheck.disabled = !isGK;

            if (isGK) {
                savesInput.style.opacity = '1';
                cleanSheetCheck.style.opacity = '1';
                savesInput.focus();
            } else {
                savesInput.style.opacity = '0.5';
                cleanSheetCheck.style.opacity = '0.5';
                savesInput.value = 0;
                cleanSheetCheck.checked = false;
            }
        });

        targetBody.appendChild(clone);

        // Trigger GK UI update if needed
        if (player && player.default_is_gk) {
            const isGkBox = tr.querySelector('.is-gk-check');
            if (isGkBox) isGkBox.dispatchEvent(new Event('change'));
        }
    }

    function getTeamById(id) {
        if (!window.LEAGUE_TEAMS) return null;
        return window.LEAGUE_TEAMS.find(t => String(t.id) === String(id)) || null;
    }

    function applyTeamNamesFromSelects() {
        if (!teamANameInput || !teamBNameInput) return;

        if (teamASelect) {
            const teamA = getTeamById(teamASelect.value);
            if (teamA) {
                teamANameInput.value = teamA.name;
            }
        }
        if (teamBSelect) {
            const teamB = getTeamById(teamBSelect.value);
            if (teamB) {
                teamBNameInput.value = teamB.name;
            }
        }
    }

    function populateBoardForRegisteredTeams() {
        if (!teamABody || !teamBBody) return;

        teamABody.innerHTML = '';
        teamBBody.innerHTML = '';

        const teamAId = teamASelect ? parseInt(teamASelect.value) || null : null;
        const teamBId = teamBSelect ? parseInt(teamBSelect.value) || null : null;
        const players = window.LEAGUE_PLAYERS || [];

        if (teamAId) {
            players
                .filter(p => p.team_id === teamAId)
                .forEach(p => addPlayerRow(teamABody, p));
        }
        if (teamBId) {
            players
                .filter(p => p.team_id === teamBId)
                .forEach(p => addPlayerRow(teamBBody, p));
        }

        // إذا مافيش لاعيبة في الفريق لسبب ما، نديك شوية صفوف فاضية تقدر تكتب فيهم
        if (teamABody.querySelectorAll('.player-row').length === 0) {
            for (let i = 0; i < 5; i++) addPlayerRow(teamABody);
        }
        if (teamBBody.querySelectorAll('.player-row').length === 0) {
            for (let i = 0; i < 5; i++) addPlayerRow(teamBBody);
        }
    }

    if (teamABody && teamBBody) {
        const hasRegisteredTeams = Array.isArray(window.LEAGUE_TEAMS) && window.LEAGUE_TEAMS.length >= 2 && teamASelect && teamBSelect;

        if (hasRegisteredTeams) {
            applyTeamNamesFromSelects();
            populateBoardForRegisteredTeams();

            teamASelect.addEventListener('change', () => {
                applyTeamNamesFromSelects();
                populateBoardForRegisteredTeams();
            });
            teamBSelect.addEventListener('change', () => {
                applyTeamNamesFromSelects();
                populateBoardForRegisteredTeams();
            });
        } else {
            if (window.LEAGUE_PLAYERS && window.LEAGUE_PLAYERS.length > 0) {
                window.LEAGUE_PLAYERS.forEach(player => {
                    const targetBody = player.team === 'B' ? teamBBody : teamABody;
                    addPlayerRow(targetBody, player);
                });
            } else {
                // Add 5 initial rows for each team if no players
                for (let i = 0; i < 5; i++) {
                    addPlayerRow(teamABody);
                    addPlayerRow(teamBBody);
                }
            }
        }

        document.getElementById('add-player-a-btn').addEventListener('click', () => addPlayerRow(teamABody));
        document.getElementById('add-player-b-btn').addEventListener('click', () => addPlayerRow(teamBBody));

        document.getElementById('save-match-btn').addEventListener('click', async () => {
            const teamAName = document.getElementById('team_a_name').value.trim() || (window.TEAM_A_LABEL || 'فريق أ');
            const teamBName = document.getElementById('team_b_name').value.trim() || (window.TEAM_B_LABEL || 'فريق ب');
            const stats = [];

            // Parse rows
            const rowsA = Array.from(teamABody.querySelectorAll('.player-row'));
            const rowsB = Array.from(teamBBody.querySelectorAll('.player-row'));

            // Compute team goals (used to auto-set GK \"عليه\")
            const teamAGoalsTotal = rowsA.reduce((sum, row) => {
                return sum + (parseInt(row.querySelector('.goals-input').value) || 0);
            }, 0);
            const teamBGoalsTotal = rowsB.reduce((sum, row) => {
                return sum + (parseInt(row.querySelector('.goals-input').value) || 0);
            }, 0);

            // Parse Team A (GK conceded = goals of Team B)
            rowsA.forEach(row => collectRowStats(row, 'A', stats, teamBGoalsTotal));

            // Parse Team B (GK conceded = goals of Team A)
            rowsB.forEach(row => collectRowStats(row, 'B', stats, teamAGoalsTotal));

            if (stats.length === 0) {
                alert('⚠️ يرجى إدخال بيانات لاعب واحد على الأقل.');
                return;
            }

            const payload = {
                team_a_name: teamAName,
                team_b_name: teamBName,
                stats: stats
            };

            // Attach team IDs when the league uses registered teams
            if (window.LEAGUE_TEAMS && window.LEAGUE_TEAMS.length >= 2) {
                const teamASelect = document.getElementById('team_a_select');
                const teamBSelect = document.getElementById('team_b_select');
                if (teamASelect && teamBSelect) {
                    payload.team_a_id = parseInt(teamASelect.value) || null;
                    payload.team_b_id = parseInt(teamBSelect.value) || null;
                }
            }

            try {
                const response = await fetch(`/l/${window.LEAGUE_SLUG}/admin/match`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data.season_ended) {
                        alert('🎉 تم اكتمال 4 مباريات وتم إنهاء الموسم بنجاح وتوزيع الأوسمة وتصفير النقاط! 🏆\nبدأ الموسم الجديد تلقائياً الآن.');
                    } else {
                        alert('✅ تم حفظ المباراة بنجاح وإحتساب النقاط تلقائياً لكل فريق!');
                    }
                    window.location.reload();
                } else {
                    const errorData = await response.json();
                    alert('❌ حدث خطأ: ' + (errorData.detail || 'Unknown error'));
                }
            } catch (error) {
                console.error('Error:', error);
                alert('❌ تعذر الاتصال بالخادم.');
            }
        });
    }

    function collectRowStats(row, teamIdentifier, statsArray, opponentGoals) {
        const nameInput = row.querySelector('.player-name-input');
        const name = nameInput.value.trim();

        if (name) {
            const isGk = row.querySelector('.is-gk-check').checked;
            let goalsConceded = 0;
            let cleanSheet = row.querySelector('.clean-sheet-check').checked;

            if (isGk) {
                goalsConceded = opponentGoals || 0;
            }

            // Apply new Clean Sheet rule: GK conceding 6 or fewer goals gets a clean sheet automatically
            if (isGk && goalsConceded <= 6) {
                cleanSheet = true;
            }

            statsArray.push({
                player_name: name,
                team: teamIdentifier,
                goals: parseInt(row.querySelector('.goals-input').value) || 0,
                assists: parseInt(row.querySelector('.assists-input').value) || 0,
                own_goals: parseInt(row.querySelector('.own-goals-input').value) || 0,
                saves: parseInt(row.querySelector('.saves-input').value) || 0,
                goals_conceded: goalsConceded,
                is_gk: isGk,
                clean_sheet: cleanSheet
            });
        }
    }

    // Delete League Logic
    const deleteBtn = document.querySelector('.delete-league-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', async function () {
            const slug = this.getAttribute('data-league-slug');
            if (!confirm("⚠️ هل أنت متأكد من حذف الدوري نهائياً؟ سيتم مسح جميع البيانات ولا يمكن التراجع عن ذلك.")) return;

            try {
                const response = await fetch(`/l/${slug}/admin/settings/delete`, {
                    method: 'POST'
                });

                const result = await response.json();
                if (result.success && result.redirect_url) {
                    showToast('تم حذف الدوري بنجاح. جاري التوجيه...', 'success');
                    setTimeout(() => window.location.href = result.redirect_url, 1500);
                } else {
                    showToast(result.detail || 'حدث خطأ أثناء الحذف.', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('حدث خطأ أثناء الاتصال بالخادم.', 'error');
            }
        });
    }

    // Player Deletion
    document.querySelectorAll('.delete-player-btn').forEach(btn => {
        btn.addEventListener('click', async function () {
            const playerId = this.getAttribute('data-player-id');
            const playerName = this.getAttribute('data-player-name');

            if (!confirm(`⚠️ هل أنت متأكد من حذف اللاعب "${playerName}" نهائياً؟\nسيتم مسح جميع إحصائياته من جميع المباريات والكؤوس.`)) {
                return;
            }

            try {
                const response = await fetch(`/l/${window.LEAGUE_SLUG}/admin/player/${playerId}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });

                const result = await response.json();
                if (result.success) {
                    alert('✅ تم حذف اللاعب بنجاح.');
                    location.reload();
                } else {
                    alert('❌ خطأ: ' + (result.detail || 'تعذر حذف اللاعب.'));
                }
            } catch (error) {
                console.error('Error deleting player:', error);
                alert('❌ حدث خطأ أثناء الاتصال بالخادم.');
            }
        });
    });

    // Player Name Editing
    document.querySelectorAll('.edit-player-btn').forEach(btn => {
        btn.addEventListener('click', async function () {
            const playerId = this.getAttribute('data-player-id');
            const currentName = this.getAttribute('data-player-name');

            const newName = prompt(`تعديل اسم اللاعب "${currentName}":`, currentName);

            if (newName === null) return; // Cancelled
            const trimmedName = newName.trim();
            if (!trimmedName || trimmedName === currentName) return;

            try {
                const response = await fetch(`/l/${window.LEAGUE_SLUG}/admin/player/${playerId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: trimmedName })
                });

                const result = await response.json();
                if (result.success) {
                    alert('✅ تم تحديث اسم اللاعب بنجاح.');
                    location.reload();
                } else {
                    alert('❌ خطأ: ' + (result.detail || 'تعذر تحديث الاسم.'));
                }
            } catch (error) {
                console.error('Error updating player name:', error);
                alert('❌ حدث خطأ أثناء الاتصال بالخادم.');
            }
        });
    });

    // Delete Team
    document.querySelectorAll('.delete-team-btn').forEach(btn => {
        btn.addEventListener('click', async function () {
            const teamId = this.getAttribute('data-team-id');
            const teamName = this.getAttribute('data-team-name');
            const playerCount = parseInt(this.getAttribute('data-player-count') || '0');

            if (playerCount > 0) {
                alert(`❌ لا يمكن حذف فريق "${teamName}" لأن هناك ${playerCount} لاعب مرتبط به.\nيجب نقل اللاعبين لفريق آخر أولاً.`);
                return;
            }

            if (!confirm(`⚠️ هل أنت متأكد من حذف فريق "${teamName}" نهائياً؟`)) return;

            try {
                const response = await fetch(`/l/${window.LEAGUE_SLUG}/admin/team/${teamId}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });

                const result = await response.json();
                if (result.success) {
                    alert('✅ تم حذف الفريق بنجاح.');
                    location.reload();
                } else {
                    alert('❌ خطأ: ' + (result.detail || 'تعذر حذف الفريق.'));
                }
            } catch (error) {
                console.error('Error deleting team:', error);
                alert('❌ حدث خطأ أثناء الاتصال بالخادم.');
            }
        });
    });
});

// ─── Team Creation: Player Assignment Helpers ──────────────────────────────

function filterPlayerList(query) {
    const items = document.querySelectorAll('.player-assign-item');
    const normalized = query.trim().toLowerCase();
    items.forEach(function (label) {
        const name = label.querySelector('span').textContent.trim().toLowerCase();
        label.style.display = name.includes(normalized) ? '' : 'none';
    });
}

// Update selected count when checkboxes change
document.addEventListener('change', function (e) {
    if (e.target && e.target.name === 'player_ids') {
        const total = document.querySelectorAll('input[name="player_ids"]:checked').length;
        const counter = document.getElementById('selected-count');
        if (counter) counter.textContent = total;
    }
});
