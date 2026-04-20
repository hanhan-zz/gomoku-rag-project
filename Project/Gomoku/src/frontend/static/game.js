// Direct replacement for static/game.js
// Works with the current-session backend APIs:
// - POST /api/new-game
// - POST /api/play-turn
// - POST /api/why
// - POST /api/review
//
// Expected HTML element IDs:
// - gameCanvas
// - status
// - reasoning
// - newGameBtn
// - whyBtn
// - reviewBtn
// - downloadBtn
// - explainPanel
// - reviewPanel
// - reviewLoading
// - reviewHint
// - winRateContainer
// - winRateChart

const BOARD_SIZE = 15;
const CELL_SIZE = 40;
const PADDING = 20;
const STONE_RADIUS = 16;

const EMPTY = 0;
const BLACK = 1;
const WHITE = 2;

let board = [];
let gameOver = false;
let lastAiStepId = null;
let isSubmitting = false;
let winRateChart = null;
let latestReviewData = null;

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const statusEl = document.getElementById('status');
const reasoningEl = document.getElementById('reasoning');
const newGameBtn = document.getElementById('newGameBtn');
const whyBtn = document.getElementById('whyBtn');
const reviewBtn = document.getElementById('reviewBtn');
const downloadBtn = document.getElementById('downloadBtn');
const personalityBtn = document.getElementById('personalityBtn');
const personalityPanel = document.getElementById('personalityPanel');
const personalityLoading = document.getElementById('personalityLoading');

const explainPanel = document.getElementById('explainPanel');
const reviewPanel = document.getElementById('reviewPanel');
const reviewLoading = document.getElementById('reviewLoading');
const reviewHint = document.getElementById('reviewHint');

const winRateContainer = document.getElementById('winRateContainer');
const winRateCanvas = document.getElementById('winRateChart');

function createEmptyBoard() {
    return Array.from({ length: BOARD_SIZE }, () => Array(BOARD_SIZE).fill(EMPTY));
}

function setStatus(text, type = '') {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.className = 'status';
    if (type) statusEl.classList.add(type);
}

function setReasoning(text) {
    if (reasoningEl) reasoningEl.textContent = text || '';
}

function setBusyState(busy) {
    isSubmitting = busy;

    if (newGameBtn) newGameBtn.disabled = busy;
    if (whyBtn) whyBtn.disabled = busy || !lastAiStepId;

    if (reviewBtn) {
        reviewBtn.disabled = busy || !gameOver;
    }

    if (downloadBtn) {
        downloadBtn.disabled = busy || !latestReviewData;
    }

    if (personalityBtn) {
        personalityBtn.disabled = busy || !latestReviewData;
    }
}

function updateButtons() {
    if (whyBtn) whyBtn.disabled = isSubmitting || !lastAiStepId;

    if (reviewBtn) {
        reviewBtn.disabled = isSubmitting || !gameOver;
    }

    if (newGameBtn) newGameBtn.disabled = isSubmitting;

    if (downloadBtn) {
        downloadBtn.disabled = isSubmitting || !latestReviewData;
    }

    if (personalityBtn) {
        personalityBtn.disabled = isSubmitting || !latestReviewData;
    }
}

function clearPanels() {
    latestReviewData = null;

    if (explainPanel) {
        explainPanel.innerHTML = `
            <p class="placeholder-text">回答将显示在这里...</p>
            <ul>
                <li>落子原因</li>
                <li>可选替代点</li>
                <li>相关策略依据</li>
            </ul>
        `;
    }

    if (reviewPanel) {
        reviewPanel.innerHTML = `
            <p class="placeholder-text">复盘结果将显示在这里...</p>
            <ul>
                <li>本局总结</li>
                <li>关键转折点</li>
                <li>失误分析</li>
                <li>改进建议</li>
            </ul>
        `;
    }

    if (personalityPanel) {
        personalityPanel.style.display = 'none';
        personalityPanel.innerHTML = `
            <p class="placeholder-text">人格测试结果将显示在这里...</p>
            <ul>
                <li>人格类型</li>
                <li>风格称号</li>
                <li>优势与风险</li>
                <li>趣味点评</li>
            </ul>
        `;
    }

    if (personalityLoading) personalityLoading.style.display = 'none';
    if (reviewLoading) reviewLoading.style.display = 'none';
    if (reviewHint) reviewHint.style.display = 'block';

    if (winRateContainer) {
        winRateContainer.style.display = 'none';
    }

    if (downloadBtn) {
        downloadBtn.style.display = 'none';
        downloadBtn.disabled = true;
    }

    if (personalityBtn) {
        personalityBtn.style.display = 'none';
        personalityBtn.disabled = true;
    }

    if (winRateChart) {
        winRateChart.destroy();
        winRateChart = null;
    }
}

