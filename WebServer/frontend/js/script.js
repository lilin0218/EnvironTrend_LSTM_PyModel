let temperatureChart, humidityChart, lightChart, mq135Chart, zp01Chart;
let statsBarChart, avgBarChart, tempDistributionChart, humDistributionChart;
let currentPage = 1;
let pageSize = 20;
let totalPages = 1;
let currentTab = 'realtime';
let statsData = null;

let currentDayLabels = [];
let chartDataCache = {
    temperature: {},
    humidity: {},
    light: {},
    mq135: {},
    zp01: {}
};

function generateDayLabels() {
    let labels = [];
    for (let hour = 0; hour <= 23; hour++) {
        for (let min = 0; min < 60; min++) {
            labels.push(String(hour).padStart(2, '0') + ':' + String(min).padStart(2, '0'));
        }
    }
    return labels;
}

function getTimeKey(timestamp) {
    let dateStr = typeof timestamp === 'string' ? timestamp : timestamp.toISOString();
    let match = dateStr.match(/T(\d{2}):(\d{2})/);
    if (match) {
        return match[1] + ':' + match[2];
    }
    let date = new Date(timestamp);
    return String(date.getHours()).padStart(2, '0') + ':' + String(date.getMinutes()).padStart(2, '0');
}

function getCurrentDateString() {
    let now = new Date();
    return now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
}

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
        const config = { 
            beginAtZero: false, 
            ticks: { 
                maxTicksLimit: 10,
                callback: function(value) {
                    return value.toFixed(value % 1 !== 0 ? 2 : 0);
                }
            } 
        };
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
        ticks: { 
            maxRotation: 45, 
            minRotation: 45, 
            font: { size: 9 },
            autoSkip: true,
            maxTicksLimit: 24
        },
        grid: { display: false }
    };

    const tempYAxis = yAxisConfig(statsData, 'temperature', 0, 50);
    const humYAxis = yAxisConfig(statsData, 'humidity', 0, 100);
    const lightYAxis = yAxisConfig(statsData, 'light', 0, 1000);
    const mq135YAxis = yAxisConfig(statsData, 'mq135', 0, 500);
    const zp01YAxis = yAxisConfig(statsData, 'zp01', 0, 500);

    currentDayLabels = generateDayLabels();

    temperatureChart = new Chart(ctxTemp, {
        type: 'line',
        data: { 
            labels: currentDayLabels, 
            datasets: [{ 
                label: 'Temperature (C)', 
                data: Array(currentDayLabels.length).fill(null), 
                borderColor: 'rgba(33, 150, 243, 1)', 
                backgroundColor: 'rgba(33, 150, 243, 0.2)', 
                tension: 0.1,
                pointRadius: 2,
                pointHoverRadius: 4
            }] 
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            scales: { x: xAxisConfig, y: tempYAxis },
            plugins: {
                legend: {
                    labels: { font: { size: 11 } }
                },
                tooltip: {
                    titleFont: { size: 11 },
                    bodyFont: { size: 10 }
                }
            }
        }
    });

    humidityChart = new Chart(ctxHumidity, {
        type: 'line',
        data: { 
            labels: currentDayLabels, 
            datasets: [{ 
                label: 'Humidity (%)', 
                data: Array(currentDayLabels.length).fill(null), 
                borderColor: 'rgba(33, 150, 243, 1)', 
                backgroundColor: 'rgba(33, 150, 243, 0.2)', 
                tension: 0.1,
                pointRadius: 2,
                pointHoverRadius: 4
            }] 
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            scales: { x: xAxisConfig, y: humYAxis },
            plugins: {
                legend: {
                    labels: { font: { size: 11 } }
                },
                tooltip: {
                    titleFont: { size: 11 },
                    bodyFont: { size: 10 }
                }
            }
        }
    });

    lightChart = new Chart(ctxLight, {
        type: 'line',
        data: { 
            labels: currentDayLabels, 
            datasets: [{ 
                label: 'Light', 
                data: Array(currentDayLabels.length).fill(null), 
                borderColor: 'rgba(33, 150, 243, 1)', 
                backgroundColor: 'rgba(33, 150, 243, 0.2)', 
                tension: 0.1,
                pointRadius: 2,
                pointHoverRadius: 4
            }] 
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            scales: { x: xAxisConfig, y: lightYAxis },
            plugins: {
                legend: {
                    labels: { font: { size: 11 } }
                },
                tooltip: {
                    titleFont: { size: 11 },
                    bodyFont: { size: 10 }
                }
            }
        }
    });

    mq135Chart = new Chart(ctxMq135, {
        type: 'line',
        data: { 
            labels: currentDayLabels, 
            datasets: [{ 
                label: 'MQ135', 
                data: Array(currentDayLabels.length).fill(null), 
                borderColor: 'rgba(33, 150, 243, 1)', 
                backgroundColor: 'rgba(33, 150, 243, 0.2)', 
                tension: 0.1,
                pointRadius: 2,
                pointHoverRadius: 4
            }] 
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            scales: { x: xAxisConfig, y: mq135YAxis },
            plugins: {
                legend: {
                    labels: { font: { size: 11 } }
                },
                tooltip: {
                    titleFont: { size: 11 },
                    bodyFont: { size: 10 }
                }
            }
        }
    });

    zp01Chart = new Chart(ctxZp01, {
        type: 'line',
        data: { 
            labels: currentDayLabels, 
            datasets: [{ 
                label: 'ZP01', 
                data: Array(currentDayLabels.length).fill(null), 
                borderColor: 'rgba(33, 150, 243, 1)', 
                backgroundColor: 'rgba(33, 150, 243, 0.2)', 
                tension: 0.1,
                pointRadius: 2,
                pointHoverRadius: 4
            }] 
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            scales: { x: xAxisConfig, y: zp01YAxis },
            plugins: {
                legend: {
                    labels: { font: { size: 11 } }
                },
                tooltip: {
                    titleFont: { size: 11 },
                    bodyFont: { size: 10 }
                }
            }
        }
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
    let dateStr = typeof timestamp === 'string' ? timestamp : timestamp.toISOString();
    let match = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/);
    if (match) {
        return match[1] + '/' + match[2] + '/' + match[3] + ' ' + match[4] + ':' + match[5] + ':' + match[6];
    }
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function checkDateChange(timestamp) {
    let dateStr = typeof timestamp === 'string' ? timestamp : timestamp.toISOString();
    let match = dateStr.match(/^(\d{4}-\d{2}-\d{2})/);
    let dataDate = match ? match[1] : null;
    let currentDate = getCurrentDateString();
    
    if (dataDate && dataDate !== currentDate) {
        console.log('Date change detected! Resetting charts for new day:', dataDate);
        resetChartsForNewDay();
        return true;
    }
    return false;
}

function resetChartsForNewDay() {
    currentDayLabels = generateDayLabels();
    
    chartDataCache = {
        temperature: {},
        humidity: {},
        light: {},
        mq135: {},
        zp01: {}
    };

    temperatureChart.data.labels = currentDayLabels;
    temperatureChart.data.datasets[0].data = Array(currentDayLabels.length).fill(null);
    temperatureChart.update('none');

    humidityChart.data.labels = currentDayLabels;
    humidityChart.data.datasets[0].data = Array(currentDayLabels.length).fill(null);
    humidityChart.update('none');

    lightChart.data.labels = currentDayLabels;
    lightChart.data.datasets[0].data = Array(currentDayLabels.length).fill(null);
    lightChart.update('none');

    mq135Chart.data.labels = currentDayLabels;
    mq135Chart.data.datasets[0].data = Array(currentDayLabels.length).fill(null);
    mq135Chart.update('none');

    zp01Chart.data.labels = currentDayLabels;
    zp01Chart.data.datasets[0].data = Array(currentDayLabels.length).fill(null);
    zp01Chart.update('none');
}

function addDataPointToChart(timestamp, temperature, humidity, light, mq135, zp01) {
    if (checkDateChange(timestamp)) {
        return;
    }

    let timeKey = getTimeKey(timestamp);
    let labelIndex = currentDayLabels.indexOf(timeKey);

    if (labelIndex !== -1) {
        if (temperature !== undefined && temperature !== null) {
            chartDataCache.temperature[timeKey] = temperature;
            temperatureChart.data.datasets[0].data[labelIndex] = temperature;
        }
        if (humidity !== undefined && humidity !== null) {
            chartDataCache.humidity[timeKey] = humidity;
            humidityChart.data.datasets[0].data[labelIndex] = humidity;
        }
        if (light !== undefined && light !== null) {
            chartDataCache.light[timeKey] = light;
            lightChart.data.datasets[0].data[labelIndex] = light;
        }
        if (mq135 !== undefined && mq135 !== null) {
            chartDataCache.mq135[timeKey] = mq135;
            mq135Chart.data.datasets[0].data[labelIndex] = mq135;
        }
        if (zp01 !== undefined && zp01 !== null) {
            chartDataCache.zp01[timeKey] = zp01;
            zp01Chart.data.datasets[0].data[labelIndex] = zp01;
        }

        temperatureChart.update('none');
        humidityChart.update('none');
        lightChart.update('none');
        mq135Chart.update('none');
        zp01Chart.update('none');
        
        updateChartsYAxisFromCurrentData();
    }
}

function loadHistoricalDataForToday(data) {
    console.log('Loading historical data for today...');
    
    let today = getCurrentDateString();
    
    data.forEach(function(item) {
        let dateStr = typeof item.timestamp === 'string' ? item.timestamp : item.timestamp.toISOString();
        let match = dateStr.match(/^(\d{4}-\d{2}-\d{2})/);
        let itemDate = match ? match[1] : null;
        
        if (itemDate === today) {
            addDataPointToChart(item.timestamp, item.temperature, item.humidity, item.light, item.mq135, item.zp01);
        }
    });
    
    console.log('Historical data loaded');
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
                
                addDataPointToChart(latest.timestamp, latest.temperature, latest.humidity, latest.light, latest.mq135, latest.zp01);
            } else {
                document.getElementById('latest-data').innerHTML = '<p>No data available</p>';
            }
        })
        .catch(function(error) {
            console.error('Error fetching data:', error);
            document.getElementById('latest-data').innerHTML = '<p style="color:#ff6b6b;">Failed to load data: ' + error.message + '</p>';
        });
}

