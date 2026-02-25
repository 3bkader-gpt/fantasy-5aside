document.addEventListener('DOMContentLoaded', function () {
    const teamABody = document.getElementById('team-a-body');
    const teamBBody = document.getElementById('team-b-body');
    const template = document.getElementById('player-row-template');

    // Function to add a new row
    function addPlayerRow(targetBody) {
        if (!template) return;
        const clone = template.content.cloneNode(true);
        const tr = clone.querySelector('tr');

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
            concededInput.disabled = !isGK;
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
    }

    if (teamABody && teamBBody) {
        // Add 5 initial rows for each team
        for (let i = 0; i < 5; i++) {
            addPlayerRow(teamABody);
            addPlayerRow(teamBBody);
        }

        document.getElementById('add-player-a-btn').addEventListener('click', () => addPlayerRow(teamABody));
        document.getElementById('add-player-b-btn').addEventListener('click', () => addPlayerRow(teamBBody));

        document.getElementById('save-match-btn').addEventListener('click', async () => {
            const adminPassword = document.getElementById('admin_password').value;
            if (!adminPassword) {
                alert('⚠️ يرجى إدخال كلمة سر الإدارة الخاص بالدوري.');
                return;
            }

            const teamAName = document.getElementById('team_a_name').value.trim() || 'فريق أ';
            const teamBName = document.getElementById('team_b_name').value.trim() || 'فريق ب';
            const stats = [];

            // Parse Team A
            const rowsA = teamABody.querySelectorAll('.player-row');
            rowsA.forEach(row => collectRowStats(row, 'A', stats));

            // Parse Team B
            const rowsB = teamBBody.querySelectorAll('.player-row');
            rowsB.forEach(row => collectRowStats(row, 'B', stats));

            if (stats.length === 0) {
                alert('⚠️ يرجى إدخال بيانات لاعب واحد على الأقل.');
                return;
            }

            const payload = {
                team_a_name: teamAName,
                team_b_name: teamBName,
                stats: stats,
                admin_password: adminPassword
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
                    alert('✅ تم حفظ المباراة بنجاح وإحتساب النقاط تلقائياً لكل فريق!');
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

    function collectRowStats(row, teamIdentifier, statsArray) {
        const nameInput = row.querySelector('.player-name-input');
        const name = nameInput.value.trim();

        if (name) {
            statsArray.push({
                player_name: name,
                team: teamIdentifier,
                goals: parseInt(row.querySelector('.goals-input').value) || 0,
                assists: parseInt(row.querySelector('.assists-input').value) || 0,
                saves: parseInt(row.querySelector('.saves-input').value) || 0,
                goals_conceded: parseInt(row.querySelector('.conceded-input').value) || 0,
                is_gk: row.querySelector('.is-gk-check').checked,
                clean_sheet: row.querySelector('.clean-sheet-check').checked
            });
        }
    }

    // Delete League Logic
    const deleteBtn = document.querySelector('.delete-league-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', async function () {
            const slug = this.getAttribute('data-league-slug');
            const password = await showPromptModal("حذف الدوري نهائياً", "أدخل كلمة مرور الآدمن لتأكيد الحذف النهائي ولا يمكن التراجع عن ذلك:");
            if (!password) return;

            try {
                const formData = new FormData();
                formData.append('admin_password', password);

                const response = await fetch(`/l/${slug}/admin/settings/delete`, {
                    method: 'POST',
                    body: formData
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

            const adminPassword = prompt('يرجى إدخال كلمة سر الإدارة لتأكيد الحذف:');
            if (!adminPassword) return;

            try {
                const response = await fetch(`/l/${window.LEAGUE_SLUG}/admin/player/${playerId}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ admin_password: adminPassword })
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
});
