document.addEventListener('DOMContentLoaded', function () {
    // =========================================
    // Points breakdown popover
    // =========================================
    const pointsPopover = document.getElementById('points-breakdown-popover');
    const pointsPopoverList = document.getElementById('points-breakdown-list');
    const pointsPopoverTitle = document.querySelector('.points-breakdown-player-name');
    const pointsCloseBtn = document.querySelector('.points-breakdown-close-btn');
    const pointsBackdrop = document.querySelector('.points-breakdown-backdrop');

    function openPointsBreakdown(playerName, breakdown) {
        if (!pointsPopover || !pointsPopoverList || !pointsPopoverTitle) return;
        pointsPopoverTitle.textContent = playerName || 'اللاعب';
        pointsPopoverTitle.setAttribute('dir', 'rtl');
        pointsPopoverList.innerHTML = '';
        var raw = breakdown;
        if (raw == null || raw === '') {
            pointsPopoverList.innerHTML = '<li class="text-secondary">تعذر تحميل التفاصيل.</li>';
            pointsPopover.setAttribute('aria-hidden', 'false');
            pointsPopover.classList.add('active');
            return;
        }
        if (typeof raw === 'string' && raw.indexOf('&') !== -1) {
            var txt = document.createElement('textarea');
            txt.innerHTML = raw;
            raw = txt.value;
        }
        try {
            var items = typeof raw === 'string' ? JSON.parse(raw) : raw;
            if (!Array.isArray(items)) items = [];
            items.forEach(function (item) {
                var li = document.createElement('li');
                var sign = (item.points >= 0) ? '+' : '';
                li.textContent = item.label + ': ' + sign + item.points;
                li.classList.add(item.points < 0 ? 'points-breakdown-negative' : 'points-breakdown-positive');
                pointsPopoverList.appendChild(li);
            });
        } catch (e) {
            pointsPopoverList.innerHTML = '<li class="text-secondary">تعذر تحميل التفاصيل.</li>';
        }
        pointsPopover.setAttribute('aria-hidden', 'false');
        pointsPopover.classList.add('active');
    }

    function closePointsBreakdown() {
        if (pointsPopover) {
            pointsPopover.classList.remove('active');
            pointsPopover.setAttribute('aria-hidden', 'true');
        }
    }

    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.points-breakdown-btn');
        if (btn) {
            e.preventDefault();
            const playerName = btn.getAttribute('data-player-name');
            const breakdown = btn.getAttribute('data-breakdown');
            openPointsBreakdown(playerName, breakdown);
            return;
        }
        if (e.target === pointsBackdrop || e.target.closest('.points-breakdown-close-btn')) {
            closePointsBreakdown();
        }
    });

    if (pointsBackdrop) {
        pointsBackdrop.addEventListener('click', closePointsBreakdown);
    }
    if (pointsCloseBtn) {
        pointsCloseBtn.addEventListener('click', closePointsBreakdown);
    }

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

                const doCapture = () => {
                    var wasDark = document.body.classList.contains("dark-mode");

                    // Kill transitions so getComputedStyle returns final values immediately
                    var noTransition = document.createElement('style');
                    noTransition.textContent = '* { transition: none !important; }';
                    document.head.appendChild(noTransition);
                    document.body.offsetHeight; // force recalc

                    if (!wasDark) document.body.classList.add("dark-mode");
                    document.body.offsetHeight; // force recalc with dark-mode values

                    // Fix html2canvas: remove overflow clip + force explicit colors
                    var tweaks = [];
                    captureArea.querySelectorAll('.table-responsive').forEach(function(el) {
                        tweaks.push({ el: el, ov: el.style.overflow, ovx: el.style.overflowX });
                        el.style.overflow = 'visible';
                        el.style.overflowX = 'visible';
                    });
                    var allEls = captureArea.querySelectorAll('*');
                    var colorSaved = [];
                    for (var i = 0; i < allEls.length; i++) {
                        var el = allEls[i];
                        var cs = getComputedStyle(el);
                        colorSaved.push({ el: el, c: el.style.color, bg: el.style.backgroundColor });
                        el.style.color = cs.color;
                        el.style.backgroundColor = cs.backgroundColor;
                    }

                    function restore() {
                        for (var j = 0; j < colorSaved.length; j++) {
                            colorSaved[j].el.style.color = colorSaved[j].c;
                            colorSaved[j].el.style.backgroundColor = colorSaved[j].bg;
                        }
                        tweaks.forEach(function(t) { t.el.style.overflow = t.ov; t.el.style.overflowX = t.ovx; });
                        if (!wasDark) document.body.classList.remove("dark-mode");
                        captureArea.style.backgroundColor = oldBg;
                        document.head.removeChild(noTransition);
                    }

                    captureArea.scrollIntoView({ behavior: 'auto', block: 'center' });
                    const oldBg = captureArea.style.backgroundColor;
                    captureArea.style.backgroundColor = !wasDark ? "#020617" : getComputedStyle(document.body).backgroundColor;
                    return html2canvas(captureArea, {
                        backgroundColor: !wasDark ? "#020617" : (oldBg || "#020617"),
                        scale: 2,
                        useCORS: true,
                        logging: false,
                        windowWidth: Math.ceil(captureArea.scrollWidth),
                        windowHeight: Math.ceil(captureArea.scrollHeight)
                    }).then(function(c) { restore(); return c; },
                           function(e) { restore(); throw e; });
                };

                Promise.resolve()
                    .then(() => document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve())
                    .then(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))))
                    .then(() => new Promise(r => setTimeout(r, 150)))
                    .then(doCapture)
                    .then(canvas => {
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

    // Card stagger for match cards
    if (window.FantasyMotion) {
        window.FantasyMotion.cardStaggerIn(".matches-container .card", 0.04);
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

            // Populate Match Date (لتصحيح مباراة انتقلت لموسم خاطئ)
            const dateInput = document.getElementById('edit_match_date');
            if (dateInput && matchData.date) {
                dateInput.value = matchData.date.length >= 16 ? matchData.date.slice(0, 16) : matchData.date;
            } else if (dateInput) {
                dateInput.value = '';
            }

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

                    let cleanSheet = row.querySelector('.clean-sheet-check').checked;
                    if (isGk && goalsConceded <= 6) {
                        cleanSheet = true;
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
                        clean_sheet: cleanSheet,
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

            const dateInputVal = document.getElementById('edit_match_date') && document.getElementById('edit_match_date').value;
            if (dateInputVal) {
                payload.date = dateInputVal.length >= 16 ? dateInputVal.slice(0, 16) : dateInputVal;
            }

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
    function chooseAllowedVoters(matchId) {
        const card = document.getElementById(`match-${matchId}`);
        if (!card) return Promise.resolve([]);

        const rows = Array.from(card.querySelectorAll('tr.stat-row[data-player-id]'));
        const seen = new Set();
        const players = [];
        rows.forEach((row) => {
            const id = parseInt(row.getAttribute('data-player-id') || '0', 10);
            const nameEl = row.querySelector('td strong');
            const name = nameEl ? nameEl.textContent.trim() : '';
            if (id > 0 && name && !seen.has(id)) {
                seen.add(id);
                players.push({ id, name });
            }
        });

        if (!players.length) {
            return Promise.resolve([]);
        }

        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;display:flex;align-items:center;justify-content:center;padding:1rem;';

            const panel = document.createElement('div');
            panel.style.cssText = 'background:#0f172a;color:#f8fafc;border:1px solid rgba(148,163,184,.4);border-radius:12px;max-width:420px;width:100%;max-height:80vh;overflow:auto;padding:1rem;';
            panel.innerHTML = '<h3 style="margin:0 0 .75rem 0;font-size:1.05rem;">اختيار اللاعبين المسموح لهم بالتصويت</h3>' +
                              '<p style="margin:0 0 .75rem 0;color:#cbd5e1;font-size:.92rem;">اختر من يقدر يصوّت في هذه المباراة:</p>';

            const list = document.createElement('div');
            list.style.cssText = 'display:grid;gap:.45rem;margin-bottom:.9rem;';
            players.forEach((p) => {
                const item = document.createElement('label');
                item.style.cssText = 'display:flex;align-items:center;gap:.5rem;padding:.4rem .5rem;background:rgba(15,23,42,.55);border:1px solid rgba(148,163,184,.35);border-radius:8px;';
                item.innerHTML = `<input type="checkbox" data-player-id="${p.id}" checked> <span>${p.name}</span>`;
                list.appendChild(item);
            });
            panel.appendChild(list);

            const actions = document.createElement('div');
            actions.style.cssText = 'display:flex;justify-content:space-between;gap:.5rem;';

            const selectAllBtn = document.createElement('button');
            selectAllBtn.type = 'button';
            selectAllBtn.textContent = 'تحديد الكل';
            selectAllBtn.className = 'btn btn-outline btn-sm';

            const clearAllBtn = document.createElement('button');
            clearAllBtn.type = 'button';
            clearAllBtn.textContent = 'إلغاء الكل';
            clearAllBtn.className = 'btn btn-outline btn-sm';

            const okBtn = document.createElement('button');
            okBtn.type = 'button';
            okBtn.textContent = 'فتح التصويت';
            okBtn.className = 'btn btn-primary btn-sm';

            const cancelBtn = document.createElement('button');
            cancelBtn.type = 'button';
            cancelBtn.textContent = 'إلغاء';
            cancelBtn.className = 'btn btn-secondary btn-sm';

            const left = document.createElement('div');
            left.style.cssText = 'display:flex;gap:.4rem;';
            left.appendChild(selectAllBtn);
            left.appendChild(clearAllBtn);

            const right = document.createElement('div');
            right.style.cssText = 'display:flex;gap:.4rem;';
            right.appendChild(cancelBtn);
            right.appendChild(okBtn);

            actions.appendChild(left);
            actions.appendChild(right);
            panel.appendChild(actions);
            overlay.appendChild(panel);
            document.body.appendChild(overlay);

            function selectedIds() {
                return Array.from(panel.querySelectorAll('input[type="checkbox"][data-player-id]:checked'))
                    .map((i) => parseInt(i.getAttribute('data-player-id') || '0', 10))
                    .filter((n) => n > 0);
            }

            selectAllBtn.addEventListener('click', () => {
                panel.querySelectorAll('input[type="checkbox"]').forEach((i) => { i.checked = true; });
            });

            clearAllBtn.addEventListener('click', () => {
                panel.querySelectorAll('input[type="checkbox"]').forEach((i) => { i.checked = false; });
            });

            cancelBtn.addEventListener('click', () => {
                document.body.removeChild(overlay);
                resolve(null);
            });

            okBtn.addEventListener('click', () => {
                const ids = selectedIds();
                if (!ids.length) {
                    showToast('اختر لاعباً واحداً على الأقل', 'error');
                    return;
                }
                document.body.removeChild(overlay);
                resolve(ids);
            });
        });
    }

    document.querySelectorAll('.voting-btn').forEach(btn => {
        btn.addEventListener('click', async function () {
            const matchId = this.getAttribute('data-match-id');
            const round = parseInt(this.getAttribute('data-round'));
            const leagueSlug = window.LEAGUE_SLUG;
            const matchNumber = this.getAttribute('data-match-number') || matchId;

            let action = round === 0 ? "فتح التصويت" : `إغلاق الجولة ${round}`;
            let endpoint = round === 0 ? `/api/voting/${leagueSlug}/open/${matchId}` : `/api/voting/${leagueSlug}/close/${matchId}`;
            let payload = {};

            if (round === 0) {
                const selected = await chooseAllowedVoters(matchId);
                if (selected === null) return;
                payload = { allowed_voter_ids: selected };
            }

            const ok = window.confirm(`هل أنت متأكد من ${action} للمباراة رقم #${matchNumber}؟`);
            if (!ok) return;

            try {
                this.disabled = true;
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', ...getCsrfHeader() },
                    body: JSON.stringify(payload),
                    credentials: 'same-origin'
                });

                const result = await response.json();
                if (response.ok) {
                    showToast(result.message || 'تمت العملية بنجاح!', 'success');
                    setTimeout(() => location.reload(), 1500);
                } else {
                    const msg = result.detail || 'حدث خطأ.';
                    const isCsrf = response.status === 403 && (msg.indexOf('CSRF') !== -1 || msg.indexOf('csrf') !== -1);
                    showToast(isCsrf ? 'انتهت صلاحية الجلسة. حدّث الصفحة (F5) ثم حاول إغلاق الجولة مرة أخرى.' : msg, 'error');
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