function initChartsWithHistoricalData() {
    console.log('Initializing charts with historical data...');
    fetch('http://localhost:5000/api/data')
        .then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP ' + response.status + ': ' + response.statusText);
            }
            return response.json();
        })
        .then(function(data) {
            console.log('Initial data received:', data.length, 'records');
            loadHistoricalDataForToday(data);
        })
        .catch(function(error) {
            console.error('Error loading historical data:', error);
        });
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
            updateChartsYAxis(stats);
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

function calculateYAxisRange(min, max) {
    if (min === null || max === null || min === undefined || max === undefined || isNaN(min) || isNaN(max)) {
        return { min: 0, max: 100 };
    }
    const padding = (max - min) * 0.1;
    return {
        min: min - padding,
        max: max + padding
    };
}

function updateChartsYAxisFromCurrentData() {
    console.log('Updating Y-axis from current chart data...');
    
    const dataStats = {
        temperature: { min: Infinity, max: -Infinity },
        humidity: { min: Infinity, max: -Infinity },
        light: { min: Infinity, max: -Infinity },
        mq135: { min: Infinity, max: -Infinity },
        zp01: { min: Infinity, max: -Infinity }
    };
    
    const charts = {
        temperature: temperatureChart,
        humidity: humidityChart,
        light: lightChart,
        mq135: mq135Chart,
        zp01: zp01Chart
    };
    
    Object.keys(charts).forEach(function(key) {
        const chart = charts[key];
        if (!chart || !chart.data || !chart.data.datasets) return;
        
        chart.data.datasets.forEach(function(dataset) {
            if (dataset.data) {
                dataset.data.forEach(function(value) {
                    if (value !== null && value !== undefined && !isNaN(value)) {
                        dataStats[key].min = Math.min(dataStats[key].min, value);
                        dataStats[key].max = Math.max(dataStats[key].max, value);
                    }
                });
            }
        });
    });
    
    Object.keys(dataStats).forEach(function(key) {
        if (dataStats[key].min === Infinity || dataStats[key].max === -Infinity) {
            dataStats[key] = { min: 0, max: 100 };
        }
    });
    
    updateChartsYAxis(dataStats);
}