function updateStatus() {
    if (gameOver) {
        setStatus('对局结束，可生成复盘', 'game-over');
        return;
    }
    setStatus('你的回合', 'your-turn');
}

function drawBoard() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#eecfa1';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;

    for (let i = 0; i < BOARD_SIZE; i++) {
        const pos = PADDING + i * CELL_SIZE;

        ctx.beginPath();
        ctx.moveTo(PADDING, pos);
        ctx.lineTo(PADDING + CELL_SIZE * (BOARD_SIZE - 1), pos);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(pos, PADDING);
        ctx.lineTo(pos, PADDING + CELL_SIZE * (BOARD_SIZE - 1));
        ctx.stroke();
    }

    const stars = [
        [3, 3], [7, 3], [11, 3],
        [3, 7], [7, 7], [11, 7],
        [3, 11], [7, 11], [11, 11]
    ];

    ctx.fillStyle = '#333';
    for (const [x, y] of stars) {
        ctx.beginPath();
        ctx.arc(PADDING + x * CELL_SIZE, PADDING + y * CELL_SIZE, 3, 0, Math.PI * 2);
        ctx.fill();
    }

    for (let y = 0; y < BOARD_SIZE; y++) {
        for (let x = 0; x < BOARD_SIZE; x++) {
            if (board[y][x] === EMPTY) continue;

            const cx = PADDING + x * CELL_SIZE;
            const cy = PADDING + y * CELL_SIZE;

            ctx.beginPath();
            ctx.arc(cx, cy, STONE_RADIUS, 0, Math.PI * 2);

            if (board[y][x] === BLACK) {
                ctx.fillStyle = '#111';
                ctx.fill();
            } else if (board[y][x] === WHITE) {
                ctx.fillStyle = '#f7f7f7';
                ctx.fill();
                ctx.strokeStyle = '#666';
                ctx.stroke();
            }
        }
    }
}

function toBoardCoord(clickX, clickY) {
    const x = Math.round((clickX - PADDING) / CELL_SIZE);
    const y = Math.round((clickY - PADDING) / CELL_SIZE);
    return { x, y };
}

function isWithinBoard(x, y) {
    return x >= 0 && x < BOARD_SIZE && y >= 0 && y < BOARD_SIZE;
}

