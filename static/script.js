document.addEventListener('DOMContentLoaded', () => {
    fetchData();
    setupTabs();
});

let currentStocks = [];
let activeStrategy = 'all';

async function fetchData() {
    const list = document.getElementById('stock-list');
    const indicator = document.querySelector('.status-indicator');

    try {
        indicator.classList.add('loading');
        // Fetch screened data (which includes strategies metadata)
        const response = await fetch('/api/screening');
        currentStocks = await response.json();

        renderHeatmap(currentStocks);
        renderStocks();

    } catch (error) {
        list.innerHTML = `<p style="text-align:center; color:var(--down-color);">CONNECTION ERROR</p>`;
        console.error('Error fetching stocks:', error);
    } finally {
        indicator.classList.remove('loading');
    }
}

function setupTabs() {
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(btn => {
        btn.addEventListener('click', () => {
            // UI Toggle
            tabs.forEach(t => t.classList.remove('active'));
            btn.classList.add('active');

            // Logic
            activeStrategy = btn.dataset.strategy;
            renderStocks();
        });
    });
}

function renderHeatmap(stocks) {
    const container = document.getElementById('heatmap-scroll');
    container.innerHTML = '';

    // Sort by absolute change percent desc (hottest movers first)
    const sorted = [...stocks].sort((a, b) => Math.abs(b.change_percent) - Math.abs(a.change_percent));

    sorted.forEach(stock => {
        const div = document.createElement('div');
        div.className = 'heat-cell';

        // Color scale calculation (-5% to +5%)
        const intensity = Math.min(Math.abs(stock.change_percent) / 5, 1);
        const baseColor = stock.change_percent >= 0 ?
            `rgba(63, 185, 80, ${0.3 + intensity * 0.7})` :
            `rgba(248, 81, 73, ${0.3 + intensity * 0.7})`;

        // AI Score Badge for heatmap
        const aiBadge = stock.ai_score ? `<span class="ai-mini-badge" style="background:${getScoreColor(stock.ai_score)}">${stock.ai_score}</span>` : '';

        div.style.backgroundColor = baseColor;
        div.innerHTML = `
            ${aiBadge}
            <span class="symbol-code">${stock.symbol}</span>
            <span class="change-val">${stock.change_percent > 0 ? '+' : ''}${stock.change_percent}%</span>
        `;
        div.onclick = () => document.getElementById(`card-${stock.symbol}`).scrollIntoView({ behavior: "smooth" });
        container.appendChild(div);
    });
}

function renderStocks() {
    const list = document.getElementById('stock-list');
    list.innerHTML = '';

    const filtered = activeStrategy === 'all' ?
        currentStocks :
        currentStocks.filter(s => s.matched_strategies && s.matched_strategies.includes(activeStrategy));

    if (filtered.length === 0) {
        list.innerHTML = `<p style="text-align:center; padding:20px; color:var(--text-secondary);">条件に一致する銘柄はありません。</p>`;
        return;
    }

    filtered.forEach(stock => {
        const isUp = stock.change_percent >= 0;
        const colorClass = isUp ? 'up' : 'down';
        const sign = isUp ? '+' : '';

        // Badges Generation
        let badgesHtml = '';
        if (stock.matched_strategies) {
            stock.matched_strategies.forEach(st => {
                const badgeNames = {
                    'value_invest': '💎 VALUE',
                    'high_dividend': '💰 YIELD',
                    'short_squeeze': '🔥 SQUEEZE',
                    'rebound': '⚡ REBOUND'
                };
                if (badgeNames[st]) {
                    badgesHtml += `<span class="badge ${st}">${badgeNames[st]}</span>`;
                }
            });
        }
        if (stock.volume_spike) badgesHtml += '<span class="badge" style="border-color:#fff; color:#fff;">📢 VOL</span>';

        // Meters Calculation
        const rsiVal = stock.rsi || 50;
        const rsiWidth = Math.min(Math.max(rsiVal, 0), 100);

        const card = document.createElement('div');
        card.id = `card-${stock.symbol}`;
        card.className = 'stock-card';
        card.innerHTML = `
            <div class="card-header">
                <div class="stock-info">
                    <h2>${stock.symbolname}</h2>
                    <span class="code">${stock.symbol}</span>
                </div>
                <div class="price-box">
                    <span class="current-price ${colorClass}">${stock.currentprice.toLocaleString()}</span>
                    <span class="change-percent ${colorClass}">${sign}${stock.change_percent}%</span>
                </div>
            </div>
            
            <div class="badges">${badgesHtml}</div>

                <div class="detail-item">
                    <span class="detail-label">RSI(${Math.round(rsiVal)})</span>
                    <div class="meter-container">
                        <div class="meter-fill" style="width: ${rsiWidth}%; background: ${getRsiColor(rsiVal)}"></div>
                    </div>
                </div>
                <!-- AI Insight Column -->
                <div class="detail-item ai-insight">
                    <span class="detail-label">AI SCORE</span>
                    <span class="detail-value" style="color:${getScoreColor(stock.ai_score)}">${stock.ai_score || '-'}</span>
                </div>
            </div>

            <div class="actions">
                <button class="btn btn-primary" onclick="copyPrompt('${stock.symbol}')">
                    <span>✨ AI分析プロンプト</span>
                </button>
                <button class="btn" onclick="viewReport('${stock.symbol}')">
                    <span>📄 レポート</span>
                </button>
                <button class="btn" onclick="openApp('${stock.symbol}')">
                    <span>📱 アプリ</span>
                </button>
            </div>
        `;
        list.appendChild(card);
    });
}