function updateChartsYAxis(stats) {
    console.log('Updating charts Y-axis with stats:', stats);
    
    if (!stats) return;
    
    const tempRange = calculateYAxisRange(stats.temperature.min, stats.temperature.max);
    const humRange = calculateYAxisRange(stats.humidity.min, stats.humidity.max);
    const lightRange = calculateYAxisRange(stats.light.min, stats.light.max);
    const mq135Range = calculateYAxisRange(stats.mq135.min, stats.mq135.max);
    const zp01Range = calculateYAxisRange(stats.zp01.min, stats.zp01.max);
    
    if (temperatureChart) {
        temperatureChart.options.scales.y.min = tempRange.min;
        temperatureChart.options.scales.y.max = tempRange.max;
        temperatureChart.update('none');
    }
    
    if (humidityChart) {
        humidityChart.options.scales.y.min = humRange.min;
        humidityChart.options.scales.y.max = humRange.max;
        humidityChart.update('none');
    }
    
    if (lightChart) {
        lightChart.options.scales.y.min = lightRange.min;
        lightChart.options.scales.y.max = lightRange.max;
        lightChart.update('none');
    }
    
    if (mq135Chart) {
        mq135Chart.options.scales.y.min = mq135Range.min;
        mq135Chart.options.scales.y.max = mq135Range.max;
        mq135Chart.update('none');
    }
    
    if (zp01Chart) {
        zp01Chart.options.scales.y.min = zp01Range.min;
        zp01Chart.options.scales.y.max = zp01Range.max;
        zp01Chart.update('none');
    }
    
    console.log('Charts Y-axis updated successfully');
}

