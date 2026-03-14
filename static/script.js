document.addEventListener('DOMContentLoaded', () => {
    fetchData();
    setupTabs();
    fetchWorkspaceLinks();
});

async function fetchWorkspaceLinks() {
    try {
        const response = await fetch('/api/workspace/links');
        const data = await response.json();
        
        if (data.sheet || data.root) {
            const container = document.getElementById('workspace-links');
            const console = document.getElementById('workspace-console');
            
            // Header Icons
            const sheetLink = document.getElementById('sheet-link');
            const driveLink = document.getElementById('drive-link');
            
            // Console Links
            const sheetLinkLarge = document.getElementById('sheet-link-large');
            const driveLinkLarge = document.getElementById('drive-link-large');
            
            if (data.sheet) {
                sheetLink.href = data.sheet;
                sheetLinkLarge.href = data.sheet;
            } else {
                sheetLink.style.display = 'none';
                sheetLinkLarge.parentElement.style.display = 'none';
            }
            
            if (data.root) {
                driveLink.href = data.root;
                driveLinkLarge.href = data.root;
            } else {
                driveLink.style.display = 'none';
                driveLinkLarge.parentElement.style.display = 'none';
            }
            
            container.style.display = 'flex';
            console.style.display = 'block';
        }
    } catch (error) {
        console.error('Error fetching workspace links:', error);
    }
}

async function toggleWatchlist(event, btn) {
    event.stopPropagation();
    const card = btn.closest('.stock-card');
    const symbol = card.dataset.symbol;
    const isWatched = btn.classList.contains('active');
    
    try {
        const method = isWatched ? 'DELETE' : 'POST';
        const response = await fetch(`/api/watchlist/${symbol}`, { method });
        if (response.ok) {
            btn.classList.toggle('active');
            if (isWatched) {
                // If we're on the watchlist tab, maybe remove card?
                // For now just change color
                btn.style.color = 'var(--text-muted)';
                btn.querySelector('svg').setAttribute('fill', 'none');
            } else {
                btn.style.color = '#FBBC04';
                btn.querySelector('svg').setAttribute('fill', '#FBBC04');
            }
        }
    } catch (error) {
        console.error('Watchlist toggle failed:', error);
    }
}

let currentStocks = [];
let watchlistData = [];
let scannerData = [];
let activeStrategy = 'all';

async function fetchData() {
    const list = document.getElementById('stock-list');
    const indicator = document.querySelector('.status-indicator');

    try {
        indicator.classList.add('loading');
        // Fetch screened data (which includes strategies metadata)
        const response = await fetch('/api/screening');
        watchlistData = await response.json();
        currentStocks = watchlistData;

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
            const strategy = btn.dataset.strategy;
            if (!strategy) return; // For select or other static elements

            // UI Toggle
            tabs.forEach(t => t.classList.remove('active'));
            btn.classList.add('active');

            // Logic
            activeStrategy = strategy;
            
            // Toggle Scanner Options
            const scannerOptions = document.getElementById('scanner-options');
            if (activeStrategy === 'scanner') {
                scannerOptions.style.display = 'block';
                if (scannerData.length === 0) {
                    fetchScannerData();
                } else {
                    currentStocks = scannerData;
                    renderStocks();
                }
            } else {
                scannerOptions.style.display = 'none';
                currentStocks = watchlistData;
                renderStocks();
            }
        });
    });
}

