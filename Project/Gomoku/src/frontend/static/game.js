/**
 * Gomoku Game Client
 * Handles game logic on frontend and communication with backend API
 */

// Constants
const BOARD_SIZE = 15;
const EMPTY = 0;
const BLACK = 1;  // Human
const WHITE = 2;  // AI

// Game state
let board = [];
let currentPlayer = BLACK;
let gameOver = false;
let winningLine = [];
let moveHistory = [];

// DOM elements
const canvas = document.getElementById('board');
const ctx = canvas.getContext('2d');
const statusEl = document.getElementById('status');
const reasoningEl = document.getElementById('reasoning');
const newGameBtn = document.getElementById('newGameBtn');
const undoBtn = document.getElementById('undoBtn');
const messageBox = document.getElementById('messageBox');
const messageText = document.getElementById('messageText');
const closeMessageBtn = document.getElementById('closeMessage');

// Board rendering
const CELL_SIZE = canvas.width / BOARD_SIZE;
const PADDING = CELL_SIZE / 2;
const PIECE_RADIUS = CELL_SIZE * 0.4;

/**
 * Initialize the game
 */
function initGame() {
    // Create empty board
    board = Array(BOARD_SIZE).fill(null).map(() => Array(BOARD_SIZE).fill(EMPTY));
    currentPlayer = BLACK;
    gameOver = false;
    winningLine = [];
    moveHistory = [];

    // Clear reasoning
    reasoningEl.classList.add('hidden');
    reasoningEl.textContent = '';

    // Update UI
    updateStatus();
    undoBtn.disabled = true;

    // Render
    drawBoard();
}

/**
 * Draw the game board
 */
function drawBoard() {
    // Clear canvas
    ctx.fillStyle = '#deb887';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw grid lines
    ctx.strokeStyle = '#8b4513';
    ctx.lineWidth = 1;

    for (let i = 0; i < BOARD_SIZE; i++) {
        // Vertical lines
        ctx.beginPath();
        ctx.moveTo(PADDING + i * CELL_SIZE, PADDING);
        ctx.lineTo(PADDING + i * CELL_SIZE, canvas.height - PADDING);
        ctx.stroke();

        // Horizontal lines
        ctx.beginPath();
        ctx.moveTo(PADDING, PADDING + i * CELL_SIZE);
        ctx.lineTo(canvas.width - PADDING, PADDING + i * CELL_SIZE);
        ctx.stroke();
    }

    // Draw star points (天元和星位)
    const starPoints = [
        [3, 3], [3, 7], [3, 11],
        [7, 3], [7, 7], [7, 11],
        [11, 3], [11, 7], [11, 11]
    ];

    ctx.fillStyle = '#8b4513';
    starPoints.forEach(([x, y]) => {
        ctx.beginPath();
        ctx.arc(PADDING + x * CELL_SIZE, PADDING + y * CELL_SIZE, 4, 0, Math.PI * 2);
        ctx.fill();
    });

    // Draw pieces
    drawPieces();

    // Highlight winning line
    if (winningLine.length > 0) {
        highlightWinningLine();
    }
}

/**
 * Draw all pieces on the board
 */
function drawPieces() {
    for (let y = 0; y < BOARD_SIZE; y++) {
        for (let x = 0; x < BOARD_SIZE; x++) {
            if (board[y][x] !== EMPTY) {
                drawPiece(x, y, board[y][x]);
            }
        }
    }
}

/**
 * Draw a single piece
 */
function drawPiece(x, y, player) {
    const cx = PADDING + x * CELL_SIZE;
    const cy = PADDING + y * CELL_SIZE;

    // Shadow
    ctx.beginPath();
    ctx.arc(cx + 2, cy + 2, PIECE_RADIUS, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0, 0, 0, 0.2)';
    ctx.fill();

    // Piece
    ctx.beginPath();
    ctx.arc(cx, cy, PIECE_RADIUS, 0, Math.PI * 2);

    if (player === BLACK) {
        const gradient = ctx.createRadialGradient(cx - 3, cy - 3, 0, cx, cy, PIECE_RADIUS);
        gradient.addColorStop(0, '#4a4a4a');
        gradient.addColorStop(1, '#1a1a1a');
        ctx.fillStyle = gradient;
    } else {
        const gradient = ctx.createRadialGradient(cx - 3, cy - 3, 0, cx, cy, PIECE_RADIUS);
        gradient.addColorStop(0, '#ffffff');
        gradient.addColorStop(1, '#e0e0e0');
        ctx.fillStyle = gradient;
    }
    ctx.fill();

    // Border
    ctx.strokeStyle = player === BLACK ? '#333' : '#bbb';
    ctx.lineWidth = 1;
    ctx.stroke();
}