function fetchPagedData(page, size) {
    if (page === undefined) page = 1;
    if (size === undefined) size = 20;
    console.log('Fetching paged data: page=' + page + ', size=' + size);

    fetch('/api/data/paged?page=' + page + '&page_size=' + size)
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
        initPredictionButton();
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
        initChartsWithHistoricalData();
        fetchLatestData();
        fetchStatistics();
        fetchPagedData(1, pageSize);
        initScreenshotDisplay();
        setInterval(fetchLatestData, 5000);
        setInterval(fetchStatistics, 30000);
        setInterval(checkForNewScreenshots, 5000);
        console.log('Initialization complete');
    } catch (e) {
        console.error('Initialization error:', e);
        alert('Initialization error: ' + e.message);
    }
};

function initScreenshotDisplay() {
    console.log('Initializing screenshot display...');
    initScreenshotNavigation();
    fetchScreenshots();
}

function fetchScreenshots() {
    console.log('Fetching screenshots...');
    fetch('/api/screenshots')
        .then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP ' + response.status + ': ' + response.statusText);
            }
            return response.json();
        })
        .then(function(result) {
            console.log('Screenshots received:', result.count, 'files');
            if (result.screenshots && result.screenshots.length > 0) {
                screenshotsList = result.screenshots;
                if (currentScreenshotIndex >= screenshotsList.length) {
                    currentScreenshotIndex = 0;
                }
                updateScreenshotDisplay(screenshotsList[currentScreenshotIndex].url, screenshotsList[currentScreenshotIndex].modified);
                updateScreenshotIndex();
                updateNavButtons();
            } else {
                screenshotsList = [];
                currentScreenshotIndex = 0;
                showScreenshotPlaceholder();
                updateScreenshotIndex();
                updateNavButtons();
            }
        })
        .catch(function(error) {
            console.error('Error fetching screenshots:', error);
            showScreenshotError('Failed to load screenshots: ' + error.message);
        });
}

function checkForNewScreenshots() {
    if (currentTab !== 'realtime') {
        return;
    }
    fetchScreenshots();
}

function updateScreenshotDisplay(url, modified) {
    var img = document.getElementById('current-screenshot');
    var placeholder = document.getElementById('screenshot-placeholder');
    var error = document.getElementById('screenshot-error');
    var status = document.getElementById('screenshot-status');
    var timestamp = document.getElementById('screenshot-timestamp');

    if (img && placeholder && error && status && timestamp) {
        img.src = url + '?t=' + new Date().getTime();
        img.style.display = 'block';
        placeholder.style.display = 'none';
        error.style.display = 'none';
        status.textContent = '状态: 已连接';
        timestamp.textContent = '最后更新: ' + formatTimestamp(modified);
        
        img.onerror = function() {
            showScreenshotError('Failed to load screenshot image');
        };
    }
}

