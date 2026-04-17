// TomatoGuard Dashboard 

let soilDoughnut, tempDoughnut, humidityDoughnut;
let soilBar, tempBar, humidityBar;
let notificationLastTime = {};

// Optimal values for maximum yield
const OPTIMAL_VALUES = {
    soil: {
        min: 60,
        max: 80,
        optimal: "60-80%",
        name: "Soil Moisture",
        icon: "💧",
        unit: "%",
        impact: "Tomatoes need 60-80% moisture to absorb nutrients effectively and grow strong. Below 60%, plants get stunted and risking death. Above 80%, roots can rot from overwatering.",
        tips: "<b>Quick Tips:</b><br>• Aim for 60-80%: Healthy roots.<br>• Under 60%: Water now!<br>• Over 80%: Let it dry out."
    },
    temp: {
        min: 20,
        max: 30,
        optimal: "20-30°C",
        name: "Temperature",
        icon: "🌡️",
        unit: "°C",
        impact: "Tomatoes grow best between 20-30°C. Extreme heat (above 30°C) can cause blossoms to drop, while cold (below 20°C) stunts development.",
        tips: "<b>Quick Tips:</b><br>• Aim for 20-30°C: Perfect development.<br>• Under 20°C: Too cold.<br>• Over 30°C: Too hot—provide shade!"
    },
    humidity: {
        min: 50,
        max: 70,
        optimal: "50-70%",
        name: "Humidity",
        icon: "❄️",
        unit: "%",
        impact: "Ideal humidity is 50-70%. High humidity (>70%) increases fungal risk. Low humidity (<50%) can lead to pollination issues.",
        tips: "<b>Quick Tips:</b><br>• Aim for 50-70%: Disease-free.<br>• Under 50%: Air too dry—wilting possible.<br>• Over 70%: High disease risk—improve ventilation!"
    }
};

// Helper function to convert UTC to Nepal local time (GMT+5:45)
function formatToNepalTime(isoTimestamp) {
    if (!isoTimestamp || isoTimestamp === '--' || isoTimestamp === null) {
        return '--:--:--';
    }

    try {
        const utcDate = new Date(isoTimestamp + 'Z');
        if (isNaN(utcDate.getTime())) {
            return '--:--:--';
        }

        const hours = utcDate.getHours().toString().padStart(2, '0');
        const minutes = utcDate.getMinutes().toString().padStart(2, '0');
        const seconds = utcDate.getSeconds().toString().padStart(2, '0');

        return `${hours}:${minutes}:${seconds}`;
    } catch (e) {
        console.error('Error formatting time:', e);
        return '--:--:--';
    }
}

// Get color based on value and type
const getColor = (value, type) => {
    const optimal = OPTIMAL_VALUES[type];
    if (!optimal) return '#4caf50';

    if (type === 'temp') {
        const hour = new Date().getHours();
        const minTemp = (hour >= 7 && hour < 19) ? 21 : 16;
        const maxTemp = (hour >= 7 && hour < 19) ? 27 : 25;
        return (value < minTemp) ? 'blue' : (value > maxTemp) ? 'red' : '#b6c036';
    }
    if (type === 'soil') {
        return (value < optimal.min) ? 'red' : (value > optimal.max) ? 'orange' : '#9d25a8';
    }
    if (type === 'humidity') {
        return (value < optimal.min) ? 'orange' : (value > optimal.max) ? 'red' : '#1759b5';
    }
    return '#4caf50';
};