async function fetchScannerData() {
    const type = document.getElementById('ranking-type').value;
    const indicator = document.querySelector('.status-indicator');
    const list = document.getElementById('stock-list');

    try {
        indicator.classList.add('loading');
        const response = await fetch(`/api/market_scanner?type=${type}`);
        scannerData = await response.json();
        currentStocks = scannerData;
        renderStocks();
    } catch (error) {
        console.error('Error fetching scanner data:', error);
    } finally {
        indicator.classList.remove('loading');
    }
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

    const filtered = (activeStrategy === 'all' || activeStrategy === 'scanner') ?
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

        // AI Reasoning text
        const aiReasoning = stock.ai_summary ? `<div class="ai-reasoning-preview">${stock.ai_summary}</div>` : '';

        const card = document.createElement('div');
        card.id = `card-${stock.symbol}`;
        card.className = 'stock-card';
        card.innerHTML = `
            <div class="card-header">
                <div class="stock-info">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <h2>${stock.symbolname}</h2>
                        <button class="watchlist-toggle-btn ${activeStrategy !== 'scanner' ? 'active' : ''}" 
                                onclick="toggleWatchlist(event, this)" 
                                style="background: none; border: none; padding: 0; cursor: pointer; color: ${activeStrategy !== 'scanner' ? '#FBBC04' : 'var(--text-muted)'}; transition: color 0.3s;">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="${activeStrategy !== 'scanner' ? '#FBBC04' : 'none'}" stroke="currentColor" stroke-width="2">
                                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 22 12 18.27 5.82 22 7 14.14l-5-4.87 6.91-1.01L12 2z"/>
                            </svg>
                        </button>
                    </div>
                    <span class="code">${stock.symbol}</span>
                </div>
                <div class="price-box">
                    <span class="current-price ${colorClass}">${stock.currentprice.toLocaleString()}</span>
                    <span class="change-percent ${colorClass}">${sign}${stock.change_percent}%</span>
                </div>
            </div>
            
            <div class="badges">${badgesHtml}</div>

            <div class="card-body">
                <div class="detail-item">
                    <span class="detail-label">RSI(${Math.round(rsiVal)})</span>
                    <div class="meter-container">
                        <div class="meter-fill" style="width: ${rsiWidth}%; background: ${getRsiColor(rsiVal)}"></div>
                    </div>
                </div>
                <div class="detail-item ai-insight">
                    <span class="detail-label">AI SCORE / SENTIMENT</span>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="detail-value" style="color:${getScoreColor(stock.ai_score)}">${stock.ai_score || '-'}</span>
                        ${stock.ai_sentiment ? `<span class="sentiment-badge ${stock.ai_sentiment.toLowerCase()}">${stock.ai_sentiment}</span>` : ''}
                    </div>
                </div>
            </div>

            ${aiReasoning}

            <div class="actions">
                <button class="btn btn-primary btn-sm" onclick="copyPrompt('${stock.symbol}', event)">
                    <span>✨ プロンプト</span>
                </button>
                <button class="btn btn-sm" onclick="viewReport('${stock.symbol}')">
                    <span>📄 レポート</span>
                </button>
                <button class="btn btn-sm" onclick="openApp('${stock.symbol}')">
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

async function copyPrompt(symbol, event) {
    const btn = event.currentTarget;
    const originalText = btn.innerHTML;

    try {
        btn.innerHTML = `<span>⏳ 取得中...</span>`;
        
        // 1. Get Prompt for Clipboard
        const responsePrompt = await fetch(`/api/prompt/${symbol}`);
        const dataPrompt = await responsePrompt.json();

        // 2. Trigger Server-side Report Saving (Fire and Forget)
        fetch(`/api/analyze/${symbol}`, { method: 'POST' });

        // Copy process
        // NOTE: In non-secure contexts (Tailscale, etc.), navigator.clipboard may be undefined.
        // Also, document.execCommand('copy') might fail after an 'await' if the browser is strict.
        let success = false;
        const textToCopy = dataPrompt.prompt;

        if (navigator.clipboard && navigator.clipboard.writeText) {
            try {
                await navigator.clipboard.writeText(textToCopy);
                success = true;
            } catch (err) {
                console.warn('Navigator clipboard failed, trying fallback', err);
            }
        }

        if (!success) {
            const textArea = document.getElementById('clipboard-area');
            textArea.value = textToCopy;
            textArea.select();
            textArea.setSelectionRange(0, 99999); // For mobile
            success = document.execCommand('copy');
        }

        if (success) {
            btn.innerHTML = `<span>✅ COPIED & Opening Gemini...</span>`;
            setTimeout(() => {
                window.open('https://gemini.google.com/app', '_blank');
            }, 500);
        } else {
            btn.innerHTML = `<span>❌ 手動コピーしてください</span>`;
            // More modern fallback: show the text in a way that's easy to copy
            alert("ブラウザの制限により自動コピーがブロックされました。次の画面でテキストをコピーしてGeminiに貼り付けてください。");
            const manualCopy = window.prompt("以下のプロンプトをコピーしてください:", textToCopy);
            if (manualCopy !== null) {
                window.open('https://gemini.google.com/app', '_blank');
            }
        }
        
        setTimeout(() => btn.innerHTML = originalText, 2000);

    } catch (error) {
        console.error('Error copying prompt:', error);
        btn.innerHTML = `<span>⚠️ ERROR</span>`;
        setTimeout(() => btn.innerHTML = originalText, 2000);
    }
}

function openApp(symbol) {
    window.open(`https://finance.yahoo.co.jp/quote/${symbol}.T`, '_blank');
}