function showScreenshotPlaceholder() {
    var img = document.getElementById('current-screenshot');
    var placeholder = document.getElementById('screenshot-placeholder');
    var error = document.getElementById('screenshot-error');
    var status = document.getElementById('screenshot-status');
    var timestamp = document.getElementById('screenshot-timestamp');

    if (img && placeholder && error && status && timestamp) {
        img.style.display = 'none';
        placeholder.style.display = 'block';
        error.style.display = 'none';
        status.textContent = '状态: 等待截图';
        timestamp.textContent = '最后更新: -';
    }
}

function showScreenshotError(message) {
    var img = document.getElementById('current-screenshot');
    var placeholder = document.getElementById('screenshot-placeholder');
    var error = document.getElementById('screenshot-error');
    var status = document.getElementById('screenshot-status');

    if (img && placeholder && error && status) {
        img.style.display = 'none';
        placeholder.style.display = 'none';
        error.style.display = 'block';
        error.textContent = message;
        status.textContent = '状态: 连接失败';
    }
}

function updateScreenshotIndex() {
    var indexElement = document.getElementById('screenshot-index');
    if (indexElement) {
        indexElement.textContent = (currentScreenshotIndex + 1) + ' / ' + screenshotsList.length;
    }
}

function updateNavButtons() {
    var prevBtn = document.getElementById('prev-screenshot');
    var nextBtn = document.getElementById('next-screenshot');
    
    if (prevBtn) {
        prevBtn.disabled = screenshotsList.length <= 1 || currentScreenshotIndex <= 0;
    }
    if (nextBtn) {
        nextBtn.disabled = screenshotsList.length <= 1 || currentScreenshotIndex >= screenshotsList.length - 1;
    }
}

function prevScreenshot() {
    if (screenshotsList.length > 1 && currentScreenshotIndex > 0) {
        currentScreenshotIndex--;
        var screenshot = screenshotsList[currentScreenshotIndex];
        updateScreenshotDisplay(screenshot.url, screenshot.modified);
        updateScreenshotIndex();
        updateNavButtons();
    }
}

function nextScreenshot() {
    if (screenshotsList.length > 1 && currentScreenshotIndex < screenshotsList.length - 1) {
        currentScreenshotIndex++;
        var screenshot = screenshotsList[currentScreenshotIndex];
        updateScreenshotDisplay(screenshot.url, screenshot.modified);
        updateScreenshotIndex();
        updateNavButtons();
    }
}

function initScreenshotNavigation() {
    var prevBtn = document.getElementById('prev-screenshot');
    var nextBtn = document.getElementById('next-screenshot');
    
    if (prevBtn) {
        prevBtn.addEventListener('click', prevScreenshot);
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', nextScreenshot);
    }
}

let predictionData = null;
let screenshotsList = [];
let currentScreenshotIndex = 0;

function initPredictionButton() {
    console.log('Initializing prediction button...');
    
    const predictBtn = document.getElementById('predict-btn');
    
    if (predictBtn) {
        predictBtn.addEventListener('click', executePrediction);
    }
}

function executePrediction() {
    const btn = document.getElementById('predict-btn');
    const status = document.getElementById('predict-status');
    const result = document.getElementById('predict-result');
    
    if (!btn || !status) return;
    
    btn.disabled = true;
    status.textContent = '状态: 正在预测...';
    status.style.color = '#ffff00';
    result.style.display = 'none';
    
    console.log('Executing prediction...');
    fetch('/api/predict')
        .then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP ' + response.status + ': ' + response.statusText);
            }
            return response.json();
        })
        .then(function(data) {
            console.log('Prediction received:', data);
            if (data.predictions && data.predictions.length > 0) {
                predictionData = data.predictions;
                updatePredictionResult(data.predictions);
                displayPredictionOnCharts(data.predictions);
                status.textContent = '状态: 预测完成';
                status.style.color = '#00ff00';
            } else {
                status.textContent = '状态: 无预测数据';
                status.style.color = '#ff6b6b';
            }
        })
        .catch(function(error) {
            console.error('Prediction error:', error);
            status.textContent = '状态: 预测失败 - ' + error.message;
            status.style.color = '#ff6b6b';
        })
        .finally(function() {
            btn.disabled = false;
        });
}

function updatePredictionResult(predictions) {
    const result = document.getElementById('predict-result');
    const count = document.getElementById('predict-count');
    const range = document.getElementById('predict-range');
    
    if (result && count && range && predictions.length > 0) {
        result.style.display = 'block';
        count.textContent = '预测点数: ' + predictions.length;
        
        const firstTime = predictions[0].timestamp;
        const lastTime = predictions[predictions.length - 1].timestamp;
        range.textContent = '时间范围: ' + firstTime + ' ~ ' + lastTime;
    }
}