function escapeHtml(text) {
    return String(text ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function renderExplain(data) {
    if (!explainPanel) return;

    const explanation = data?.explanation || '';
    const evidence = Array.isArray(data?.evidence) ? data.evidence : [];
    const alternatives = Array.isArray(data?.alternatives) ? data.alternatives : [];

    explainPanel.innerHTML = `
        <h3>AI Move Explanation</h3>
        <p>${escapeHtml(explanation)}</p>
        <p><strong>Evidence</strong></p>
        <ul>${evidence.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        ${alternatives.length ? `
            <p><strong>Alternatives</strong></p>
            <ul>${alternatives.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        ` : ''}
    `;
}

function renderReview(data) {
    if (!reviewPanel) return;

    const summary = data?.summary || '';
    const turningPoints = Array.isArray(data?.turning_points) ? data.turning_points : [];
    const mistakes = Array.isArray(data?.mistakes) ? data.mistakes : [];
    const suggestions = Array.isArray(data?.suggestions) ? data.suggestions : [];
    const evidence = Array.isArray(data?.evidence) ? data.evidence : [];

    reviewPanel.innerHTML = `
        <h3>Post-game Review</h3>
        <p><strong>Summary:</strong> ${escapeHtml(summary)}</p>
        <p><strong>Turning Points</strong></p>
        <ul>${turningPoints.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        <p><strong>Mistakes</strong></p>
        <ul>${mistakes.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        <p><strong>Suggestions</strong></p>
        <ul>${suggestions.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        <p><strong>Evidence</strong></p>
        <ul>${evidence.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
    `;
}

function renderPersonality(data) {
    if (!personalityPanel) return;

    const personalityType = data?.personality_type || '';
    const title = data?.title || '';
    const description = data?.description || '';
    const strengths = Array.isArray(data?.strengths) ? data.strengths : [];
    const risks = Array.isArray(data?.risks) ? data.risks : [];
    const advice = Array.isArray(data?.advice) ? data.advice : [];
    const funComment = data?.fun_comment || '';

    personalityPanel.style.display = 'block';
    personalityPanel.innerHTML = `
        <h3>Gomoku Personality Test</h3>
        <div class="personality-tag">${escapeHtml(personalityType)}</div>

        <p><strong>称号：</strong>${escapeHtml(title)}</p>
        <p><strong>画像描述：</strong>${escapeHtml(description)}</p>

        <div class="personality-section">
            <strong>你的优势</strong>
            <ul>${strengths.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        </div>

        <div class="personality-section">
            <strong>潜在风险</strong>
            <ul>${risks.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        </div>

        <div class="personality-section">
            <strong>成长建议</strong>
            <ul>${advice.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        </div>

        <div class="personality-fun">
            ${escapeHtml(funComment)}
        </div>
    `;
}

function renderWinRateChart(series) {
    if (!winRateContainer || !winRateCanvas) return;

    if (!Array.isArray(series) || series.length === 0) {
        winRateContainer.style.display = 'none';
        if (winRateChart) {
            winRateChart.destroy();
            winRateChart = null;
        }
        return;
    }

    if (typeof Chart === 'undefined') {
        console.error('Chart.js is not loaded. Cannot render win-rate chart.');
        return;
    }

    winRateContainer.style.display = 'block';

    const labels = series.map(item => `Step ${item.step}`);
    const values = series.map(item => item.winrate_ai);
    const pointColors = series.map(item => item.player === 'ai' ? '#ef6c00' : '#2b6cb0');

    if (winRateChart) {
        winRateChart.destroy();
        winRateChart = null;
    }

    winRateChart = new Chart(winRateCanvas.getContext('2d'), {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'AI Win Rate (%)',
                data: values,
                borderColor: '#ef6c00',
                backgroundColor: 'rgba(239, 108, 0, 0.12)',
                pointBackgroundColor: pointColors,
                pointBorderColor: pointColors,
                pointRadius: 4,
                pointHoverRadius: 6,
                fill: true,
                tension: 0.35
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            scales: {
                y: {
                    beginAtZero: true,
                    min: 0,
                    max: 100,
                    title: {
                        display: true,
                        text: 'AI Win Rate (%)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Move Number'
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        afterLabel: function (context) {
                            const point = series[context.dataIndex];
                            const side = point.player === 'ai' ? 'White (AI)' : 'Black (Human)';
                            return `Move by: ${side}`;
                        }
                    }
                }
            }
        }
    });
}

function buildMarkdownReport(reviewData) {
    const summary = reviewData?.summary || 'No summary';
    const turningPoints = Array.isArray(reviewData?.turning_points) ? reviewData.turning_points : [];
    const mistakes = Array.isArray(reviewData?.mistakes) ? reviewData.mistakes : [];
    const suggestions = Array.isArray(reviewData?.suggestions) ? reviewData.suggestions : [];
    const evidence = Array.isArray(reviewData?.evidence) ? reviewData.evidence : [];
    const winrateSeries = Array.isArray(reviewData?.winrate_series) ? reviewData.winrate_series : [];
    const winner = reviewData?.winner || 'unknown';
    const totalSteps = reviewData?.total_steps || 0;

    const bullet = (items) => {
        if (!items.length) return '- None';
        return items.map(item => `- ${item}`).join('\n');
    };

    const trendLines = winrateSeries.length
        ? winrateSeries.map(item =>
            `- Step ${item.step} (${item.player === 'human' ? 'Black/Human' : 'White/AI'}): AI win rate ${item.winrate_ai}%`
        ).join('\n')
        : '- No data';

    return `# Gomoku Review Report

Generated at: ${new Date().toLocaleString()}

## Game Overview
- Winner: ${winner}
- Total steps: ${totalSteps}

## Summary
${summary}

## Turning Points
${bullet(turningPoints)}

## Mistakes
${bullet(mistakes)}

## Suggestions
${bullet(suggestions)}

## Evidence
${bullet(evidence)}

## Win Rate Trend
${trendLines}
`;
}

function downloadTextFile(filename, content, mime = 'text/markdown;charset=utf-8') {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();

    URL.revokeObjectURL(url);
}

async function initGame() {
    setBusyState(true);
    try {
        const response = await fetch('/api/new-game', { method: 'POST' });
        if (!response.ok) {
            throw new Error(`new-game failed: ${response.status}`);
        }

        const data = await response.json();
        board = Array.isArray(data.board) ? data.board : createEmptyBoard();
        gameOver = Boolean(data.game_over);
        lastAiStepId = null;

        clearPanels();
        setReasoning('');
        updateStatus();
        drawBoard();
    } catch (err) {
        console.error(err);
        setStatus('Failed to start new game', 'game-over');
    } finally {
        setBusyState(false);
        updateButtons();
    }
}

async function playTurn(x, y) {
    if (!isWithinBoard(x, y) || board[y][x] !== EMPTY || gameOver || isSubmitting) {
        return;
    }

    const previousBoard = board.map(row => [...row]);
    board[y][x] = BLACK;
    drawBoard();

    setBusyState(true);
    setStatus('Submitting move...', 'ai-turn');

    try {
        const response = await fetch('/api/play-turn', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ x, y })
        });

        if (!response.ok) {
            let message = `play-turn failed: ${response.status}`;
            try {
                message = await response.text();
            } catch (e) { }
            throw new Error(message);
        }

        const data = await response.json();
        board = Array.isArray(data.board) ? data.board : previousBoard;
        gameOver = Boolean(data.game_over);

        if (data.ai_move && typeof data.ai_move.step_id === 'number') {
            lastAiStepId = data.ai_move.step_id;
        }

        setReasoning(data.reasoning ? `AI: ${data.reasoning}` : '');
        drawBoard();

        if (gameOver) {
            const winner = data.winner || 'unknown';
            setStatus(`Game Over: ${winner} wins`, 'game-over');
        } else {
            updateStatus();
        }
    } catch (err) {
        console.error(err);
        board = previousBoard;
        drawBoard();
        setStatus('Move failed', 'game-over');
    } finally {
        setBusyState(false);
        updateButtons();
    }
}

