let temperatureChart, humidityChart, lightChart, mq135Chart, zp01Chart;
let statsBarChart, avgBarChart, tempDistributionChart, humDistributionChart;
let currentPage = 1;
let pageSize = 20;
let totalPages = 1;
let currentTab = 'realtime';
let statsData = null;

function initCharts() {
    console.log('Initializing charts...');
    const ctxTemp = document.getElementById('temperature-chart').getContext('2d');
    const ctxHumidity = document.getElementById('humidity-chart').getContext('2d');
    const ctxLight = document.getElementById('light-chart').getContext('2d');
    const ctxMq135 = document.getElementById('mq135-chart').getContext('2d');
    const ctxZp01 = document.getElementById('zp01-chart').getContext('2d');

    const yAxisConfig = function(stats, field, fallbackMin, fallbackMax) {
        const min = stats ? (stats[field] ? stats[field].min : null) : null;
        const max = stats ? (stats[field] ? stats[field].max : null) : null;
        const config = { beginAtZero: false, ticks: { maxTicksLimit: 10 } };
        if (min !== null && max !== null) {
            const padding = (max - min) * 0.1;
            config.min = Math.max(0, min - padding);
            config.max = max + padding;
        } else if (fallbackMin !== undefined && fallbackMax !== undefined) {
            config.min = fallbackMin;
            config.max = fallbackMax;
        }
        return config;
    };

    const xAxisConfig = {
        ticks: { maxRotation: 45, minRotation: 45, font: { size: 9 } },
        grid: { display: false }
    };

    const tempYAxis = yAxisConfig(statsData, 'temperature', 0, 50);
    const humYAxis = yAxisConfig(statsData, 'humidity', 0, 100);
    const lightYAxis = yAxisConfig(statsData, 'light', 0, 1000);
    const mq135YAxis = yAxisConfig(statsData, 'mq135', 0, 500);
    const zp01YAxis = yAxisConfig(statsData, 'zp01', 0, 500);

    temperatureChart = new Chart(ctxTemp, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Temperature (C)', data: [], borderColor: 'rgba(255, 99, 132, 1)', backgroundColor: 'rgba(255, 99, 132, 0.2)', tension: 0.1 }] },
        options: { responsive: true, maintainAspectRatio: true, scales: { x: xAxisConfig, y: tempYAxis } }
    });

    humidityChart = new Chart(ctxHumidity, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Humidity (%)', data: [], borderColor: 'rgba(54, 162, 235, 1)', backgroundColor: 'rgba(54, 162, 235, 0.2)', tension: 0.1 }] },
        options: { responsive: true, maintainAspectRatio: true, scales: { x: xAxisConfig, y: humYAxis } }
    });

    lightChart = new Chart(ctxLight, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Light', data: [], borderColor: 'rgba(255, 206, 86, 1)', backgroundColor: 'rgba(255, 206, 86, 0.2)', tension: 0.1 }] },
        options: { responsive: true, maintainAspectRatio: true, scales: { x: xAxisConfig, y: lightYAxis } }
    });

    mq135Chart = new Chart(ctxMq135, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'MQ135', data: [], borderColor: 'rgba(75, 192, 192, 1)', backgroundColor: 'rgba(75, 192, 192, 0.2)', tension: 0.1 }] },
        options: { responsive: true, maintainAspectRatio: true, scales: { x: xAxisConfig, y: mq135YAxis } }
    });

    zp01Chart = new Chart(ctxZp01, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'ZP01', data: [], borderColor: 'rgba(153, 102, 255, 1)', backgroundColor: 'rgba(153, 102, 255, 0.2)', tension: 0.1 }] },
        options: { responsive: true, maintainAspectRatio: true, scales: { x: xAxisConfig, y: zp01YAxis } }
    });
    console.log('Charts initialized');
}

function initBarCharts() {
    console.log('Initializing bar charts...');
    const ctxStatsBar = document.getElementById('stats-bar-chart').getContext('2d');
    const ctxAvgBar = document.getElementById('avg-bar-chart').getContext('2d');

    statsBarChart = new Chart(ctxStatsBar, {
        type: 'bar',
        data: { labels: [], datasets: [] },
        options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }
    });

    avgBarChart = new Chart(ctxAvgBar, {
        type: 'bar',
        data: { labels: [], datasets: [] },
        options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }
    });
    console.log('Bar charts initialized');
}