function displayPredictionOnCharts(predictions) {
    if (!predictions || predictions.length === 0) return;
    
    console.log('Displaying prediction on charts...');
    
    const now = new Date();
    const currentTimeKey = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');
    const currentIndex = currentDayLabels.indexOf(currentTimeKey);
    
    const tempPredData = Array(currentDayLabels.length).fill(null);
    const humPredData = Array(currentDayLabels.length).fill(null);
    const lightPredData = Array(currentDayLabels.length).fill(null);
    const mq135PredData = Array(currentDayLabels.length).fill(null);
    const zp01PredData = Array(currentDayLabels.length).fill(null);
    
    let count = 0;
    predictions.forEach(function(pred) {
        const timeKey = getTimeKey(pred.timestamp);
        const labelIndex = currentDayLabels.indexOf(timeKey);
        
        if (labelIndex !== -1 && labelIndex < currentDayLabels.length && labelIndex > currentIndex) {
            tempPredData[labelIndex] = pred.temperature;
            humPredData[labelIndex] = pred.humidity;
            lightPredData[labelIndex] = pred.light;
            mq135PredData[labelIndex] = pred.mq135;
            zp01PredData[labelIndex] = pred.zp01;
            count++;
        }
    });
    
    console.log('Filtered predictions:', count, 'points mapped to chart (only future times)');
    
    updateChartWithPrediction(temperatureChart, tempPredData);
    updateChartWithPrediction(humidityChart, humPredData);
    updateChartWithPrediction(lightChart, lightPredData);
    updateChartWithPrediction(mq135Chart, mq135PredData);
    updateChartWithPrediction(zp01Chart, zp01PredData);
    
    updateChartsYAxisWithPrediction(predictions);
}

function updateChartWithPrediction(chart, predData) {
    if (!chart) return;
    
    if (chart.data.datasets.length < 2) {
        chart.data.datasets.push({
            label: 'Prediction',
            data: [],
            borderColor: 'rgba(255, 152, 0, 1)',
            backgroundColor: 'rgba(255, 152, 0, 0.1)',
            borderDash: [5, 5],
            tension: 0.3,
            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 2
        });
    }
    
    chart.data.datasets[1].data = predData;
    chart.update('none');
}

function updateChartsYAxisWithPrediction(predictions) {
    if (!predictions || predictions.length === 0) return;
    
    console.log('Updating Y-axis with prediction data...');
    
    const predStats = {
        temperature: { min: Infinity, max: -Infinity },
        humidity: { min: Infinity, max: -Infinity },
        light: { min: Infinity, max: -Infinity },
        mq135: { min: Infinity, max: -Infinity },
        zp01: { min: Infinity, max: -Infinity }
    };
    
    predictions.forEach(function(pred) {
        predStats.temperature.min = Math.min(predStats.temperature.min, pred.temperature);
        predStats.temperature.max = Math.max(predStats.temperature.max, pred.temperature);
        predStats.humidity.min = Math.min(predStats.humidity.min, pred.humidity);
        predStats.humidity.max = Math.max(predStats.humidity.max, pred.humidity);
        predStats.light.min = Math.min(predStats.light.min, pred.light);
        predStats.light.max = Math.max(predStats.light.max, pred.light);
        predStats.mq135.min = Math.min(predStats.mq135.min, pred.mq135);
        predStats.mq135.max = Math.max(predStats.mq135.max, pred.mq135);
        predStats.zp01.min = Math.min(predStats.zp01.min, pred.zp01);
        predStats.zp01.max = Math.max(predStats.zp01.max, pred.zp01);
    });
    
    const combinedStats = {};
    Object.keys(predStats).forEach(function(key) {
        const existingMin = statsData && statsData[key] ? statsData[key].min : null;
        const existingMax = statsData && statsData[key] ? statsData[key].max : null;
        
        combinedStats[key] = {
            min: existingMin !== null ? Math.min(existingMin, predStats[key].min) : predStats[key].min,
            max: existingMax !== null ? Math.max(existingMax, predStats[key].max) : predStats[key].max
        };
    });
    
    updateChartsYAxis(combinedStats);
}