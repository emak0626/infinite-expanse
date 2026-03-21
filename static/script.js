document.addEventListener('DOMContentLoaded', () => {
    try {
        fetchStocks();
        setupTabs();
        fetchWorkspaceLinks();
        updateHealthStatus();
        setInterval(updateHealthStatus, 30000); 
        updateScanStatus();
        setInterval(updateScanStatus, 10000); // Poll scan status every 10s
        
        // 🛠️ Robust event listeners (Override inline onclick for reliability)
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', (e) => {
                e.preventDefault();
                console.log("[UI] Refresh button clicked (fetchStocks)");
                fetchStocks(true);
            });
        }
    } catch (e) {
        console.error("Initialization error:", e);
    }
});

async function copyAnalysisPrompt(symbol, name) {
    try {
        const response = await fetch(`/api/analysis/prompt/${symbol}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
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
        const workspaceConsole = document.getElementById('workspace-console');
        
        // Always show the console if the element exists
        if (workspaceConsole) workspaceConsole.style.display = 'block';

        if (container) {
            // Container style is managed by the parent #workspace-content in the new layout
            if (files && files.length > 0) {
                container.innerHTML = `
                    <div style="font-size: 0.7rem; opacity: 0.7; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <span>最近の重要レポート:</span>
                        <button onclick="fetchWorkspaceLinks()" class="btn btn-outline btn-xs" style="font-size: 0.6rem; padding: 2px 5px;">🔄 更新</button>
                    </div>
                    ${files.slice(0, 10).map(f => {
                        return `
                        <div class="glass-card" style="display: flex; align-items: center; gap: 8px; padding: 10px; border: 1px solid rgba(255,255,255,0.1); transition: all 0.2s; background: rgba(255,255,255,0.03); margin-bottom: 8px;">
                            <span style="font-size: 1.2rem;">${f.category === 'AI_Reports' ? '📃' : (f.category === 'Trash' ? '🗑️' : '📊')}</span>
                            <a href="${f.path}" target="_blank" style="text-decoration: none; color: #fff; overflow: hidden; flex: 1;">
                                <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; font-size: 0.75rem;">${f.name}</div>
                                <div style="font-size: 0.6rem; opacity: 0.5;">${new Date(f.mtime).toLocaleString()}</div>
                            </a>
                        </div>
                    `}).join('')}
                    ${files.length > 10 ? `<div style="font-size: 0.6rem; text-align: center; opacity: 0.4; margin-top: 4px;">...他 ${files.length - 10} 件のファイル</div>` : ''}
                `;
            } else {
                container.innerHTML = `
                    <div style="text-align: center; padding: 20px; opacity: 0.5; font-size: 0.75rem; border: 1px dashed rgba(255,255,255,0.1); border-radius: 8px;">
                        レポートはまだありません。<br>分析を実行してインテリジェンスを生成してください。
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error fetching workspace files:', error);
    }
}

function toggleWorkspaceConsole() {
    const content = document.getElementById('workspace-content');
    const icon = document.getElementById('workspace-toggle-icon');
    if (!content || !icon) return;

    const isHidden = content.style.display === 'none' || content.style.display === '';
    
    if (isHidden) {
        content.style.display = 'block';
        icon.style.transform = 'rotate(90deg)';
        fetchWorkspaceLinks(); // Refresh links when opening
    } else {
        content.style.display = 'none';
        icon.style.transform = 'rotate(0deg)';
    }
}

// Make toggle accessible to HTML onclick
window.toggleWorkspaceConsole = toggleWorkspaceConsole;

async function updateHealthStatus() {
    const dbIndicator = document.getElementById('db-status');
    const apiIndicator = document.getElementById('api-status');
    const localAiIndicator = document.getElementById('local-ai-status');
    
    // Check main API and DB
    try {
        const response = await fetch('/api/stocks');
        if (response.ok) {
            if (dbIndicator) dbIndicator.style.background = 'var(--success)';
            if (apiIndicator) apiIndicator.style.background = 'var(--success)';
        } else {
            if (dbIndicator) dbIndicator.style.background = 'var(--danger)';
            if (apiIndicator) apiIndicator.style.background = 'var(--danger)';
        }
    } catch {
        if (dbIndicator) dbIndicator.style.background = 'var(--danger)';
        if (apiIndicator) apiIndicator.style.background = 'var(--danger)';
    }

    // Check Local AI (Ollama)
    try {
        const response = await fetch('/api/health/local_ai');
        const data = await response.json();
        if (data.status === 'online') {
            if (localAiIndicator) {
                localAiIndicator.style.background = 'var(--success)';
                localAiIndicator.title = `ローカルAI: 接続中 (${data.url})`;
            }
        } else {
            if (localAiIndicator) {
                localAiIndicator.style.background = 'var(--danger)';
                localAiIndicator.title = `ローカルAI: 停止中 (${data.message})`;
            }
        }
    } catch {
        if (localAiIndicator) {
            localAiIndicator.style.background = 'var(--danger)';
            localAiIndicator.title = 'ローカルAI: 接続エラー';
        }
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

async function exportForNotebookLM(event) {
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

async function fetchStocks(refresh = false) {
    const list = document.getElementById('stock-list');
    const indicator = document.querySelector('.status-indicator');

    try {
        if (indicator) indicator.classList.add('loading');
        // Fetch screened data (which includes strategies metadata)
        console.log(`Fetching latest stocks... (Refresh: ${refresh})`);
        const url = refresh ? '/api/screening?refresh=true' : '/api/screening';
        const response = await fetch(url);
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
window.fetchData = fetchStocks; 
window.fetchWorkspaceLinks = fetchWorkspaceLinks;
window.updateHealthStatus = updateHealthStatus;
window.updateScanStatus = updateScanStatus;

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
        if (list) list.innerHTML = '<div class="loading-state"><div class="pulse-ring"></div><p>市場をスキャン中...</p></div>';
        
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

    let sorted = [...stocks];
    if (activeStrategy === 'scanner') {
        // Sort by AI score descending
        sorted.sort((a, b) => (b.ai_score || 0) - (a.ai_score || 0));
    } else {
        // Default sort by absolute change percent
        sorted.sort((a, b) => Math.abs(b.change_percent) - Math.abs(a.change_percent));
    }

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

    // If on scanner tab, show a helper message
    if (activeStrategy === 'scanner') {
        const title = document.querySelector('.section-title');
        if (title) title.innerHTML = '✨ AI選別: おすすめ銘柄（高スコア順）';
    }
}

function renderStocks() {
    const list = document.getElementById('stock-list');
    list.innerHTML = '';

    const filtered = (activeStrategy === 'all' || activeStrategy === 'scanner') ?
        currentStocks :
        currentStocks.filter(s => s.matched_strategies && s.matched_strategies.includes(activeStrategy));

    if (filtered.length === 0) {
        list.innerHTML = `<p style="text-align:center; padding:40px; color:var(--text-secondary); opacity:0.6;">対象銘柄が見つかりません</p>`;
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
                    <div style="display:flex; align-items:center; gap:8px;">
                        <h3 style="margin:0">${stock.symbolname}</h3>
                        <button class="watchlist-toggle ${stock.is_watched ? 'active' : ''}" 
                                onclick="toggleWatchlist(event, this)" 
                                title="ウォッチリストから削除"
                                style="background:none; border:none; cursor:pointer; padding:4px; display:flex; align-items:center;">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="${stock.is_watched ? '#FBBC04' : 'none'}" stroke="${stock.is_watched ? '#FBBC04' : 'currentColor'}" stroke-width="2">
                                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                            </svg>
                        </button>
                    </div>
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
                    <span class="detail-label">RSI(14) <small>過熱感</small></span>
                    <span class="detail-value" style="color:${getRsiColor(stock.rsi)}">${Math.round(stock.rsi || 0)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">AIスコア <small>期待値</small></span>
                    <span class="detail-value" style="color:${getScoreColor(stock.ai_score)}">${stock.ai_score || '-'}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">PER <small>割安性</small></span>
                    <span class="detail-value">${stock.per || '-'}</span>
                </div>
            </div>

            <div id="notes-${stock.symbol}" class="llm-notes-container"></div>

            ${aiReasoning}

            <div class="card-actions" style="display:flex; flex-wrap:wrap; gap:8px; margin-top:16px;">
                <button class="btn btn-primary" style="flex:1; min-width:120px; height:40px; font-size:0.75rem;" onclick="copyPrompt('${stock.symbol}', event)">PROMPTコピー</button>
                <button class="btn btn-outline" style="flex:1; min-width:120px; height:40px; font-size:0.75rem;" onclick="viewReport('${stock.symbol}')">AI詳細分析</button>
                <button class="btn btn-outline" style="flex:1; min-width:120px; height:40px; font-size:0.75rem; border-color:rgba(0,255,255,0.3);" onclick="viewTradeAnalysis('${stock.symbol}')">🎯 売買戦略</button>
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

async function copyPrompt(symbol, event = null) {
    const btn = event ? event.currentTarget : null;
    const originalText = btn ? btn.innerHTML : '';

    try {
        console.log(`[copyPrompt] Starting for ${symbol}`);
        btn.innerHTML = `<span>⏳ 取得中...</span>`;
        
        // 1. Get Prompt for Clipboard
        const responsePrompt = await fetch(`/api/analysis/prompt/${symbol}`);
        console.log(`[copyPrompt] Prompt fetch status: ${responsePrompt.status}`);
        if (!responsePrompt.ok) {
            const errBody = await responsePrompt.text();
            throw new Error(`HTTP error! status: ${responsePrompt.status}, body: ${errBody}`);
        }
        const dataPrompt = await responsePrompt.json();
        console.log(`[copyPrompt] Received prompt (length: ${dataPrompt.prompt ? dataPrompt.prompt.length : 0})`);

        // Removed: Automatic background analysis trigger to save API limits
        // fetch(`/api/analyze/${symbol}`, { method: 'POST' }).catch(err => ...);

        // Copy process
        let success = false;
        const textToCopy = dataPrompt.prompt;
        
        if (!textToCopy) {
            throw new Error("No prompt text received from server");
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
            try {
                console.log(`[copyPrompt] Using navigator.clipboard.writeText`);
                await navigator.clipboard.writeText(textToCopy);
                success = true;
            } catch (err) {
                console.warn('[copyPrompt] Navigator clipboard failed, trying fallback', err);
            }
        } else {
            console.log(`[copyPrompt] navigator.clipboard not available (possibly insecure context)`);
        }

        if (!success) {
            console.log(`[copyPrompt] Trying fallback with textarea...`);
            const textArea = document.getElementById('clipboard-area');
            if (textArea) {
                textArea.value = textToCopy;
                textArea.select();
                textArea.setSelectionRange(0, 99999); // For mobile
                success = document.execCommand('copy');
                console.log(`[copyPrompt] Fallback execCommand success: ${success}`);
            } else {
                console.error(`[copyPrompt] clipboard-area not found in DOM`);
            }
        }

        if (success) {
            console.log(`[copyPrompt] コピー成功、Geminiを開きます`);
            btn.innerHTML = `<span style="color:#5fcf80;">✅ コピー成功 (Geminiへ)</span>`;
            
            // Show a temporary success style on the button
            btn.style.boxShadow = '0 0 15px var(--success)';
            setTimeout(() => {
                btn.style.boxShadow = '';
                window.open('https://gemini.google.com/app', '_blank');
            }, 800);
        } else {
            console.error('[copyPrompt] すべてのコピー手法が失敗しました');
            btn.innerHTML = `<span style="color:#ff6b6b;">❌ 自動コピー失敗 - クリックで詳細</span>`;
            
            // Explicitly show textarea for manual copy if everything fails
            const manualText = textToCopy;
            const userChoice = confirm("ブラウザのセキュリティ設定により、クリップボードへの自動アクセスがブロックされました。\n\n「OK」を押すとプロンプトを手動でコピーできる画面を開きます。コピー後、Geminiに貼り付けてください。");
            
            if (userChoice) {
                showManualCopyModal(manualText);
            }
        }
        
        setTimeout(() => btn.innerHTML = originalText, 2500);

    } catch (error) {
        console.error('[copyPrompt] Fatal error:', error);
        btn.innerHTML = `<span>⚠️ 取得エラー</span>`;
        setTimeout(() => btn.innerHTML = originalText, 2500);
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
    title.innerText = `詳細分析: ${symbol}`;
    reportDiv.innerHTML = '<p>履歴を読み込み中...</p>';
    historySelect.innerHTML = '<option>読み込み中...</option>';

    try {
        // 2. Track active symbol for overlay actions
        window.currentAnalysisSymbol = symbol;

        // 3. Fetch History & Render Chart
        const historyResponse = await fetch(`/api/history/${symbol}`);
        const historyData = await historyResponse.json();
        renderChart(historyData);

        // 4. Fetch Analysis History List
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
    reportDiv.innerHTML = '<p>詳細を読み込み中...</p>';
    
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
        // Find it from the title. Format: "詳細分析: 7203"
        const titleText = document.getElementById('overlay-title').innerText;
        const titleMatch = titleText.match(/詳細分析:\s*(\w+)/);
        symbol = titleMatch ? titleMatch[1] : (window.currentAnalysisSymbol || '');
    }

    const reportDiv = document.getElementById('report-content');
    reportDiv.innerHTML = `
        <div class="manual-paste-container" style="padding:20px; border:1px dashed var(--accent-color); border-radius:8px; margin-top:10px;">
            <p style="color:var(--text-primary); font-weight:bold; margin-bottom:10px;">✨ 新しい分析結果を保存</p>
            <p style="color:var(--text-secondary); margin-bottom:15px; font-size:0.9rem;">Geminiの回答をここに貼り付けてください。過去のデータとは別に新しく保存されます。</p>
            <textarea id="manual-report-input" placeholder="Geminiの回答をここに貼り付けてください..." style="width:100%; height:150px; background:#0d1117; color:white; border:1px solid #30363d; padding:10px; border-radius:4px; font-family:inherit; margin-bottom:10px;"></textarea>
            <div style="display:flex; gap:10px; align-items:center;">
                <input type="number" id="manual-score-input" placeholder="スコア(0-10)" min="0" max="10" step="0.1" style="width:100px; padding:8px; background:#0d1117; color:white; border:1px solid #30363d; border-radius:4px;">
                <button class="btn btn-primary" onclick="saveManualReport('${symbol}')" id="save-report-btn">結果を保存する</button>
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
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span class="badge" style="background:var(--accent-color); color:white">SCORE: ${score}</span>
                <button id="copy-report-btn" class="btn btn-outline btn-xs" onclick="copyFullReport()" style="font-size:0.7rem;">📄 レポートをコピー</button>
            </div>
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

        <div class="ai-reasoning" style="margin-top:20px;">${marked.parse(textToRender)}</div>
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

async function copyFullReport() {
    const reportContent = document.getElementById('report-content');
    if (!reportContent) return;
    
    // Extract text but preserve some structure
    const textToCopy = reportContent.innerText || reportContent.textContent;
    const btn = document.getElementById('copy-report-btn');
    
    try {
        await navigator.clipboard.writeText(textToCopy);
        if (btn) {
            const originalText = btn.innerHTML;
            btn.innerHTML = '✅ COPY完了';
            setTimeout(() => btn.innerHTML = originalText, 2000);
        }
    } catch (err) {
        console.warn('Clipboard fallback needed');
        const textArea = document.getElementById('clipboard-area');
        if (textArea) {
            textArea.value = textToCopy;
            textArea.select();
            document.execCommand('copy');
            if (btn) {
                const originalText = btn.innerHTML;
                btn.innerHTML = '✅ COPY完了';
                setTimeout(() => btn.innerHTML = originalText, 2000);
            }
        } else {
            prompt("以下の内容をコピーしてください:", textToCopy);
        }
    }
}

// Simple markdown subset parser (just for the demo)
function parseMarkdown(text) {
    if (typeof marked !== 'undefined') {
        return marked.parse(text);
    }
    // Fallback if marked is missing
    return text.replace(/\n/g, '<br>');
}

async function saveManualReport(symbol) {
    const content = document.getElementById('manual-report-input').value;
    const score = document.getElementById('manual-score-input').value || 0;

    const saveBtn = document.getElementById('save-report-btn');
    if (saveBtn) {
        saveBtn.innerHTML = '⏳ 保存中...';
        saveBtn.disabled = true;
    }

    try {
        const response = await fetch(`/api/save_manual_report/${symbol}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content, score })
        });

        if (response.ok) {
            alert("保存しました！分析を表示します。");
            viewReport(symbol);
        } else {
            const errorText = await response.text();
            alert(`保存に失敗しました: ${errorText}`);
        }
    } catch (error) {
        console.error(error);
        alert(`エラーが発生しました: ${error.message}`);
    } finally {
        const saveBtn = document.getElementById('save-report-btn');
        if (saveBtn) {
            saveBtn.innerHTML = '結果を保存する';
            saveBtn.disabled = false;
        }
    }
}

async function exportNotebookLM(event) {
    const btn = event ? event.currentTarget : document.getElementById('notebooklm-btn');
    const originalText = btn.innerHTML;

    // Selection choice
    const useCurrentFilter = confirm("現在表示中のフィルタ結果のみを出力しますか？\n(「いいえ」を選択するとウォッチリスト全銘柄が出力されます)");
    let body = null;
    if (useCurrentFilter) {
        const cards = document.querySelectorAll('.stock-card');
        const symbols = Array.from(cards).map(c => c.dataset.symbol);
        body = JSON.stringify({ symbols });
    }

    try {
        btn.innerHTML = `<span>⏳ 準備中...</span>`;
        
        const response = await fetch('/api/export/notebooklm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: body
        });
        if (!response.ok) throw new Error("Failed to fetch export content");
        
        const data = await response.json();
        const textToCopy = data.prompt;

        showManualCopyModal(textToCopy);
        btn.innerHTML = `<span>✅ 完了</span>`;
    } catch (error) {
        console.error(error);
        btn.innerHTML = `<span>⚠️ ERROR</span>`;
    } finally {
        setTimeout(() => btn.innerHTML = originalText, 2500);
    }
}

async function syncNotebookLMToDrive() {
    const btn = document.getElementById('sync-drive-btn');
    const originalText = btn ? btn.innerHTML : '☁️ Drive同期';

    // Selection choice
    const useCurrentFilter = confirm("現在表示中のフィルタ結果のみを同期しますか？\n(「いいえ」を選択するとウォッチリスト全銘柄が同期されます)");
    let body = null;
    if (useCurrentFilter) {
        const cards = document.querySelectorAll('.stock-card');
        const symbols = Array.from(cards).map(c => c.dataset.symbol);
        body = JSON.stringify({ symbols });
    }

    if (btn) {
        btn.innerHTML = '⏳ 同期中...';
        btn.disabled = true;
    }

    try {
        const response = await fetch('/api/export/notebooklm/sync_drive', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: body
        });
        const data = await response.json();
        if (data.status === 'success') {
            alert(`Google Drive への同期が完了しました！\nファイル: ${data.filename}\n共有先: ${data.shared_with}`);
            if (data.webViewLink) {
                window.open(data.webViewLink, '_blank');
            }
        } else {
            alert(`同期に失敗しました: ${data.detail || 'Unknown error'}`);
        }
    } catch (e) {
        console.error(e);
        alert(`エラーが発生しました: ${e.message}`);
    } finally {
        if (btn) {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }
}
async function updateScanStatus() {
    const btn = document.getElementById('scan-market-btn');
    const aiBtn = document.getElementById('scan-ai-btn');
    const timeLabel = document.getElementById('last-scan-time');
    const aiTimeLabel = document.getElementById('last-ai-scan-time');
    
    try {
        const response = await fetch('/api/admin/scan-status');
        const data = await response.json();
        
        if (data.is_running) {
            if (btn) btn.disabled = true;
            if (aiBtn) aiBtn.disabled = true;
            if (btn) btn.classList.add('scanning-glow');
            if (aiBtn) aiBtn.classList.add('scanning-glow');
            const cancelBtn = document.getElementById('scan-cancel-btn');
            if (cancelBtn) cancelBtn.style.display = 'inline-block';
        } else {
            if (btn) btn.disabled = false;
            if (aiBtn) aiBtn.disabled = false;
            if (btn) btn.classList.remove('scanning-glow');
            if (aiBtn) aiBtn.classList.remove('scanning-glow');
            const cancelBtn = document.getElementById('scan-cancel-btn');
            if (cancelBtn) cancelBtn.style.display = 'none';
        }

        if (data.last_scan_at && timeLabel) {
            const date = new Date(data.last_scan_at);
            timeLabel.innerText = `Last: ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`;
        }
        if (data.last_ai_scan_at && aiTimeLabel) {
            const date = new Date(data.last_ai_scan_at);
            aiTimeLabel.innerText = `AI: ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`;
        }
    } catch (error) {
        console.error('Failed to update scan status:', error);
    }
}

async function triggerTechnicalScan() {
    const btn = document.getElementById('scan-market-btn');
    const strategy = document.getElementById('scan-strategy').value;
    if (btn.disabled) return;
    
    try {
        btn.innerHTML = '📡 ...';
        const response = await fetch(`/api/admin/scan-technical?strategy=${strategy}`, { method: 'POST' });
        const data = await response.json();
        console.log(data.message);
        setTimeout(updateScanStatus, 1000);
    } catch (error) {
        console.error('Technical scan failed:', error);
    } finally {
        btn.innerHTML = '📡 SCAN';
    }
}

async function triggerAIScreening() {
    const btn = document.getElementById('scan-ai-btn');
    const cancelBtn = document.getElementById('scan-cancel-btn');
    if (btn.disabled) return;
    
    try {
        btn.innerHTML = '🤖 ...';
        btn.disabled = true;
        if (cancelBtn) cancelBtn.style.display = 'inline-block';
        
        await fetch('/api/admin/scan-ai', { method: 'POST' });
        setTimeout(updateScanStatus, 1000);
    } catch (error) {
        console.error('AI screening failed:', error);
    } finally {
        btn.innerHTML = '🤖 AI SCREEN';
        // Wait bit more for status update to hide cancel btn
        setTimeout(() => {
            updateScanStatus();
        }, 3000);
    }
}

async function cancelAIScreening() {
    const cancelBtn = document.getElementById('scan-cancel-btn');
    try {
        if (cancelBtn) cancelBtn.innerHTML = '⏳ ...';
        const response = await fetch('/api/admin/scan-cancel', { method: 'POST' });
        alert("中断リクエストを送信しました。");
    } catch (e) {
        console.error(e);
    } finally {
        if (cancelBtn) {
            cancelBtn.innerHTML = '🛑 CANCEL';
            cancelBtn.style.display = 'none';
        }
    }
}

async function viewTradeAnalysis(symbol) {
    try {
        const response = await fetch(`/api/analysis/trade_prompt/${symbol}`);
        if (!response.ok) throw new Error("Failed to fetch trade prompt");
        const data = await response.json();
        showManualCopyModal(data.prompt);
    } catch (e) {
        console.error(e);
        alert(`エラー: ${e.message}`);
    }
}

async function syncNotebookLMToDrive() {
    const btn = document.getElementById('sync-drive-btn');
    if (btn) {
        btn.innerHTML = '⏳ 同期中...';
        btn.disabled = true;
    }

    try {
        const response = await fetch('/api/export/notebooklm/sync_drive', { method: 'POST' });
        const data = await response.json();
        if (data.status === 'success') {
            alert(`Google Drive への同期が完了しました！\nファイル: ${data.filename}\n共有先: ${data.shared_with}`);
            if (data.webViewLink) {
                window.open(data.webViewLink, '_blank');
            }
        } else {
            alert(`同期に失敗しました: ${data.detail || 'Unknown error'}`);
        }
    } catch (e) {
        console.error(e);
        alert(`エラーが発生しました: ${e.message}`);
    } finally {
        if (btn) {
            btn.innerHTML = '☁️ Drive同期';
            btn.disabled = false;
        }
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

// Help Modal Controls
function openHelpModal() {
    const overlay = document.getElementById('help-overlay');
    if (overlay) overlay.classList.add('active');
}

function closeHelpModal() {
    const overlay = document.getElementById('help-overlay');
    if (overlay) overlay.classList.remove('active');
}

// Manual Copy Modal Controls
function showManualCopyModal(text) {
    const overlay = document.getElementById('manual-copy-overlay');
    const textarea = document.getElementById('manual-copy-textarea');
    if (overlay && textarea) {
        textarea.value = text;
        overlay.classList.add('active');
        setTimeout(() => textarea.select(), 100);
    }
}

function closeManualCopyModal() {
    const overlay = document.getElementById('manual-copy-overlay');
    if (overlay) overlay.classList.remove('active');
}

async function moveToTrash(path) {
    if (!confirm("このレポートをゴミ箱へ移動しますか？")) return;
    try {
        const response = await fetch('/api/workspace/move_to_trash', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        if (response.ok) {
            // Unified refresh: Dashboard OR Explorer
            if (typeof fetchWorkspaceLinks === 'function') fetchWorkspaceLinks();
            if (typeof fetchStructure === 'function') fetchStructure();
        } else {
            alert("移動に失敗しました。");
        }
    } catch (e) {
        console.error(e);
    }
}

async function deletePermanent(path) {
    if (!confirm("このファイルを完全に削除しますか？\nこの操作は取り消せません。")) return;
    try {
        const response = await fetch(`/api/workspace/delete_permanent?path=${encodeURIComponent(path)}`, {
            method: 'DELETE'
        });
        if (response.ok) {
            // Unified refresh: Dashboard OR Explorer
            if (typeof fetchWorkspaceLinks === 'function') fetchWorkspaceLinks();
            if (typeof fetchStructure === 'function') fetchStructure();
        } else {
            alert("削除に失敗しました。");
        }
    } catch (e) {
        console.error(e);
    }
}

async function triggerFullSync(event) {
    if (!confirm("ワークスペース全体のファイルを Google Drive に同期しますか？\n（Market_Data, AI_Reports, Portfolios が対象です）")) return;
    
    const btn = event?.currentTarget || event?.target || document.activeElement;
    const originalText = btn.innerHTML;
    btn.innerHTML = "⏳ 同期中...";
    btn.disabled = true;

    try {
        const response = await fetch('/api/sync/full_workspace', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (response.ok) {
            alert("Google Drive への全同期が完了しました。");
            if (data.root_link) window.open(data.root_link, '_blank');
        } else {
            alert("同期に失敗しました: " + (data.detail || "Unknown error"));
        }
    } catch (e) {
        console.error(e);
        alert("通信エラーが発生しました。");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

