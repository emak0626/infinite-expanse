document.addEventListener('DOMContentLoaded', () => {
    try {
        fetchStocks();
        setupTabs();
        fetchWorkspaceLinks();
        updateHealthStatus();
        setInterval(updateHealthStatus, 30000); 
    } catch (e) {
        console.error("Initialization error:", e);
    }
});

async function copyAnalysisPrompt(symbol, name) {
    try {
        const response = await fetch(`/api/analysis/prompt/${symbol}`);
        const data = await response.json();
        
        let promptText = data.prompt;
        // Inject company name if it's not present or to ensure clarity
        if (name && !promptText.includes(name)) {
            promptText = `銘柄名: ${name}\n` + promptText;
        }

        await navigator.clipboard.writeText(promptText);
    } catch (error) {
        console.error('Failed to copy analysis prompt:', error);
        alert('分析プロンプトのコピーに失敗しました。');
    }
}

async function fetchWorkspaceLinks() {
    try {
        const response = await fetch('/api/workspace/files');
        const files = await response.json();
        
        const container = document.getElementById('workspace-links');
        const console = document.getElementById('workspace-console');
        
        // Always show the console if the element exists
        if (console) console.style.display = 'block';

        if (container) {
            container.style.display = 'flex';
            container.style.flexDirection = 'column';
            container.style.gap = '8px';
            
            if (files && files.length > 0) {
                container.innerHTML = `
                    <div style="font-size: 0.7rem; opacity: 0.7; margin-bottom: 8px;">Recent Intelligence:</div>
                    ${files.slice(0, 5).map(f => `
                        <a href="${f.path}" target="_blank" class="glass-card" style="display: flex; align-items: center; gap: 12px; text-decoration: none; color: #fff; padding: 10px; border: 1px solid rgba(255,255,255,0.1); transition: all 0.2s; background: rgba(255,255,255,0.03);">
                            <span style="font-size: 1.2rem;">${f.category === 'AI_Reports' ? '📃' : '📊'}</span>
                            <div style="overflow: hidden; flex: 1;">
                                <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; font-size: 0.75rem;">${f.name}</div>
                                <div style="font-size: 0.6rem; opacity: 0.5;">${new Date(f.mtime).toLocaleString()}</div>
                            </div>
                        </a>
                    `).join('')}
                    ${files.length > 5 ? `<div style="font-size: 0.6rem; text-align: center; opacity: 0.4; margin-top: 4px;">...and ${files.length - 5} more files</div>` : ''}
                `;
            } else {
                container.innerHTML = `
                    <div style="text-align: center; padding: 20px; opacity: 0.5; font-size: 0.75rem; border: 1px dashed rgba(255,255,255,0.1); border-radius: 8px;">
                        No data collected yet.<br>Generating your first intelligence...
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error fetching workspace files:', error);
    }
}

async function updateHealthStatus() {
    const dbIndicator = document.getElementById('db-status');
    const apiIndicator = document.getElementById('api-status');
    
    // For now, simplify check based on fetchData success or a dedicated health endpoint
    // In a real robust app, add /api/health endpoint balance
    try {
        const response = await fetch('/api/stocks');
        if (response.ok) {
            dbIndicator.style.background = 'var(--success)';
            apiIndicator.style.background = 'var(--success)';
        } else {
            dbIndicator.style.background = 'var(--danger)';
        }
    } catch {
        dbIndicator.style.background = 'var(--danger)';
        apiIndicator.style.background = 'var(--danger)';
    }
}

async function searchAndAddStock() {
    const input = document.getElementById('symbol-search');
    const symbol = input.value.trim();
    if (!symbol || symbol.length !== 4) {
        alert("4桁の銘柄コードを入力してください。");
        return;
    }

    try {
        const response = await fetch(`/api/watchlist/${symbol}`, { method: 'POST' });
        if (response.ok) {
            input.value = '';
            alert(`${symbol} をウォッチリストに追加しました。`);
            fetchData(); // Refresh list
        } else {
            const err = await response.json();
            alert(`追加に失敗しました: ${err.detail || '不明なエラー'}`);
        }
    } catch (error) {
        console.error('Search add failed:', error);
        alert("通信エラーが発生しました。");
    }
}

async function exportForNotebookLM() {
    const btn = event.currentTarget;
    const originalText = btn.innerHTML;
    
    try {
        btn.innerHTML = '⌛ 生成中...';
        // Use the dedicated NotebookLM export endpoint
        const response = await fetch('/api/export/notebooklm');
        const data = await response.json();
        
        const blob = new Blob([data.prompt], { type: 'text/markdown' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `market_analysis_for_notebooklm_${new Date().toISOString().slice(0,10)}.md`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        
        btn.innerHTML = '✅ 完了';
        setTimeout(() => btn.innerHTML = originalText, 2000);
    } catch (error) {
        console.error('Export failed:', error);
        btn.innerHTML = '❌ ERROR';
        setTimeout(() => btn.innerHTML = originalText, 2000);
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

async function fetchStocks() {
    const list = document.getElementById('stock-list');
    const indicator = document.querySelector('.status-indicator');

    try {
        if (indicator) indicator.classList.add('loading');
        // Fetch screened data (which includes strategies metadata)
        console.log("Fetching latest stocks...");
        const response = await fetch('/api/screening');
        const data = await response.json();
        watchlistData = data;
        currentStocks = watchlistData;

        console.log(`Stocks loaded: ${currentStocks.length}`);
        renderHeatmap(currentStocks);
        renderStocks();

    } catch (error) {
        if (list) list.innerHTML = `<p style="text-align:center; color:var(--down-color);">CONNECTION ERROR</p>`;
        console.error('Error fetching stocks:', error);
    } finally {
        if (indicator) indicator.classList.remove('loading');
        // Visual feedback for the refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.classList.add('refresh-success');
            setTimeout(() => refreshBtn.classList.remove('refresh-success'), 1000);
        }
    }
}

// Ensure it's available for onclick in HTML
window.fetchStocks = fetchStocks;
window.fetchData = fetchStocks; // Backward compatibility

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
            console.log(`Tab clicked: ${activeStrategy}`);
            
            // Toggle Scanner Options
            const scannerOptions = document.getElementById('scanner-options');
            if (activeStrategy === 'scanner') {
                if (scannerOptions) scannerOptions.style.display = 'block';
                if (scannerData.length === 0) {
                    fetchScannerData();
                } else {
                    currentStocks = scannerData;
                    renderStocks();
                }
            } else {
                if (scannerOptions) scannerOptions.style.display = 'none';
                currentStocks = watchlistData;
                console.log(`Rendering watchlist stocks (Total: ${currentStocks.length}) for strategy: ${activeStrategy}`);
                renderStocks();
            }
        });
    });
}

async function fetchScannerData() {
    const rankSelect = document.getElementById('ranking-type');
    const type = rankSelect ? rankSelect.value : '1';
    const indicator = document.querySelector('.status-indicator');
    const list = document.getElementById('stock-list');

    try {
        if (indicator) indicator.classList.add('loading');
        if (list) list.innerHTML = '<div class="loading-state"><div class="pulse-ring"></div><p>SCANNING MARKET...</p></div>';
        
        const response = await fetch(`/api/market_scanner?type=${type}`);
        scannerData = await response.json();
        currentStocks = scannerData;
        renderStocks();
    } catch (error) {
        console.error('Error fetching scanner data:', error);
        if (list) list.innerHTML = `<p style="text-align:center; color:var(--down-color);">SCANNER ERROR</p>`;
    } finally {
        if (indicator) indicator.classList.remove('loading');
    }
}

function renderHeatmap(stocks) {
    const container = document.getElementById('heatmap-scroll');
    if (!container) {
        console.warn("Heatmap container not found (#heatmap-scroll)");
        return;
    }
    container.innerHTML = '';

    const sorted = [...stocks].sort((a, b) => Math.abs(b.change_percent) - Math.abs(a.change_percent));

    sorted.forEach(stock => {
        const div = document.createElement('div');
        const isUp = stock.change_percent >= 0;
        div.className = `heat-cell ${isUp ? 'up' : 'down'}`;

        const aiBadge = stock.ai_score ? `<span class="ai-mini-badge" style="background:${getScoreColor(stock.ai_score)}">${stock.ai_score}</span>` : '';

        div.innerHTML = `
            ${aiBadge}
            <span class="symbol-code">${stock.symbol}</span>
            <span class="change-val">${isUp ? '+' : ''}${stock.change_percent}%</span>
        `;
        div.onclick = () => {
            const card = document.getElementById(`card-${stock.symbol}`);
            if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });
        };
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
        list.innerHTML = `<p style="text-align:center; padding:40px; color:var(--text-secondary); opacity:0.6;">NO ASSETS FOUND</p>`;
        return;
    }

    filtered.forEach(stock => {
        const isUp = stock.change_percent >= 0;
        const colorClass = isUp ? 'up' : 'down';
        const sign = isUp ? '+' : '';

        let badgesHtml = '';
        if (stock.matched_strategies) {
            stock.matched_strategies.forEach(st => {
                const badgeNames = {
                    'value_invest': '💎 バリュー',
                    'high_dividend': '💰 配当重視',
                    'short_squeeze': '🔥 モメンタム',
                    'rebound': '⚡ 反発期待'
                };
                if (badgeNames[st]) {
                    badgesHtml += `<span class="badge ${st}">${badgeNames[st]}</span>`;
                }
            });
        }

        const aiReasoning = stock.ai_summary ? `<div class="ai-reasoning-preview">${stock.ai_summary}</div>` : '';

        const card = document.createElement('div');
        card.id = `card-${stock.symbol}`;
        card.className = 'stock-card glass-card animate-in';
        card.dataset.symbol = stock.symbol;
        card.innerHTML = `
            <div class="card-top">
                <div class="stock-info">
                    <h3>${stock.symbolname}</h3>
                    <span class="detail-label">${stock.symbol}</span>
                </div>
                <div class="price-main">
                    <span class="price-now">${stock.currentprice.toLocaleString()}</span>
                    <span class="price-change ${colorClass}">${sign}${stock.change_percent}%</span>
                </div>
            </div>
            
            <div class="strategy-badges" style="display:flex; gap:6px; margin-bottom:12px;">${badgesHtml}</div>

            <div class="details-grid">
                <div class="detail-item">
                    <span class="detail-label">RSI</span>
                    <span class="detail-value" style="color:${getRsiColor(stock.rsi)}">${Math.round(stock.rsi || 0)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">AI SCORE</span>
                    <span class="detail-value" style="color:${getScoreColor(stock.ai_score)}">${stock.ai_score || '-'}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">PER</span>
                    <span class="detail-value">${stock.per || '-'}</span>
                </div>
            </div>

            <div id="notes-${stock.symbol}" class="llm-notes-container"></div>

            ${aiReasoning}

            <div class="card-actions" style="display:flex; gap:8px; margin-top:16px;">
                <button class="btn btn-primary" style="flex:1; height:40px; font-size:0.8rem;" onclick="copyPrompt('${stock.symbol}', event)">PROMPTコピー</button>
                <button class="btn btn-outline" style="flex:1; height:40px; font-size:0.8rem;" onclick="viewReport('${stock.symbol}')">詳細分析</button>
            </div>
        `;
        list.appendChild(card);
        fetchNotes(stock.symbol);
    });
}

async function fetchNotes(symbol) {
    const container = document.getElementById(`notes-${symbol}`);
    if (!container) return;

    try {
        const response = await fetch(`/api/notes/${symbol}`);
        const notes = await response.json();
        
        if (notes && notes.length > 0) {
            container.innerHTML = `
                <div class="section-title" style="margin-top: 12px; font-size: 0.65rem;">所見 (Local LLM)</div>
                ${notes.map(n => `
                    <div class="llm-note-item priority-${n.priority}">
                        <span class="note-time">${new Date(n.created_at).toLocaleDateString()}</span>
                        <p class="note-text">${n.note}</p>
                    </div>
                `).join('')}
            `;
        }
    } catch (e) {
        console.error(`Failed to fetch notes for ${symbol}:`, e);
    }
}

function getRsiColor(val) {
    if (val <= 30) return '#00ffff'; 
    if (val >= 70) return '#ff00ff'; 
    return 'var(--accent)';
}

function getScoreColor(score) {
    if (!score) return 'var(--text-secondary)';
    if (score >= 7) return 'var(--success)';
    if (score <= 4) return 'var(--danger)';
    return 'var(--accent)';
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
                <button class="btn btn-outline btn-sm" onclick="copyAnalysisPrompt('${symbol}', document.getElementById('overlay-title').innerText.replace('ANALYSIS: ', ''))">PROMPTコピー</button>
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
        
        ${data.persona_views ? `
            <div class="persona-section" style="margin-top:20px; display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:15px;">
                <div class="persona-box" style="background:#1c2128; padding:12px; border-radius:6px; border-left:4px solid #3fb950;">
                    <div style="font-size:0.8rem; color:#8b949e; margin-bottom:5px;">💎 VALUE INVESTOR</div>
                    <div style="font-size:0.9rem;">${data.persona_views.value || '-'}</div>
                </div>
                <div class="persona-box" style="background:#1c2128; padding:12px; border-radius:6px; border-left:4px solid #f85149;">
                    <div style="font-size:0.8rem; color:#8b949e; margin-bottom:5px;">👺 DEVIL'S ADVOCATE</div>
                    <div style="font-size:0.9rem;">${data.persona_views.risk || '-'}</div>
                </div>
                <div class="persona-box" style="background:#1c2128; padding:12px; border-radius:6px; border-left:4px solid #388bfd;">
                    <div style="font-size:0.8rem; color:#8b949e; margin-bottom:5px;">⚡ STRATEGIST</div>
                    <div style="font-size:0.9rem;">${data.persona_views.technical || '-'}</div>
                </div>
            </div>
        ` : ''}

        <div class="ai-reasoning" style="margin-top:20px;">${parseMarkdown(textToRender)}</div>
    `;

    if (data.catalysts && Array.isArray(data.catalysts)) {
        html += `
            <div style="margin-top:20px; padding:15px; background:rgba(56, 139, 253, 0.1); border-radius:8px; border:1px solid rgba(56, 139, 253, 0.3);">
                <h3 style="margin-top:0; font-size:1rem; color:#58a6ff;">🚀 材料・カタリスト</h3>
                <ul style="margin-bottom:0;">${data.catalysts.map(c => `<li>${c}</li>`).join('')}</ul>
            </div>
        `;
    }

    if (content.risks && Array.isArray(content.risks)) {
        html += `<h3 style="margin-top:20px;">注意点・リスク</h3><ul>${content.risks.map(r => `<li>${r}</li>`).join('')}</ul>`;
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
async function triggerMarketScan() {
    const btn = document.getElementById('scan-market-btn');
    const originalText = btn.innerHTML;
    
    try {
        btn.innerHTML = '📡 SCANNING...';
        btn.disabled = true;
        const response = await fetch('/api/admin/scan-market', { method: 'POST' });
        const data = await response.json();
        // Use console log instead of alert for non-disruptive feedback
        console.log(data.message);
    } catch (error) {
        console.error('Market scan failed:', error);
    } finally {
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }, 3000);
    }
}

async function triggerEdinetScan() {
    const btn = document.getElementById('scan-edinet-btn');
    if (!btn) return;
    const originalText = btn.innerHTML;
    btn.innerHTML = '🔍 ANALYZING...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/admin/scan-edinet', { method: 'POST' });
        const data = await response.json();
        console.log('情報収集（EDINETスキャン）をバックグラウンドで開始しました。');
    } catch (e) {
        console.error('Failed to trigger EDINET scan:', e);
    } finally {
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }, 3000);
    }
}