/**
 * Highlight the winning line
 */
function highlightWinningLine() {
    ctx.strokeStyle = '#22c55e';
    ctx.lineWidth = 4;
    ctx.lineCap = 'round';

    ctx.beginPath();
    winningLine.forEach(([x, y], index) => {
        const cx = PADDING + x * CELL_SIZE;
        const cy = PADDING + y * CELL_SIZE;
        if (index === 0) {
            ctx.moveTo(cx, cy);
        } else {
            ctx.lineTo(cx, cy);
        }
    });
    ctx.stroke();
}

/**
 * Handle canvas click
 */
canvas.addEventListener('click', async (e) => {
    if (gameOver || currentPlayer !== BLACK) {
        return;
    }

    // Get click position
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const clickX = (e.clientX - rect.left) * scaleX;
    const clickY = (e.clientY - rect.top) * scaleY;

    // Convert to board coordinates
    const x = Math.round((clickX - PADDING) / CELL_SIZE);
    const y = Math.round((clickY - PADDING) / CELL_SIZE);

    // Validate coordinates
    if (x < 0 || x >= BOARD_SIZE || y < 0 || y >= BOARD_SIZE) {
        return;
    }

    // Check if position is empty
    if (board[y][x] !== EMPTY) {
        return;
    }

    // Make move
    await makeMove(x, y, BLACK);

    // Check game over
    if (gameOver) {
        return;
    }

    // AI's turn
    await aiMove();
});

/**
 * Make a move
 */
async function makeMove(x, y, player) {
    // Update board
    board[y][x] = player;
    moveHistory.push({ x, y, player });

    // Redraw
    drawBoard();

    // Check win
    const winner = checkWin(x, y, player);
    if (winner) {
        gameOver = true;
        winningLine = getWinningLine(x, y, player);
        drawBoard();
        showGameOver(winner);
        return;
    }

    // Check draw
    if (isBoardFull()) {
        gameOver = true;
        showGameOver(null);
        return;
    }

    // Switch player
    currentPlayer = player === BLACK ? WHITE : BLACK;
    updateStatus();

    // Update undo button
    undoBtn.disabled = moveHistory.length === 0;
}

/**
 * AI move using backend API
 */
async function aiMove() {
    if (gameOver) return;

    // Update status
    statusEl.textContent = 'AI 思考中...';
    statusEl.className = 'status ai-turn';
    canvas.classList.add('disabled');

    try {
        const response = await fetch('/api/move', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                board: board,
                player: 'white'
            })
        });

        if (!response.ok) {
            throw new Error('API request failed');
        }

        const data = await response.json();
        const { x, y, reasoning } = data;

        // Show reasoning
        reasoningEl.textContent = `AI: ${reasoning}`;
        reasoningEl.classList.remove('hidden');

        // Make the move
        await makeMove(x, y, WHITE);

    } catch (error) {
        console.error('AI move error:', error);
        reasoningEl.textContent = 'AI 请求失败，请重试';
        reasoningEl.classList.remove('hidden');
        currentPlayer = BLACK;
        updateStatus();
    } finally {
        canvas.classList.remove('disabled');
    }
}

/**
 * Check if there's a winner at position (x, y)
 */
function checkWin(x, y, player) {
    const directions = [
        [1, 0],   // Horizontal
        [0, 1],   // Vertical
        [1, 1],   // Main diagonal
        [1, -1]   // Anti-diagonal
    ];

    for (const [dx, dy] of directions) {
        let count = 1;
        count += countDirection(x, y, dx, dy, player);
        count += countDirection(x, y, -dx, -dy, player);

        if (count >= 5) {
            return player;
        }
    }

    return null;
}

