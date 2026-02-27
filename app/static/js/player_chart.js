document.addEventListener("DOMContentLoaded", function () {
    const canvas = document.getElementById('performanceChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const labels = canvas.getAttribute('data-labels').split(',');
    const pointsData = canvas.getAttribute('data-points').split(',').map(Number);
    const goalsData = canvas.getAttribute('data-goals').split(',').map(Number);
    const assistsData = canvas.getAttribute('data-assists').split(',').map(Number);

    // New: Point Colors from Analytics Service
    const pointColorsRaw = canvas.getAttribute('data-point-colors');
    const pointColors = pointColorsRaw ? pointColorsRaw.split(',') : [];

    // Parse outcomes for tooltip
    const outcomesRaw = canvas.getAttribute('data-outcomes');
    const outcomes = outcomesRaw ? outcomesRaw.split(',') : [];

    const textColor = getComputedStyle(document.body).getPropertyValue('--text-color').trim();
    const gridColor = getComputedStyle(document.body).getPropertyValue('--border-color').trim();

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
                    labels: { color: textColor, font: { family: 'Cairo', size: 12 } }
                },
                tooltip: {
                    padding: 12,
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleFont: { family: 'Cairo', size: 14 },
                    bodyFont: { family: 'Cairo', size: 13 },
                    callbacks: {
                        afterLabel: function (context) {
                            if (context.datasetIndex === 0 && outcomes.length) {
                                const outcome = outcomes[context.dataIndex].trim();
                                return outcome === 'W' ? '✅ نتيجة المباراة: فوز' : '❌ نتيجة المباراة: خسارة';
                            }
                            return '';
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: textColor, font: { family: 'Cairo' } },
                    grid: { color: gridColor, drawOnChartArea: false },
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: { display: true, text: 'النقاط', color: textColor, font: { family: 'Cairo' } },
                    ticks: { color: textColor },
                    grid: { color: gridColor },
                    min: 0,
                    suggestedMax: 15
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: { display: true, text: 'الأهداف / الأسيست', color: textColor, font: { family: 'Cairo' } },
                    ticks: { color: textColor, stepSize: 1 },
                    grid: { drawOnChartArea: false },
                    min: 0,
                    suggestedMax: 5
                }
            }
        }
    });
});