// Update status messages with optimal values
const updateStatus = (elementId, value, type, wateringRec = null) => {
    const el = document.getElementById(elementId);
    if (!el) return;

    const optimal = OPTIMAL_VALUES[type];
    let msg = '', color = '';

    if (type === 'soil') {
        const soilVal = parseFloat(value);
        if (soilVal < optimal.min) {
            msg = soilVal < 40 ? "🔴 URGENT: Too Dry!" : "⚠️ Too Dry!";
            color = 'red';
        } else if (soilVal > optimal.max) {
            msg = soilVal > 85 ? "🔴 URGENT: Too Wet!" : "⚠️ Too Wet!";
            color = 'orange';
        } else {
            msg = "✅ Optimal Status";
            color = 'green';
        }
    } else if (type === 'temp') {
        const tempVal = parseFloat(value);
        if (tempVal < optimal.min) {
            msg = "❄️ Too Cold!";
            color = 'blue';
        } else if (tempVal > optimal.max) {
            msg = "🔥 Too Hot!";
            color = 'red';
        } else {
            msg = "✅ Optimal Status";
            color = 'green';
        }
    } else if (type === 'humidity') {
        const humVal = parseFloat(value);
        if (humVal < optimal.min) {
            msg = "⚠️ Too Dry!";
            color = 'orange';
        } else if (humVal > optimal.max) {
            msg = "❄️ Too Humid!";
            color = 'red';
        } else {
            msg = "✅ Optimal Status";
            color = 'green';
        }
    }

    // Update Title (Top)
    const titleEl = document.getElementById(`${type}Title`);
    if (titleEl) {
        titleEl.innerHTML = `<span>${optimal.icon}</span> ${optimal.name}`;
    }

    el.innerHTML = `
        <div style="font-size: 0.85rem; color: #666; text-transform: uppercase; font-weight: 600;">Current</div>
        <div style="font-weight: 800; font-size: 1.1rem; margin-bottom: 0.4rem; color: ${color};">${value}${optimal.unit}</div>
        <div style="font-size: 0.85rem; color: #666; text-transform: uppercase; font-weight: 600;">Optimal</div>
        <div style="font-weight: 700; font-size: 1.05rem; margin-bottom: 0.8rem; color: #333;">${optimal.optimal}</div>
        <div style="font-weight: 800; font-size: 0.95rem; padding: 0.4rem; border-radius: 0.4rem; color: ${color}; background: ${color === 'green' ? '#e8f5e9' : (color === 'red' || color === 'blue' ? '#ffebee' : '#fff3e0')};">${msg}</div>
    `;
    el.style.textAlign = 'center';


    // Update Premium Overlays (Horticultural Advice Only)
    const prefix = type === 'temp' ? 'temp' : type;
    const adviceEl = document.getElementById(`${prefix}AdviceOverlay`);

    if (adviceEl) {
        let msgAdvice = optimal.impact;

        if (optimal.tips) {
            msgAdvice += `<div style="margin-top: 1rem; padding: 0.75rem; background: rgba(46, 125, 50, 0.08); border-radius: 0.5rem; border-left: 3px solid #2e7d32;">${optimal.tips}</div>`;
        }
        adviceEl.innerHTML = msgAdvice;
    }
};


// Create doughnut chart with tooltip showing optimal values
const createDoughnut = (ctx, value, type, color) => {
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js not loaded. Skipping doughnut chart for', type);
        return null;
    }
    const optimal = OPTIMAL_VALUES[type];

    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            datasets: [{
                data: [value, 100 - value],
                backgroundColor: [color, '#e8f5e9'],
                borderWidth: 1
            }]
        },
        options: {
            cutout: '70%',
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: true,
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: '#2e7d32',
                    bodyColor: '#333',
                    borderColor: '#2e7d32',
                    borderWidth: 1,
                    padding: 10,
                    displayColors: false,
                    callbacks: {
                        label: (context) => `Value: ${context.raw}${optimal.unit}`
                    }
                }
            },

            animation: {
                onComplete: function () {
                    const chart = this;
                    const ctx = chart.ctx;
                    ctx.save();
                    ctx.font = 'bold 1.2em sans-serif';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillStyle = '#333';
                    let displayValue = value;
                    if (type === 'temp') {
                        displayValue = Math.round(value) + '°C';
                    } else {
                        displayValue = Math.round(value) + '%';
                    }
                    ctx.fillText(displayValue, chart.width / 2, chart.height / 2);
                    ctx.restore();
                }
            }
        }
    });
};

// Create bar chart with tooltip showing optimal values
const createBar = (ctx, labels, maxData, minData, type) => {
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js not loaded. Skipping bar chart for', type);
        return null;
    }

    const optimal = OPTIMAL_VALUES[type];
    const optimalVal = parseFloat(optimal.optimal.split('-')[1]) || 50;

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Daily Max',
                    data: maxData,
                    backgroundColor: 'rgba(231, 76, 60, 0.7)',
                    borderColor: '#e74c3c',
                    borderWidth: 1,
                    borderRadius: 4,
                    categoryPercentage: 0.8,
                    barPercentage: 0.95
                },
                {
                    label: 'Daily Min',
                    data: minData,
                    backgroundColor: 'rgba(52, 152, 219, 0.7)',
                    borderColor: '#3498db',
                    borderWidth: 1,
                    borderRadius: 4,
                    categoryPercentage: 0.8,
                    barPercentage: 0.95
                },
                {
                    label: 'Optimal Target',
                    data: labels.map(() => optimalVal),
                    backgroundColor: 'rgba(46, 125, 50, 0.2)',
                    borderColor: '#2e7d32',
                    borderWidth: 2,
                    type: 'line',
                    pointRadius: 0,
                    fill: false,
                    borderDash: [5, 5]
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: 0 },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: { boxWidth: 12, font: { size: 10 } }
                },
                tooltip: {
                    enabled: true,
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    offset: false,
                    bounds: 'ticks',
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45,
                        font: { size: 10 },
                        padding: 0
                    }
                },
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: { display: true, text: optimal.unit, font: { weight: 'bold' } },
                    grid: { color: '#f0f0f0' }
                }
            }
        }
    });
};