/**
 * Count consecutive pieces in a direction
 */
function countDirection(x, y, dx, dy, player) {
    let count = 0;
    let nx = x + dx;
    let ny = y + dy;

    while (nx >= 0 && nx < BOARD_SIZE && ny >= 0 && ny < BOARD_SIZE) {
        if (board[ny][nx] === player) {
            count++;
            nx += dx;
            ny += dy;
        } else {
            break;
        }
    }

    return count;
}

/**
 * Get the winning line coordinates
 */
function getWinningLine(x, y, player) {
    const directions = [
        [1, 0],   // Horizontal
        [0, 1],   // Vertical
        [1, 1],   // Main diagonal
        [1, -1]   // Anti-diagonal
    ];

    for (const [dx, dy] of directions) {
        let line = [[x, y]];

        // Count in positive direction
        let nx = x + dx;
        let ny = y + dy;
        while (nx >= 0 && nx < BOARD_SIZE && ny >= 0 && ny < BOARD_SIZE) {
            if (board[ny][nx] === player) {
                line.push([nx, ny]);
                nx += dx;
                ny += dy;
            } else {
                break;
            }
        }

        // Count in negative direction
        nx = x - dx;
        ny = y - dy;
        while (nx >= 0 && nx < BOARD_SIZE && ny >= 0 && ny < BOARD_SIZE) {
            if (board[ny][nx] === player) {
                line.unshift([nx, ny]);
                nx -= dx;
                ny -= dy;
            } else {
                break;
            }
        }

        if (line.length >= 5) {
            return line.slice(0, 5);
        }
    }

    return [];
}

/**
 * Check if board is full
 */
function isBoardFull() {
    for (let y = 0; y < BOARD_SIZE; y++) {
        for (let x = 0; x < BOARD_SIZE; x++) {
            if (board[y][x] === EMPTY) {
                return false;
            }
        }
    }
    return true;
}

/**
 * Update status display
 */
function updateStatus() {
    if (gameOver) {
        statusEl.textContent = '游戏结束';
        statusEl.className = 'status game-over';
    } else if (currentPlayer === BLACK) {
        statusEl.textContent = '你的回合';
        statusEl.className = 'status your-turn';
    } else {
        statusEl.textContent = 'AI 回合';
        statusEl.className = 'status ai-turn';
    }
}

/**
 * Show game over message
 */
function showGameOver(winner) {
    updateStatus();

    if (winner === BLACK) {
        messageText.textContent = '🎉 恭喜！你赢了！';
    } else if (winner === WHITE) {
        messageText.textContent = '😅 AI 获胜！再接再厉！';
    } else {
        messageText.textContent = '🤝 平局！';
    }

    messageBox.classList.remove('hidden');
    // Create overlay
    let overlay = document.querySelector('.overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'overlay';
        document.body.appendChild(overlay);
    }
    overlay.classList.remove('hidden');

    canvas.classList.add('winning');
}

/**
 * Close message box
 */
closeMessageBtn.addEventListener('click', () => {
    messageBox.classList.add('hidden');
    const overlay = document.querySelector('.overlay');
    if (overlay) {
        overlay.classList.add('hidden');
    }
});

/**
 * New game button
 */
newGameBtn.addEventListener('click', () => {
    initGame();
});

/**
 * Undo button
 */
undoBtn.addEventListener('click', async () => {
    if (moveHistory.length < 2 || gameOver) {
        return;
    }

    // Remove AI's last move
    if (moveHistory.length > 0) {
        const aiMove = moveHistory.pop();
        board[aiMove.y][aiMove.x] = EMPTY;
    }

    // Remove player's last move
    if (moveHistory.length > 0) {
        const playerMove = moveHistory.pop();
        board[playerMove.y][playerMove.x] = EMPTY;
    }

    // Update state
    currentPlayer = BLACK;
    reasoningEl.classList.add('hidden');
    updateStatus();
    undoBtn.disabled = moveHistory.length === 0;

    // Redraw
    drawBoard();
});

// Initialize game on load
initGame();
