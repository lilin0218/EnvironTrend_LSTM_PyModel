// 初始化图表
let temperatureChart, humidityChart, lightChart, gasChart, airQualityChart, noiseChart;

/**
 * 初始化图表
 */
function initCharts() {
    const ctxTemp = document.getElementById('temperature-chart').getContext('2d');
    const ctxHumidity = document.getElementById('humidity-chart').getContext('2d');
    const ctxLight = document.getElementById('light-chart').getContext('2d');
    const ctxGas = document.getElementById('gas-chart').getContext('2d');
    const ctxAirQuality = document.getElementById('air-quality-chart').getContext('2d');
    const ctxNoise = document.getElementById('noise-chart').getContext('2d');

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                beginAtZero: true
            }
        },
        animation: {
            duration: 1000
        }
    };

    temperatureChart = new Chart(ctxTemp, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '温度 (°C)',
                data: [],
                borderColor: 'rgba(255, 99, 132, 1)',
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                tension: 0.1
            }]
        },
        options: chartOptions
    });

    humidityChart = new Chart(ctxHumidity, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '湿度 (%)',
                data: [],
                borderColor: 'rgba(54, 162, 235, 1)',
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                tension: 0.1
            }]
        },
        options: chartOptions
    });

    lightChart = new Chart(ctxLight, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '光照 (lux)',
                data: [],
                borderColor: 'rgba(255, 206, 86, 1)',
                backgroundColor: 'rgba(255, 206, 86, 0.2)',
                tension: 0.1
            }]
        },
        options: chartOptions
    });

    gasChart = new Chart(ctxGas, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '有害气体',
                data: [],
                borderColor: 'rgba(75, 192, 192, 1)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                tension: 0.1
            }]
        },
        options: chartOptions
    });

    airQualityChart = new Chart(ctxAirQuality, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '空气质量',
                data: [],
                borderColor: 'rgba(153, 102, 255, 1)',
                backgroundColor: 'rgba(153, 102, 255, 0.2)',
                tension: 0.1
            }]
        },
        options: chartOptions
    });

    noiseChart = new Chart(ctxNoise, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '噪音 (dB)',
                data: [],
                borderColor: 'rgba(255, 159, 64, 1)',
                backgroundColor: 'rgba(255, 159, 64, 0.2)',
                tension: 0.1
            }]
        },
        options: chartOptions
    });
}

/**
 * 格式化时间戳
 * @param {string} timestamp - ISO格式的时间戳
 * @returns {string} 格式化后的时间字符串
 */
function formatTimestamp(timestamp) {
    if (!timestamp) return '未知';
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

/**
 * 获取最新数据
 */
function fetchLatestData() {
    fetch('http://localhost:5000/api/data')
        .then(response => response.json())
        .then(data => {
            if (data.length > 0) {
                const latest = data[0];
                document.getElementById('latest-data').innerHTML = `
                    <p><strong>时间:</strong> ${formatTimestamp(latest.timestamp)}</p>
                    <p><strong>温度:</strong> ${latest.temperature || '-'} °C</p>
                    <p><strong>湿度:</strong> ${latest.humidity || '-'} %</p>
                    <p><strong>光照:</strong> ${latest.light || '-'} lux</p>
                    <p><strong>有害气体:</strong> ${latest.gas || '-'}</p>
                    <p><strong>空气质量:</strong> ${latest.air_quality || '-'}</p>
                    <p><strong>噪音:</strong> ${latest.noise || '-'} dB</p>
                `;

                // 更新图表数据
                updateCharts(data);
            } else {
                document.getElementById('latest-data').innerHTML = '<p>暂无数据</p>';
            }
        })
        .catch(error => {
            console.error('Error fetching data:', error);
            document.getElementById('latest-data').innerHTML = '<p>获取数据失败</p>';
        });
}

/**
 * 更新图表数据
 * @param {Array} data - 环境数据数组
 */
function updateCharts(data) {
    // 限制数据点数量，只显示最近10条
    const recentData = data.slice(0, 10).reverse();
    const labels = recentData.map(item => formatTimestamp(item.timestamp));
    const temperatures = recentData.map(item => item.temperature);
    const humidities = recentData.map(item => item.humidity);
    const lights = recentData.map(item => item.light);
    const gases = recentData.map(item => item.gas);
    const airQualities = recentData.map(item => item.air_quality);
    const noises = recentData.map(item => item.noise);

    temperatureChart.data.labels = labels;
    temperatureChart.data.datasets[0].data = temperatures;
    temperatureChart.update();

    humidityChart.data.labels = labels;
    humidityChart.data.datasets[0].data = humidities;
    humidityChart.update();

    lightChart.data.labels = labels;
    lightChart.data.datasets[0].data = lights;
    lightChart.update();

    gasChart.data.labels = labels;
    gasChart.data.datasets[0].data = gases;
    gasChart.update();

    airQualityChart.data.labels = labels;
    airQualityChart.data.datasets[0].data = airQualities;
    airQualityChart.update();

    noiseChart.data.labels = labels;
    noiseChart.data.datasets[0].data = noises;
    noiseChart.update();
}

// 初始化
window.onload = function() {
    initCharts();
    fetchLatestData();
    // 每5秒刷新一次数据
    setInterval(fetchLatestData, 5000);
};