function initPieCharts() {
    console.log('Initializing pie charts...');
    const ctxTempDist = document.getElementById('temp-distribution').getContext('2d');
    const ctxHumDist = document.getElementById('hum-distribution').getContext('2d');

    tempDistributionChart = new Chart(ctxTempDist, { type: 'pie', data: { labels: [], datasets: [] }, options: { responsive: true, maintainAspectRatio: false } });
    humDistributionChart = new Chart(ctxHumDist, { type: 'pie', data: { labels: [], datasets: [] }, options: { responsive: true, maintainAspectRatio: false } });
    console.log('Pie charts initialized');
}

function formatTimestamp(timestamp) {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function fetchLatestData() {
    console.log('Fetching latest data...');
    fetch('http://localhost:5000/api/data')
        .then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP ' + response.status + ': ' + response.statusText);
            }
            return response.json();
        })
        .then(function(data) {
            console.log('Latest data received:', data.length, 'records');
            if (data.length > 0) {
                var latest = data[0];
                document.getElementById('latest-data').innerHTML = '<p><strong>Time:</strong> ' + formatTimestamp(latest.timestamp) + '</p>' +
                    '<p><strong>Temperature:</strong> ' + (latest.temperature || '-') + ' C</p>' +
                    '<p><strong>Humidity:</strong> ' + (latest.humidity || '-') + ' %</p>' +
                    '<p><strong>Light:</strong> ' + (latest.light || '-') + '</p>' +
                    '<p><strong>MQ135:</strong> ' + (latest.mq135 || '-') + '</p>' +
                    '<p><strong>ZP01:</strong> ' + (latest.zp01 || '-') + '</p>';
                updateLineCharts(data.slice(0, 20));
            } else {
                document.getElementById('latest-data').innerHTML = '<p>No data available</p>';
            }
        })
        .catch(function(error) {
            console.error('Error fetching data:', error);
            document.getElementById('latest-data').innerHTML = '<p style="color:#ff6b6b;">Failed to load data: ' + error.message + '</p>';
        });
}

function updateLineCharts(data) {
    console.log('Updating line charts with', data.length, 'records');
    var recentData = data.slice(0, 30).reverse();
    var labels = recentData.map(function(item) { return formatTimestamp(item.timestamp); });

    temperatureChart.data.labels = labels;
    temperatureChart.data.datasets[0].data = recentData.map(function(item) { return item.temperature; });
    temperatureChart.update();

    humidityChart.data.labels = labels;
    humidityChart.data.datasets[0].data = recentData.map(function(item) { return item.humidity; });
    humidityChart.update();

    lightChart.data.labels = labels;
    lightChart.data.datasets[0].data = recentData.map(function(item) { return item.light; });
    lightChart.update();

    mq135Chart.data.labels = labels;
    mq135Chart.data.datasets[0].data = recentData.map(function(item) { return item.mq135; });
    mq135Chart.update();

    zp01Chart.data.labels = labels;
    zp01Chart.data.datasets[0].data = recentData.map(function(item) { return item.zp01; });
    zp01Chart.update();
}

function fetchStatistics() {
    console.log('Fetching statistics...');
    fetch('http://localhost:5000/api/data/statistics')
        .then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP ' + response.status + ': ' + response.statusText);
            }
            return response.json();
        })
        .then(function(stats) {
            console.log('Statistics received:', stats);
            statsData = stats;
            document.getElementById('temp-max').textContent = stats.temperature.max || '-';
            document.getElementById('temp-min').textContent = stats.temperature.min || '-';
            document.getElementById('temp-avg').textContent = stats.temperature.avg || '-';

            document.getElementById('hum-max').textContent = stats.humidity.max || '-';
            document.getElementById('hum-min').textContent = stats.humidity.min || '-';
            document.getElementById('hum-avg').textContent = stats.humidity.avg || '-';

            document.getElementById('light-max').textContent = stats.light.max || '-';
            document.getElementById('light-min').textContent = stats.light.min || '-';
            document.getElementById('light-avg').textContent = stats.light.avg || '-';

            document.getElementById('mq135-max').textContent = stats.mq135.max || '-';
            document.getElementById('mq135-min').textContent = stats.mq135.min || '-';
            document.getElementById('mq135-avg').textContent = stats.mq135.avg || '-';

            document.getElementById('zp01-max').textContent = stats.zp01.max || '-';
            document.getElementById('zp01-min').textContent = stats.zp01.min || '-';
            document.getElementById('zp01-avg').textContent = stats.zp01.avg || '-';

            document.getElementById('total-records').textContent = stats.total_records || 0;

            updateBarCharts(stats);
            updatePieCharts(stats);
            updateLineChartBounds(stats);
        })
        .catch(function(error) {
            console.error('Error fetching statistics:', error);
            var statsSection = document.querySelector('.stats-section');
            if (statsSection) {
                var existingError = statsSection.querySelector('.error-msg');
                if (!existingError) {
                    var errorDiv = document.createElement('div');
                    errorDiv.className = 'error-msg';
                    errorDiv.textContent = 'Failed to load statistics: ' + error.message;
                    statsSection.appendChild(errorDiv);
                }
            }
        });
}