function getRsiColor(val) {
    if (val <= 30) return 'cyan'; // Oversold
    if (val >= 70) return 'magenta'; // Overbought
    return 'var(--accent-color)';
}

function getScoreColor(score) {
    if (!score) return 'var(--text-secondary)';
    if (score >= 7) return 'var(--up-color)';
    if (score <= 4) return 'var(--down-color)';
    return 'var(--accent-color)';
}

async function copyPrompt(symbol) {
    const btn = event.currentTarget;
    const originalText = btn.innerHTML;

    try {
        // 1. Get Prompt for Clipboard
        const responsePrompt = await fetch(`/api/prompt/${symbol}`);
        const dataPrompt = await responsePrompt.json();

        // 2. Trigger Server-side Report Saving (Fire and Forget)
        fetch(`/api/analyze/${symbol}`, { method: 'POST' });

        // Copy process
        if (navigator.clipboard) {
            await navigator.clipboard.writeText(dataPrompt.prompt);
        } else {
            const textArea = document.getElementById('clipboard-area');
            textArea.value = dataPrompt.prompt;
            textArea.select();
            document.execCommand('copy');
        }

        btn.innerHTML = `<span>✅ SAVED & COPIED</span>`;
        setTimeout(() => btn.innerHTML = originalText, 2000);

    } catch (error) {
        console.error('Error copying prompt:', error);
    }
}

function openApp(symbol) {
    window.open(`https://finance.yahoo.co.jp/quote/${symbol}.T`, '_blank');
}

async function viewReport(symbol) {
    const overlay = document.getElementById('analysis-overlay');
    const title = document.getElementById('overlay-title');
    const reportDiv = document.getElementById('report-content');

    // 1. Show UI Loading
    overlay.classList.add('active');
    title.innerText = `ANALYZING: ${symbol}`;
    reportDiv.innerHTML = '<p>Loading Analysis...</p>';

    try {
        // 2. Fetch History & Render Chart
        const historyResponse = await fetch(`/api/history/${symbol}`);
        const historyData = await historyResponse.json();
        renderChart(historyData);

        // 3. Fetch AI Report Content
        const analysisResponse = await fetch(`/api/analysis/${symbol}`);
        if (analysisResponse.ok) {
            const analysisData = await analysisResponse.json();
            renderReport(analysisData);
        } else {
            reportDiv.innerHTML = '<p style="color:var(--text-secondary)">分析データが見つかりません。プロンプトを実行して生成してください。</p>';
        }

    } catch (error) {
        console.error('Error loading analysis view:', error);
        reportDiv.innerHTML = '<p style="color:var(--down-color)">ERROR LOADING ANALYSIS</p>';
    }
}

function closeAnalysis() {
    document.getElementById('analysis-overlay').classList.remove('active');
    if (window.currentChart) {
        window.currentChart.destroy();
        window.currentChart = null;
    }
}

function renderChart(data) {
    const options = {
        series: [{
            name: 'Price',
            data: data.map(p => ({
                x: new Date(p.time),
                y: [p.open, p.high, p.low, p.close]
            }))
        }],
        chart: {
            type: 'candlestick',
            height: '100%',
            background: 'transparent',
            toolbar: { show: false }
        },
        theme: { mode: 'dark' },
        xaxis: { type: 'datetime' },
        yaxis: { tooltip: { enabled: true } },
        grid: { borderColor: '#30363d' }
    };

    if (window.currentChart) {
        window.currentChart.destroy();
    }

    const container = document.querySelector("#chart-container");
    container.innerHTML = "";
    window.currentChart = new ApexCharts(container, options);
    window.currentChart.render();
}

function renderReport(data) {
    const reportDiv = document.getElementById('report-content');
    const content = data.content;

    let html = `
        <div class="ai-summary">
            <span class="badge" style="background:var(--accent-color); color:white">SCORE: ${data.score}</span>
            <p style="font-weight:700; margin-top:10px">${content.summary || ''}</p>
        </div>
        <div class="ai-reasoning">${marked.parse(content.reasoning || content.text || '')}</div>
    `;

    if (content.risks) {
        html += `<h3>RISKS</h3><ul>${content.risks.map(r => `<li>${marked.parseInline(r)}</li>`).join('')}</ul>`;
    }

    reportDiv.innerHTML = html;
}

// Simple markdown subset parser (just for the demo)
function parseMarkdown(text) {
    return text
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/^\* (.*$)/gim, '<li>$1</li>')
        .replace(/\n/g, '<br>');
}