async function viewReport(symbol) {
    const overlay = document.getElementById('analysis-overlay');
    const title = document.getElementById('overlay-title');
    const reportDiv = document.getElementById('report-content');
    const historySelect = document.getElementById('history-select');

    // 1. Show UI Loading
    overlay.classList.add('active');
    title.innerText = `ANALYSIS: ${symbol}`;
    reportDiv.innerHTML = '<p>Loading History...</p>';
    historySelect.innerHTML = '<option>Loading...</option>';

    try {
        // 2. Fetch History & Render Chart
        const historyResponse = await fetch(`/api/history/${symbol}`);
        const historyData = await historyResponse.json();
        renderChart(historyData);

        // 3. Fetch Analysis History List
        const analysisHistoryResponse = await fetch(`/api/analysis_history/${symbol}`);
        const analysisHistory = await analysisHistoryResponse.json();
        
        if (analysisHistory.length > 0) {
            // Populate select box
            historySelect.innerHTML = analysisHistory.map((r, i) => 
                `<option value="${r.id}">${new Date(r.created_at).toLocaleString()} (${r.score})</option>`
            ).join('');
            
            // Load latest by default
            loadSpecificAnalysis(analysisHistory[0].id);
        } else {
            historySelect.innerHTML = '<option>No history</option>';
            showManualPasteUI(symbol);
        }

    } catch (error) {
        console.error('Error loading analysis view:', error);
        reportDiv.innerHTML = '<p style="color:var(--down-color)">ERROR LOADING ANALYSIS</p>';
    }
}

async function loadSpecificAnalysis(reportId) {
    const reportDiv = document.getElementById('report-content');
    reportDiv.innerHTML = '<p>Loading Detail...</p>';
    
    try {
        const response = await fetch(`/api/analysis_detail/${reportId}`);
        const data = await response.json();
        renderReport(data);
    } catch (error) {
        console.error(error);
        reportDiv.innerHTML = '<p style="color:var(--down-color)">FAILED TO LOAD REPORT</p>';
    }
}