async function askWhy() {
    if (!lastAiStepId) {
        setStatus('No AI move to explain yet', 'ai-turn');
        return;
    }

    setBusyState(true);
    setStatus('Generating explanation...', 'ai-turn');

    try {
        const response = await fetch('/api/why', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                step_id: lastAiStepId,
                question: 'Why did AI move here?'
            })
        });

        if (!response.ok) {
            let message = `why failed: ${response.status}`;
            try {
                message = await response.text();
            } catch (e) { }
            throw new Error(message);
        }

        const data = await response.json();
        renderExplain(data);
        updateStatus();
    } catch (err) {
        console.error(err);
        setStatus('Explanation failed', 'game-over');
    } finally {
        setBusyState(false);
        updateButtons();
    }
}

async function askReview() {
    // 要求 1：游戏过程中不能点击 Generate Review
    if (!gameOver) {
        setStatus('Finish the game before generating review', 'ai-turn');
        return;
    }

    setBusyState(true);
    setStatus('Generating review...', 'ai-turn');

    // 要求 3：生成 review 时强化 loading 显示
    if (reviewLoading) reviewLoading.style.display = 'flex';
    if (reviewHint) reviewHint.style.display = 'none';

    if (reviewPanel) {
        reviewPanel.innerHTML = `
            <p class="placeholder-text">正在生成复盘内容...</p>
            <ul>
                <li>分析关键转折点</li>
                <li>识别失误与策略问题</li>
                <li>生成改进建议</li>
                <li>绘制胜率走势</li>
            </ul>
        `;
    }

    try {
        const response = await fetch('/api/review', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        if (!response.ok) {
            let message = `review failed: ${response.status}`;
            try {
                message = await response.text();
            } catch (e) { }
            throw new Error(message);
        }

        const data = await response.json();

        latestReviewData = {
            ...data,
            winner: data.winner || 'unknown',
            total_steps: data.total_steps || 0
        };

        renderReview(data);
        renderWinRateChart(data.winrate_series || []);

        // 要求 2：只有生成完 review 后才能点下载
        if (downloadBtn) {
            downloadBtn.style.display = 'inline-block';
            downloadBtn.disabled = false;
        }

        if (personalityBtn) {
            personalityBtn.style.display = 'inline-block';
            personalityBtn.disabled = false;
        }

        updateStatus();
    } catch (err) {
        console.error(err);
        setStatus('Review failed', 'game-over');

        if (reviewPanel) {
            reviewPanel.innerHTML = `
                <p class="placeholder-text">复盘生成失败</p>
                <ul>
                    <li>请稍后重试</li>
                    <li>检查后端 /api/review 是否正常</li>
                </ul>
            `;
        }
    } finally {
        if (reviewLoading) reviewLoading.style.display = 'none';
        setBusyState(false);
        updateButtons();
    }
}

async function askPersonality() {
    if (!latestReviewData) {
        setStatus('Generate review first', 'ai-turn');
        return;
    }

    setBusyState(true);
    setStatus('Generating personality test...', 'ai-turn');

    if (personalityLoading) personalityLoading.style.display = 'flex';
    if (personalityPanel) personalityPanel.style.display = 'none';

    try {
        const response = await fetch('/api/personality-test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        if (!response.ok) {
            let message = `personality-test failed: ${response.status}`;
            try {
                message = await response.text();
            } catch (e) {}
            throw new Error(message);
        }

        const data = await response.json();
        renderPersonality(data);
        updateStatus();
    } catch (err) {
        console.error(err);
        setStatus('Personality test failed', 'game-over');

        if (personalityPanel) {
            personalityPanel.style.display = 'block';
            personalityPanel.innerHTML = `
                <p class="placeholder-text">人格测试生成失败</p>
                <ul>
                    <li>请确认后端 /api/personality-test 已实现</li>
                    <li>请先生成复盘结果后再测试</li>
                </ul>
            `;
        }
    } finally {
        if (personalityLoading) personalityLoading.style.display = 'none';
        setBusyState(false);
        updateButtons();
    }
}

function downloadReport() {
    if (!latestReviewData) {
        setStatus('Generate review first', 'ai-turn');
        return;
    }

    const markdown = buildMarkdownReport(latestReviewData);
    downloadTextFile('gomoku_review_report.md', markdown);
}

canvas.addEventListener('click', async (e) => {
    if (gameOver || isSubmitting) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const clickX = (e.clientX - rect.left) * scaleX;
    const clickY = (e.clientY - rect.top) * scaleY;

    const { x, y } = toBoardCoord(clickX, clickY);
    if (!isWithinBoard(x, y)) return;

    await playTurn(x, y);
});

if (newGameBtn) {
    newGameBtn.addEventListener('click', async () => {
        await initGame();
    });
}

if (whyBtn) {
    whyBtn.addEventListener('click', async () => {
        await askWhy();
    });
}

if (reviewBtn) {
    reviewBtn.addEventListener('click', async () => {
        await askReview();
    });
}

if (downloadBtn) {
    downloadBtn.addEventListener('click', () => {
        downloadReport();
    });
}

if (personalityBtn) {
    personalityBtn.addEventListener('click', async () => {
        await askPersonality();
    });
}

board = createEmptyBoard();
drawBoard();
updateButtons();
initGame();