function updateBarCharts(stats) {
    console.log('Updating bar charts...');
    var labels = ['Temp', 'Humidity', 'Light', 'MQ135', 'ZP01'];

    statsBarChart.data = {
        labels: labels,
        datasets: [
            { label: 'Max', data: [stats.temperature.max, stats.humidity.max, stats.light.max, stats.mq135.max, stats.zp01.max], backgroundColor: 'rgba(255, 99, 132, 0.8)', borderColor: 'rgba(255, 99, 132, 1)', borderWidth: 1 },
            { label: 'Min', data: [stats.temperature.min, stats.humidity.min, stats.light.min, stats.mq135.min, stats.zp01.min], backgroundColor: 'rgba(54, 162, 235, 0.8)', borderColor: 'rgba(54, 162, 235, 1)', borderWidth: 1 }
        ]
    };
    statsBarChart.update();

    avgBarChart.data = {
        labels: labels,
        datasets: [{ label: 'Average', data: [stats.temperature.avg, stats.humidity.avg, stats.light.avg, stats.mq135.avg, stats.zp01.avg], backgroundColor: 'rgba(75, 192, 192, 0.8)', borderColor: 'rgba(75, 192, 192, 1)', borderWidth: 1 }]
    };
    avgBarChart.update();
}

function updatePieCharts(stats) {
    console.log('Updating pie charts...');
    var tempRanges = [
        { label: 'Low (<22C)', value: 25 },
        { label: 'Normal (22-28C)', value: 50 },
        { label: 'High (>28C)', value: 25 }
    ];

    var humRanges = [
        { label: 'Dry (<40%)', value: 25 },
        { label: 'Normal (40-60%)', value: 50 },
        { label: 'Humid (>60%)', value: 25 }
    ];

    tempDistributionChart.data = {
        labels: tempRanges.map(function(r) { return r.label; }),
        datasets: [{ data: tempRanges.map(function(r) { return r.value; }), backgroundColor: ['rgba(54, 162, 235, 0.8)', 'rgba(75, 192, 192, 0.8)', 'rgba(255, 99, 132, 0.8)'], borderWidth: 1 }]
    };
    tempDistributionChart.update();

    humDistributionChart.data = {
        labels: humRanges.map(function(r) { return r.label; }),
        datasets: [{ data: humRanges.map(function(r) { return r.value; }), backgroundColor: ['rgba(255, 206, 86, 0.8)', 'rgba(75, 192, 192, 0.8)', 'rgba(54, 162, 235, 0.8)'], borderWidth: 1 }]
    };
    humDistributionChart.update();
}

function updateLineChartBounds(stats) {
    console.log('Updating line chart Y-axis bounds...');

    const updateChartBounds = function(chart, field) {
        const min = stats[field] ? stats[field].min : null;
        const max = stats[field] ? stats[field].max : null;

        if (min !== null && max !== null) {
            const padding = (max - min) * 0.1;
            chart.options.scales.y.min = Math.max(0, min - padding);
            chart.options.scales.y.max = max + padding;
            chart.update();
        }
    };

    updateChartBounds(temperatureChart, 'temperature');
    updateChartBounds(humidityChart, 'humidity');
    updateChartBounds(lightChart, 'light');
    updateChartBounds(mq135Chart, 'mq135');
    updateChartBounds(zp01Chart, 'zp01');
}