function showManualPasteUI(symbol) {
    // If symbol is not passed, try to get it from the UI/Context
    if (!symbol) {
        // Find it from the title or current state if needed
        const titleMatch = document.getElementById('overlay-title').innerText.match(/ANALYSIS: (.*)/);
        symbol = titleMatch ? titleMatch[1] : '';
    }

    const reportDiv = document.getElementById('report-content');
    reportDiv.innerHTML = `
        <div class="manual-paste-container" style="padding:20px; border:1px dashed var(--accent-color); border-radius:8px; margin-top:10px;">
            <p style="color:var(--text-primary); font-weight:bold; margin-bottom:10px;">✨ 新しい分析結果を保存</p>
            <p style="color:var(--text-secondary); margin-bottom:15px; font-size:0.9rem;">Geminiの回答をここに貼り付けてください。過去のデータとは別に新しく保存されます。</p>
            <textarea id="manual-report-input" placeholder="Geminiの回答をここに貼り付けてください..." style="width:100%; height:150px; background:#0d1117; color:white; border:1px solid #30363d; padding:10px; border-radius:4px; font-family:inherit; margin-bottom:10px;"></textarea>
            <div style="display:flex; gap:10px; align-items:center;">
                <input type="number" id="manual-score-input" placeholder="スコア(0-10)" min="0" max="10" step="0.1" style="width:100px; padding:8px; background:#0d1117; color:white; border:1px solid #30363d; border-radius:4px;">
                <button class="btn btn-primary" onclick="saveManualReport('${symbol}')">結果を保存する</button>
                <button class="btn" onclick="viewReport('${symbol}')">キャンセル</button>
            </div>
        </div>
    `;
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
    let content = data.content;

    // Handle stringified JSON from the database
    if (typeof content === 'string') {
        try {
            content = JSON.parse(content);
        } catch (e) {
            // It's already plain text
        }
    }

    // Determine the text to display
    const textToRender = content.text || content.reasoning || (typeof content === 'string' ? content : JSON.stringify(content));
    const score = data.score || content.score || 0;
    const summary = content.summary || '';

    let html = `
        <div class="ai-summary">
            <span class="badge" style="background:var(--accent-color); color:white">SCORE: ${score}</span>
            <p style="font-weight:700; margin-top:10px">${summary}</p>
        </div>
        <div class="ai-reasoning">${parseMarkdown(textToRender)}</div>
    `;

    if (content.risks && Array.isArray(content.risks)) {
        html += `<h3>RISKS</h3><ul>${content.risks.map(r => `<li>${r}</li>`).join('')}</ul>`;
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

async function saveManualReport(symbol) {
    const content = document.getElementById('manual-report-input').value;
    const score = document.getElementById('manual-score-input').value || 0;

    if (!content) {
        alert("内容を入力してください。");
        return;
    }

    try {
        const response = await fetch(`/api/save_manual_report/${symbol}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content, score })
        });

        if (response.ok) {
            alert("保存しました！分析を表示します。");
            // After saving, we need a slight delay or just call viewReport
            viewReport(symbol);
        } else {
            alert("保存に失敗しました。");
        }
    } catch (error) {
        console.error(error);
        alert("エラーが発生しました。");
    }
}

async function copyBulkPrompt(event) {
    const btn = event.currentTarget;
    const originalText = btn.innerHTML;

    try {
        btn.innerHTML = `<span>⏳ 準備中...</span>`;
        
        let url = '/api/bulk_prompt?source=watchlist';
        if (activeStrategy === 'scanner') {
            const type = document.getElementById('ranking-type').value;
            url = `/api/bulk_prompt?source=scanner&type=${type}`;
        }
        
        const response = await fetch(url);
        if (!response.ok) throw new Error("Failed to fetch bulk prompt");
        
        const data = await response.json();
        const textToCopy = data.prompt;

        let success = false;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            try {
                await navigator.clipboard.writeText(textToCopy);
                success = true;
            } catch (err) {
                console.warn('Fallback needed');
            }
        }

        if (!success) {
            const textArea = document.getElementById('clipboard-area');
            textArea.value = textToCopy;
            textArea.select();
            success = document.execCommand('copy');
        }

        if (success) {
            btn.innerHTML = `<span>✅ ${data.count}銘柄 COPY完了!</span>`;
            setTimeout(() => {
                window.open('https://gemini.google.com/app', '_blank');
            }, 800);
        } else {
            btn.innerHTML = `<span>❌ 手動コピー</span>`;
            window.prompt("コピーしてください:", textToCopy);
        }
        
        setTimeout(() => btn.innerHTML = originalText, 2500);

    } catch (error) {
        console.error(error);
        btn.innerHTML = `<span>⚠️ ERROR</span>`;
        setTimeout(() => btn.innerHTML = originalText, 2000);
    }
}
