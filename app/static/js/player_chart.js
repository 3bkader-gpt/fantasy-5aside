document.addEventListener("DOMContentLoaded", function () {
    const canvas = document.getElementById('performanceChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const labels = canvas.getAttribute('data-labels').split(',');
    const pointsData = canvas.getAttribute('data-points').split(',').map(Number);
    const goalsData = canvas.getAttribute('data-goals').split(',').map(Number);
    const assistsData = canvas.getAttribute('data-assists').split(',').map(Number);

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
                    tension: 0.3,
                    fill: true,
                    yAxisID: 'y'
                },
                {
                    label: 'الأهداف',
                    data: goalsData,
                    type: 'bar',
                    backgroundColor: 'rgba(46, 204, 113, 0.6)',
                    yAxisID: 'y1'
                },
                {
                    label: 'الأسيست',
                    data: assistsData,
                    type: 'bar',
                    backgroundColor: 'rgba(155, 89, 182, 0.6)',
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    labels: { color: textColor, font: { family: 'Cairo' } }
                }
            },
            scales: {
                x: {
                    ticks: { color: textColor },
                    grid: { color: gridColor },
                    title: { display: true, text: 'المباريات', color: textColor }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: { display: true, text: 'النقاط', color: textColor },
                    ticks: { color: textColor },
                    grid: { color: gridColor },
                    min: 0,
                    suggestedMax: 15
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: { display: true, text: 'الأهداف / الأسيست', color: textColor },
                    ticks: { color: textColor, stepSize: 1 },
                    grid: { drawOnChartArea: false },
                    min: 0,
                    suggestedMax: 5
                }
            }
        }
    });
});