// Main fetch function
const fetchSensorData = async () => {
    try {
        const startDate = document.getElementById('chartStartDate')?.value;
        const endDate = document.getElementById('chartEndDate')?.value;

        let historyUrl = '/api/history';
        if (startDate && endDate) {
            historyUrl += `?start_date=${startDate}&end_date=${endDate}`;
        }

        console.log(`📊 Fetching sensor data from: ${historyUrl}`);

        const latestRes = await fetch('/api/latest');
        const historyRes = await fetch(historyUrl);

        if (latestRes.status === 401 || historyRes.status === 401) {
            window.location.href = '/login';
            return;
        }

        const latest = await latestRes.json();
        const history = await historyRes.json();

        console.log('✅ Latest data:', latest);
        console.log('✅ History data:', history);

        const labels = history.days || [];

        if (!labels || labels.length === 0) {
            console.warn('⚠️ No historical data available for date range:', { startDate, endDate });
        }

        // 1. Update Status Labels IMMEDIATELY (Fail-safe)
        updateStatus('soilStatus', latest.soil, 'soil', globalWateringRec);
        updateStatus('tempStatus', latest.temperature, 'temp');
        updateStatus('humidityStatus', latest.humidity, 'humidity');

        // Check watering recommendation in background
        checkWateringRecommendation();

        // Check if we have labels/data
        if (!labels || labels.length === 0) {
            console.warn('⚠️ No history data collected. Creating placeholders for charts to show structure.');
            // If no data, create placeholder to show trend structure
            for (let i = 0; i < 7; i++) {
                const d = new Date();
                d.setDate(d.getDate() - (6 - i));
                labels.push(d.toISOString().split('T')[0]);
            }
            // Add mock data so charts show structure
            if (!history.temperature) history.temperature = {};
            if (!history.humidity) history.humidity = {};
            if (!history.soil) history.soil = {};

            history.temperature.max = labels.map(() => 25);
            history.temperature.min = labels.map(() => 18);
            history.humidity.max = labels.map(() => 65);
            history.humidity.min = labels.map(() => 45);
            history.soil.max = labels.map(() => 70);
            history.soil.min = labels.map(() => 55);
        }

        // 2. Wrap Chart logic in try-catch to prevent whole UI crash
        try {
            // Soil Chart
            const soilDoughCtx = document.getElementById('soilDoughnut')?.getContext('2d');
            if (soilDoughCtx) {
                const soilColor = getColor(latest.soil, 'soil');
                if (!soilDoughnut) {
                    soilDoughnut = createDoughnut(soilDoughCtx, latest.soil, 'soil', soilColor);
                } else {
                    soilDoughnut.data.datasets[0].data = [latest.soil, 100 - latest.soil];
                    soilDoughnut.data.datasets[0].backgroundColor = [soilColor, '#e8f5e9'];
                    soilDoughnut.update();
                }
            }

            const soilBarCtx = document.getElementById('soilBar')?.getContext('2d');
            if (soilBarCtx) {
                if (!soilBar) {
                    soilBar = createBar(soilBarCtx, labels, history.soil.max, history.soil.min, 'soil');
                } else {
                    soilBar.data.labels = labels;
                    soilBar.data.datasets[0].data = history.soil.max;
                    soilBar.data.datasets[1].data = history.soil.min;
                    soilBar.data.datasets[2].data = labels.map(() => parseFloat(OPTIMAL_VALUES.soil.optimal.split('-')[1]));
                    soilBar.update();
                }
            }

            // Temperature Chart
            const tempDoughCtx = document.getElementById('tempDoughnut')?.getContext('2d');
            if (tempDoughCtx) {
                const tempColor = getColor(latest.temperature, 'temp');
                if (!tempDoughnut) {
                    tempDoughnut = createDoughnut(tempDoughCtx, latest.temperature, 'temp', tempColor);
                } else {
                    tempDoughnut.data.datasets[0].data = [latest.temperature, 100 - latest.temperature];
                    tempDoughnut.data.datasets[0].backgroundColor = [tempColor, '#e8f5e9'];
                    tempDoughnut.update();
                }
            }

            const tempBarCtx = document.getElementById('tempBar')?.getContext('2d');
            if (tempBarCtx) {
                if (!tempBar) {
                    tempBar = createBar(tempBarCtx, labels, history.temperature.max, history.temperature.min, 'temp');
                } else {
                    tempBar.data.labels = labels;
                    tempBar.data.datasets[0].data = history.temperature.max;
                    tempBar.data.datasets[1].data = history.temperature.min;
                    tempBar.data.datasets[2].data = labels.map(() => parseFloat(OPTIMAL_VALUES.temp.optimal.split('-')[1]));
                    tempBar.update();
                }
            }

            // Humidity Chart
            const humidityDoughCtx = document.getElementById('humidityDoughnut')?.getContext('2d');
            if (humidityDoughCtx) {
                const humidityColor = getColor(latest.humidity, 'humidity');
                if (!humidityDoughnut) {
                    humidityDoughnut = createDoughnut(humidityDoughCtx, latest.humidity, 'humidity', humidityColor);
                } else {
                    humidityDoughnut.data.datasets[0].data = [latest.humidity, 100 - latest.humidity];
                    humidityDoughnut.data.datasets[0].backgroundColor = [humidityColor, '#e8f5e9'];
                    humidityDoughnut.update();
                }
            }

            const humidityBarCtx = document.getElementById('humidityBar')?.getContext('2d');
            if (humidityBarCtx) {
                if (!humidityBar) {
                    humidityBar = createBar(humidityBarCtx, labels, history.humidity.max, history.humidity.min, 'humidity');
                } else {
                    humidityBar.data.labels = labels;
                    humidityBar.data.datasets[0].data = history.humidity.max;
                    humidityBar.data.datasets[1].data = history.humidity.min;
                    humidityBar.data.datasets[2].data = labels.map(() => parseFloat(OPTIMAL_VALUES.humidity.optimal.split('-')[1]));
                    humidityBar.update();
                }
            }
        } catch (chartErr) {
            console.warn('Dashboard charts failed to render, but status data is loaded:', chartErr);
        }

    } catch (err) {
        console.error('Failed to fetch sensor data:', err);
    }
};