function fetchPagedData(page, size) {
    if (page === undefined) page = 1;
    if (size === undefined) size = 20;
    console.log('Fetching paged data: page=' + page + ', size=' + size);

    fetch('http://localhost:5000/api/data/paged?page=' + page + '&page_size=' + size)
        .then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP ' + response.status + ': ' + response.statusText);
            }
            return response.json();
        })
        .then(function(result) {
            console.log('Paged data received:', result.data.length, 'records');
            currentPage = result.page;
            pageSize = result.page_size;
            totalPages = result.total_pages;

            document.getElementById('current-page').textContent = currentPage;
            document.getElementById('total-pages').textContent = totalPages;

            updatePaginationButtons();

            var tbody = document.getElementById('table-body');
            if (result.data.length > 0) {
                var html = '';
                for (var i = 0; i < result.data.length; i++) {
                    var item = result.data[i];
                    html += '<tr><td>' + item.id + '</td><td>' + formatTimestamp(item.timestamp) + '</td><td>' + (item.temperature || '-') + '</td><td>' + (item.humidity || '-') + '</td><td>' + (item.light || '-') + '</td><td>' + (item.mq135 || '-') + '</td><td>' + (item.zp01 || '-') + '</td></tr>';
                }
                tbody.innerHTML = html;
            } else {
                tbody.innerHTML = '<tr><td colspan="7">No data available</td></tr>';
            }
        })
        .catch(function(error) {
            console.error('Error fetching paged data:', error);
            document.getElementById('table-body').innerHTML = '<tr><td colspan="7" style="color:#ff6b6b;">Load failed: ' + error.message + '</td></tr>';
        });
}

function updatePaginationButtons() {
    var prevBtn = document.getElementById('prev-page');
    var nextBtn = document.getElementById('next-page');

    if (prevBtn) {
        prevBtn.disabled = currentPage <= 1;
    }
    if (nextBtn) {
        nextBtn.disabled = currentPage >= totalPages;
    }
}

function switchTab(tabName) {
    console.log('Switching to tab:', tabName);

    var tabs = document.querySelectorAll('.nav-tab');
    var pages = document.querySelectorAll('.page-content');

    tabs.forEach(function(tab) {
        if (tab.dataset.page === tabName) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });

    pages.forEach(function(page) {
        if (page.id === 'page-' + tabName) {
            page.style.display = 'block';
            setTimeout(function() {
                page.classList.add('slide-in');
                page.classList.remove('slide-out');
            }, 10);
        } else {
            if (page.classList.contains('active')) {
                page.classList.add('slide-out');
                page.classList.remove('slide-in');
                setTimeout(function() {
                    page.style.display = 'none';
                    page.classList.remove('slide-out');
                }, 300);
            } else {
                page.style.display = 'none';
            }
        }
    });

    currentTab = tabName;

    if (tabName === 'realtime') {
        fetchLatestData();
    } else if (tabName === 'statistics') {
        fetchStatistics();
    } else if (tabName === 'trends') {
        fetchLatestData();
    } else if (tabName === 'history') {
        fetchPagedData(1, pageSize);
    }
}

function initTabNavigation() {
    var tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(function(tab) {
        tab.onclick = function() {
            var tabName = this.dataset.page;
            switchTab(tabName);
        };
    });

    var prevBtn = document.getElementById('prev-page');
    var nextBtn = document.getElementById('next-page');

    if (prevBtn) {
        prevBtn.onclick = function() {
            if (currentPage > 1) {
                fetchPagedData(currentPage - 1, pageSize);
            }
        };
    }

    if (nextBtn) {
        nextBtn.onclick = function() {
            if (currentPage < totalPages) {
                fetchPagedData(currentPage + 1, pageSize);
            }
        };
    }

    document.getElementById('page-size').onchange = function(e) {
        pageSize = parseInt(e.target.value);
        fetchPagedData(1, pageSize);
    };
}

window.onload = function() {
    console.log('Page loaded, initializing...');
    try {
        initCharts();
        initBarCharts();
        initPieCharts();
        initTabNavigation();
        fetchLatestData();
        fetchStatistics();
        fetchPagedData(1, pageSize);
        setInterval(fetchLatestData, 5000);
        setInterval(fetchStatistics, 30000);
        console.log('Initialization complete');
    } catch (e) {
        console.error('Initialization error:', e);
        alert('Initialization error: ' + e.message);
    }
};