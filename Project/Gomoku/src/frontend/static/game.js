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
// - explainPanel
// - reviewPanel

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

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const statusEl = document.getElementById('status');
const reasoningEl = document.getElementById('reasoning');
const newGameBtn = document.getElementById('newGameBtn');
const whyBtn = document.getElementById('whyBtn');
const reviewBtn = document.getElementById('reviewBtn');
const explainPanel = document.getElementById('explainPanel');
const reviewPanel = document.getElementById('reviewPanel');

function createEmptyBoard() {
    return Array.from({ length: BOARD_SIZE }, () => Array(BOARD_SIZE).fill(EMPTY));
}

function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
}

function setReasoning(text) {
    if (reasoningEl) reasoningEl.textContent = text || '';
}

function setBusyState(busy) {
    isSubmitting = busy;

    if (newGameBtn) newGameBtn.disabled = busy;
    if (whyBtn) whyBtn.disabled = busy || !lastAiStepId;
    if (reviewBtn) reviewBtn.disabled = busy;
}

function updateButtons() {
    if (whyBtn) whyBtn.disabled = isSubmitting || !lastAiStepId;
    if (reviewBtn) reviewBtn.disabled = isSubmitting;
    if (newGameBtn) newGameBtn.disabled = isSubmitting;
}

function clearPanels() {
    if (explainPanel) explainPanel.innerHTML = '';
    if (reviewPanel) reviewPanel.innerHTML = '';
}

function updateStatus() {
    if (gameOver) return;
    setStatus('Your turn (Black)');
}

function drawBoard() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#DEB887';
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

function escapeHtml(text) {
    return String(text)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
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
        setStatus('Failed to start new game');
    } finally {
        setBusyState(false);
        updateButtons();
    }
}

async function playTurn(x, y) {
    setBusyState(true);
    setStatus('Submitting move...');

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
            } catch (e) {}
            throw new Error(message);
        }

        const data = await response.json();
        board = Array.isArray(data.board) ? data.board : board;
        gameOver = Boolean(data.game_over);

        if (data.ai_move && typeof data.ai_move.step_id === 'number') {
            lastAiStepId = data.ai_move.step_id;
        }

        setReasoning(data.reasoning ? `AI: ${data.reasoning}` : '');
        drawBoard();

        if (gameOver) {
            const winner = data.winner || 'unknown';
            setStatus(`Game Over: ${winner} wins`);
        } else {
            updateStatus();
        }
    } catch (err) {
        console.error(err);
        setStatus('Move failed');
    } finally {
        setBusyState(false);
        updateButtons();
    }
}

async function askWhy() {
    if (!lastAiStepId) {
        setStatus('No AI move to explain yet');
        return;
    }

    setBusyState(true);
    setStatus('Generating explanation...');

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
            } catch (e) {}
            throw new Error(message);
        }

        const data = await response.json();
        renderExplain(data);
        updateStatus();
    } catch (err) {
        console.error(err);
        setStatus('Explanation failed');
    } finally {
        setBusyState(false);
        updateButtons();
    }
}

async function askReview() {
    setBusyState(true);
    setStatus('Generating review...');

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
            } catch (e) {}
            throw new Error(message);
        }

        const data = await response.json();
        renderReview(data);
        updateStatus();
    } catch (err) {
        console.error(err);
        setStatus('Review failed');
    } finally {
        setBusyState(false);
        updateButtons();
    }
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

board = createEmptyBoard();
drawBoard();
updateButtons();
initGame();