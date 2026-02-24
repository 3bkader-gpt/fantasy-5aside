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

        gkCheck.addEventListener('change', function () {
            savesInput.disabled = !this.checked;
            if (this.checked) {
                savesInput.style.backgroundColor = '';
                savesInput.style.opacity = '1';
                savesInput.focus();
            } else {
                savesInput.style.backgroundColor = '';
                savesInput.style.opacity = '0.5';
                savesInput.value = 0;
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
                clean_sheet: row.querySelector('.clean-sheet-check').checked,
                mvp: row.querySelector('.mvp-check').checked,
                is_captain: row.querySelector('.captain-check').checked
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
});
