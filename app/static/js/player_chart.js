document.addEventListener("DOMContentLoaded", function () {
    const textColor = getComputedStyle(document.body).getPropertyValue('--text-color').trim();
    const gridColor = getComputedStyle(document.body).getPropertyValue('--border-color').trim();

    const perfCanvas = document.getElementById('performanceChart');
    if (perfCanvas) {
        const ctx = perfCanvas.getContext('2d');
        const labels = perfCanvas.getAttribute('data-labels').split(',');
        const pointsData = perfCanvas.getAttribute('data-points').split(',').map(Number);
        const goalsData = perfCanvas.getAttribute('data-goals').split(',').map(Number);
        const assistsData = perfCanvas.getAttribute('data-assists').split(',').map(Number);
        const pointColorsRaw = perfCanvas.getAttribute('data-point-colors');
        const pointColors = pointColorsRaw ? pointColorsRaw.split(',') : [];
        const outcomesRaw = perfCanvas.getAttribute('data-outcomes');
        const outcomes = outcomesRaw ? outcomesRaw.split(',') : [];

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'النقاط',
                        data: pointsData,
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        borderWidth: 3,
                        tension: 0.4,
                        fill: true,
                        yAxisID: 'y',
                        pointBackgroundColor: pointColors.length ? pointColors : '#3498db',
                        pointBorderColor: '#fff',
                        pointRadius: 6,
                        pointHoverRadius: 9,
                        pointBorderWidth: 2
                    },
                    {
                        label: 'الأهداف',
                        data: goalsData,
                        type: 'bar',
                        backgroundColor: 'rgba(46, 204, 113, 0.6)',
                        yAxisID: 'y1',
                        borderRadius: 4
                    },
                    {
                        label: 'الأسيست',
                        data: assistsData,
                        type: 'bar',
                        backgroundColor: 'rgba(155, 89, 182, 0.6)',
                        yAxisID: 'y1',
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: textColor, font: { family: 'Tajawal', size: 12 } }
                    },
                    tooltip: {
                        padding: 12,
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        titleFont: { family: 'Tajawal', size: 14 },
                        bodyFont: { family: 'Tajawal', size: 13 },
                        callbacks: {
                            afterLabel: function (context) {
                                if (context.datasetIndex === 0 && outcomes.length) {
                                    const outcome = outcomes[context.dataIndex].trim();
                                    return outcome === 'W' ? '✅ نتيجة المباراة: فوز' : outcome === 'D' ? '➖ نتيجة المباراة: تعادل' : '❌ نتيجة المباراة: خسارة';
                                }
                                return '';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: textColor, font: { family: 'Tajawal' } },
                        grid: { color: gridColor, drawOnChartArea: false },
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: 'النقاط', color: textColor, font: { family: 'Tajawal' } },
                        ticks: { color: textColor },
                        grid: { color: gridColor },
                        min: 0,
                        suggestedMax: 15
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: { display: true, text: 'الأهداف / الأسيست', color: textColor, font: { family: 'Tajawal' } },
                        ticks: { color: textColor, stepSize: 1 },
                        grid: { drawOnChartArea: false },
                        min: 0,
                        suggestedMax: 5
                    }
                }
            }
        });
    }

    // Radar + H2H
    const radarCanvas = document.getElementById('playerRadarChart');
    const h2hSelect = document.getElementById('h2h-select');
    if (!radarCanvas || !h2hSelect) {
        return;
    }

    const radarCtx = radarCanvas.getContext('2d');
    const basePlayerName = document.querySelector('.player-profile h1')?.textContent?.trim() || 'Player';
    let radarChart = null;

    function buildRadarChart(p1, p2) {
        const labels = ['أهداف', 'أسيست', 'تصديات', 'شباكات نظيفة', 'متوسط النقاط'];
        const data1 = p1.radar;
        const data2 = p2 ? p2.radar : null;

        if (radarChart) {
            radarChart.destroy();
        }

        radarChart = new Chart(radarCtx, {
            type: 'radar',
            data: {
                labels,
                datasets: [
                    {
                        label: p1.name,
                        data: data1,
                        borderColor: 'rgba(59, 130, 246, 1)',
                        backgroundColor: 'rgba(59, 130, 246, 0.3)',
                    },
                    ...(data2 ? [{
                        label: p2.name,
                        data: data2,
                        borderColor: 'rgba(249, 115, 22, 1)',
                        backgroundColor: 'rgba(249, 115, 22, 0.3)',
                    }] : []),
                ],
            },
            options: {
                responsive: true,
                scales: {
                    r: {
                        angleLines: { color: gridColor },
                        grid: { color: gridColor },
                        pointLabels: { color: textColor, font: { family: 'Tajawal' } },
                        ticks: { display: false },
                    },
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: textColor, font: { family: 'Tajawal' } },
                    },
                },
            },
        });
    }

    async function loadHeadToHead(otherId) {
        const pathParts = window.location.pathname.split('/');
        const slugIdx = pathParts.indexOf('l') + 1;
        const slug = pathParts[slugIdx] || '';
        const playerId = parseInt(pathParts[pathParts.length - 1], 10);
        if (!slug || !playerId || !otherId) return;

        try {
            const res = await fetch(`/l/${slug}/api/player/${playerId}/vs/${otherId}`);
            if (!res.ok) return;
            const data = await res.json();

            const h2hSummary = document.getElementById('h2h-summary');
            const p1Points = document.getElementById('h2h-p1-points');
            const p2Points = document.getElementById('h2h-p2-points');
            const p2Name = document.getElementById('h2h-p2-name');
            const p2Header = document.getElementById('h2h-p2-header');
            const body = document.getElementById('h2h-matches-body');

            if (!h2hSummary || !p1Points || !p2Points || !p2Name || !p2Header || !body) return;

            const p1 = data.player1;
            const p2 = data.player2;
            buildRadarChart(p1, p2);

            p1Points.textContent = `مجموع النقاط: ${p1.aggregates.points} (في ${p1.aggregates.matches} مباراة)`;
            p2Points.textContent = `مجموع النقاط: ${p2.aggregates.points} (في ${p2.aggregates.matches} مباراة)`;
            p2Name.textContent = p2.name;
            p2Header.textContent = p2.name;

            body.innerHTML = '';
            if (!data.shared_matches.length) {
                const tr = document.createElement('tr');
                const td = document.createElement('td');
                td.colSpan = 5;
                td.className = 'text-center text-secondary';
                td.textContent = 'لا توجد مباريات مشتركة حتى الآن.';
                tr.appendChild(td);
                body.appendChild(tr);
            } else {
                data.shared_matches.forEach((m) => {
                    const tr = document.createElement('tr');
                    const dateCell = document.createElement('td');
                    dateCell.textContent = m.date ? new Date(m.date).toLocaleDateString('ar-EG') : '';
                    const scoreCell = document.createElement('td');
                    scoreCell.textContent = m.score || '';
                    const p1Cell = document.createElement('td');
                    p1Cell.textContent = String(m.p1_points);
                    const p2Cell = document.createElement('td');
                    p2Cell.textContent = String(m.p2_points);
                    const winnerCell = document.createElement('td');
                    let winnerLabel = 'تعادل';
                    if (m.winner === 'p1') winnerLabel = p1.name;
                    else if (m.winner === 'p2') winnerLabel = p2.name;
                    winnerCell.textContent = winnerLabel;
                    tr.appendChild(dateCell);
                    tr.appendChild(scoreCell);
                    tr.appendChild(p1Cell);
                    tr.appendChild(p2Cell);
                    tr.appendChild(winnerCell);
                    body.appendChild(tr);
                });
            }

            h2hSummary.style.display = 'block';
        } catch (e) {
            console.error('Failed to load H2H', e);
        }
    }

    h2hSelect.addEventListener('change', function () {
        const otherId = parseInt(this.value, 10);
        if (!otherId) return;
        loadHeadToHead(otherId);
    });

    // Initialise radar with zeroes until a comparison is selected
    buildRadarChart(
        {
            name: basePlayerName,
            radar: [0, 0, 0, 0, 0],
        },
        null
    );
});