// Watering Recommendation & Pair Device Logic
let globalWateringRec = null;

async function pairDevice(chipId) {
    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        const res = await fetch('/api/pair-device', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ chip_id: chipId })
        });
        const data = await res.json();
        if (data.success) {
            showSuccess(data.message);
            setTimeout(() => location.reload(), 1500);
        } else {
            showError(data.error);
        }
    } catch (err) {
        showError('Failed to pair device');
    }
}

async function checkWateringRecommendation() {
    try {
        const res = await fetch('/api/watering-recommendation');
        const data = await res.json();
        if (!data.has_data) return;

        globalWateringRec = data.recommendation;
        const soil = data.soil_moisture;

        // Update UI if soil status element exists
        updateStatus('soilStatus', soil, 'soil', globalWateringRec);

        if (data.should_notify && globalWateringRec.action !== 'normal') {
            sendBrowserNotification(globalWateringRec, soil);
        }
    } catch (err) {
        console.error('Error checking watering:', err);
    }
}


function sendBrowserNotification(rec, soilMoisture) {
    const now = Date.now();
    const lastTime = notificationLastTime[rec.action] || 0;

    if (now - lastTime < 3600000) return;

    notificationLastTime[rec.action] = now;

    // Get CSRF token from meta tag or form
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
        document.querySelector('input[name="csrf_token"]')?.value;

    fetch('/api/notification-log', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken  // Add this
        },
        body: JSON.stringify({
            action: rec.action,
            message: rec.message,
            soil_moisture: soilMoisture
        }),
        credentials: 'same-origin'  // Ensure cookies are sent
    })
        .then(response => {
            if (!response.ok) {
                console.error('Notification log failed:', response.status, response.statusText);
                return response.text().then(text => console.error('Response:', text));
            }
            return response.json();
        })
        .then(data => {
            if (data && !data.success) {
                console.warn('Notification log returned error:', data.error);
            }
        })
        .catch(err => console.error('Error logging notification:', err));

    // Rest of your notification code...
    if (Notification.permission === 'granted') {
        const notification = new Notification('🌱 TomatoGuard Alert', {
            body: `${rec.icon} ${rec.message}\nSoil: ${soilMoisture}%\nOptimal: 60-80%\n${rec.advice}`,
            tag: rec.action,
            requireInteraction: rec.action.includes('urgent')
        });

        notification.onclick = () => window.focus();
        setTimeout(() => notification.close(), rec.action.includes('urgent') ? 15000 : 8000);
    }
}


