document.addEventListener('DOMContentLoaded', function () {
    const teamABody = document.getElementById('team-a-body');
    const teamBBody = document.getElementById('team-b-body');
    const template = document.getElementById('player-row-template');

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
        const concededInput = clone.querySelector('.conceded-input');
        const cleanSheetCheck = clone.querySelector('.clean-sheet-check');

        gkCheck.addEventListener('change', function () {
            const isGK = this.checked;
            savesInput.disabled = !isGK;
            // Goals conceded for GK are auto-calculated from opponent goals, keep input read-only
            concededInput.disabled = true;
            cleanSheetCheck.disabled = !isGK;

            if (isGK) {
                savesInput.style.opacity = '1';
                concededInput.style.opacity = '1';
                cleanSheetCheck.style.opacity = '1';
                savesInput.focus();
            } else {
                savesInput.style.opacity = '0.5';
                concededInput.style.opacity = '0.5';
                cleanSheetCheck.style.opacity = '0.5';
                savesInput.value = 0;
                concededInput.value = 0;
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

    if (teamABody && teamBBody) {
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

        document.getElementById('add-player-a-btn').addEventListener('click', () => addPlayerRow(teamABody));
        document.getElementById('add-player-b-btn').addEventListener('click', () => addPlayerRow(teamBBody));

        document.getElementById('save-match-btn').addEventListener('click', async () => {
            const teamAName = document.getElementById('team_a_name').value.trim() || 'فريق أ';
            const teamBName = document.getElementById('team_b_name').value.trim() || 'فريق ب';
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
                // For goalkeepers, conceded goals = goals scored by the opponent team
                goalsConceded = opponentGoals || 0;
                const concededInput = row.querySelector('.conceded-input');
                if (concededInput) {
                    concededInput.value = goalsConceded;
                }
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
});