// Cost Calculator JavaScript

document.addEventListener('DOMContentLoaded', function () {
    // Initialize date input and period selector for new UI
    const today = new Date();
    const baseDateInput = document.getElementById('chartBaseDate');
    const periodSelect = document.getElementById('chartPeriodSelect');

    if (baseDateInput) baseDateInput.value = today.toISOString().split('T')[0];
    if (periodSelect) periodSelect.value = '7days';

    // Calculate initial date range (last 7 days)
    const sevenDaysAgo = new Date(today);
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

    const startInput = document.getElementById('chartStartDate');
    const endInput = document.getElementById('chartEndDate');

    const startDateStr = sevenDaysAgo.toISOString().split('T')[0];
    const endDateStr = today.toISOString().split('T')[0];

    if (startInput) {
        startInput.value = startDateStr;
        console.log(`📅 Set chartStartDate to: ${startDateStr}`, startInput);
    } else {
        console.error('❌ chartStartDate input not found!');
    }
    if (endInput) {
        endInput.value = endDateStr;
        console.log(`📅 Set chartEndDate to: ${endDateStr}`, endInput);
    } else {
        console.error('❌ chartEndDate input not found!');
    }

    console.log('🚀 Calling fetchSensorData() on page load...');
    // Fetch initial data
    fetchSensorData();

    // Filter button listener
    document.getElementById('updateChartsBtn')?.addEventListener('click', function () {
        const baseDate = new Date(document.getElementById('chartBaseDate').value || today.toISOString().split('T')[0]);
        const period = document.getElementById('chartPeriodSelect').value;

        console.log(`🔧 Filter button clicked. Base date:`, baseDate.toISOString().split('T')[0], 'Period:', period);

        // Calculate date range based on period
        let startDate = new Date(baseDate);
        let endDate = new Date(baseDate);

        switch (period) {
            case '7days':
                startDate.setDate(startDate.getDate() - 7);
                break;
            case '1month':
                startDate.setDate(startDate.getDate() - 30);
                break;
            case '2months':
                startDate.setDate(startDate.getDate() - 60);
                break;
            case '3months':
                startDate.setDate(startDate.getDate() - 90);
                break;
            case '6months':
                startDate.setDate(startDate.getDate() - 180);
                break;
            case '1year':
                startDate.setDate(startDate.getDate() - 365);
                break;
        }

        // Update hidden inputs for API call
        const startInput = document.getElementById('chartStartDate');
        const endInput = document.getElementById('chartEndDate');

        if (startInput) startInput.value = startDate.toISOString().split('T')[0];
        if (endInput) endInput.value = endDate.toISOString().split('T')[0];

        // Destroy existing bar charts to re-create them with new data
        if (soilBar) { soilBar.destroy(); soilBar = null; }
        if (tempBar) { tempBar.destroy(); tempBar = null; }
        if (humidityBar) { humidityBar.destroy(); humidityBar = null; }

        fetchSensorData();
    });

    // Initialize event listeners
    initEventListeners();

    // Auto-calculate break-even price on input changes
    const investmentInputs = ['seeds', 'fertilizer', 'water', 'yield'];
    investmentInputs.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('input', updateBreakEvenPreview);
        }
    });
});

function initEventListeners() {
    // Reset button functionality
    const resetBtn = document.getElementById('resetBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', resetCalculator);
    }

    // Investment form submission
    const investmentForm = document.getElementById('investmentForm');
    if (investmentForm) {
        investmentForm.addEventListener('submit', function (e) {
            showLoading(this);
        });
    }

    // Profit form submission
    const profitForm = document.getElementById('profitForm');
    if (profitForm) {
        profitForm.addEventListener('submit', function (e) {
            showLoading(this);
        });
    }

    // Real-time price validation
    const marketPrice = document.getElementById('marketPrice');
    if (marketPrice) {
        marketPrice.addEventListener('input', validateMarketPrice);
        marketPrice.addEventListener('change', validateMarketPrice);
    }
}

function updateBreakEvenPreview() {
    const seeds = parseFloat(document.getElementById('seeds')?.value) || 0;
    const fertilizer = parseFloat(document.getElementById('fertilizer')?.value) || 0;
    const water = parseFloat(document.getElementById('water')?.value) || 0;
    const yield_ = parseFloat(document.getElementById('yield')?.value) || 0;

    if (yield_ > 0) {
        const totalCost = seeds + fertilizer + water;
        const breakEven = totalCost / yield_;
        const recommended = (totalCost * 1.3) / yield_;

        const breakEvenSpan = document.getElementById('breakEvenPrice');
        const recommendedSpan = document.getElementById('recommendedPrice');

        if (breakEvenSpan) {
            breakEvenSpan.textContent = breakEven.toFixed(2);
        }
        if (recommendedSpan) {
            recommendedSpan.textContent = recommended.toFixed(2);
        }

        // Add visual feedback for high cost per kg
        if (breakEven > 100) {
            showWarning('High cost per kg detected. Consider reducing input costs.');
        }
    }
}

function validateMarketPrice() {
    const priceInput = document.getElementById('marketPrice');
    if (!priceInput) return;

    let price = parseFloat(priceInput.value);
    const maxPrice = 500;
    const breakEvenPrice = parseFloat(document.getElementById('breakEvenPrice')?.textContent) || 0;

    if (price > maxPrice) {
        priceInput.value = maxPrice;
        showError(`Market price cannot exceed Rs ${maxPrice}`);
        price = maxPrice;
    }

    if (price < 0) {
        priceInput.value = 0;
        showError('Market price cannot be negative');
        price = 0;
    }

    // Show price comparison feedback
    if (price > 0 && breakEvenPrice > 0) {
        const priceDifference = price - breakEvenPrice;
        const feedbackDiv = document.getElementById('priceFeedback');

        if (priceDifference > 0) {
            showSuccess(`Great! You're making Rs ${priceDifference.toFixed(2)} profit per kg`);
        } else if (priceDifference < 0) {
            showWarning(`You're losing Rs ${Math.abs(priceDifference).toFixed(2)} per kg. Consider raising your price.`);
        }
    }
}

function resetCalculator() {
    if (confirm('Are you sure you want to reset all calculations? This will clear all your data.')) {
        // Clear all input fields instantly
        const inputs = ['seeds', 'fertilizer', 'water', 'yield', 'marketPrice'];
        inputs.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });

        showLoading(null);

        // Create a form to submit reset request
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = window.location.href;

        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrf_token';
        csrfInput.value = document.querySelector('input[name="csrf_token"]').value;

        const resetInput = document.createElement('input');
        resetInput.type = 'hidden';
        resetInput.name = 'reset';
        resetInput.value = 'true';

        form.appendChild(csrfInput);
        form.appendChild(resetInput);
        document.body.appendChild(form);
        form.submit();
    }
}

function showLoading(form) {
    if (form) {
        form.classList.add('loading');
        setTimeout(() => {
            form.classList.remove('loading');
        }, 3000);
    }
}

function showError(message) {
    showToast(message, 'error');
}

function showWarning(message) {
    showToast(message, 'warning');
}

function showSuccess(message) {
    showToast(message, 'success');
}

function showToast(message, type = 'info') {
    // Remove existing toast if any
    const existingToast = document.querySelector('.toast-notification');
    if (existingToast) {
        existingToast.remove();
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast-notification ${type}`;
    toast.innerHTML = `
        <div class="toast-content">
            <span class="toast-icon">${getToastIcon(type)}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close">&times;</button>
        </div>
    `;

    document.body.appendChild(toast);

    // Toast style handled in style.css


    // Add close button functionality
    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => {
        toast.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    });

    // Auto remove after 5 seconds
    setTimeout(() => {
        if (toast.parentNode) {
            toast.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }
    }, 5000);
}

function getToastIcon(type) {
    switch (type) {
        case 'error': return '❌';
        case 'warning': return '⚠️';
        case 'success': return '✅';
        default: return 'ℹ️';
    }
}

// Format currency helper
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-NP', {
        style: 'currency',
        currency: 'NPR',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}

// Format percentage helper
function formatPercentage(value) {
    return `${value.toFixed(2)}%`;
}

// Export functions for debugging (optional)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatCurrency,
        formatPercentage,
        validateMarketPrice,
        updateBreakEvenPreview
    };
}

// Initialize - Update every 5 minutes instead of 30 seconds
fetchSensorData();
setInterval(fetchSensorData, 300000); // 5 minutes

setInterval(checkWateringRecommendation, 300000); // 5 minutes