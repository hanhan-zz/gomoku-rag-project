"""
FastAPI application for Gomoku Game with AI
Integrates real game logic and AI decision-making
"""

import random
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from game import GomokuGame, BLACK, WHITE, EMPTY, BOARD_SIZE
from llm_client import LLMClient

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Gomoku Game API")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class MoveRequest(BaseModel):
    board: list[list[int]]
    player: str  # "black" or "white"


class MoveResponse(BaseModel):
    x: int
    y: int
    reasoning: str


class HealthResponse(BaseModel):
    status: str


class ValidateRequest(BaseModel):
    board: list[list[int]]
    x: int
    y: int


class ValidateResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# LLM Client (lazy init)
# ---------------------------------------------------------------------------

_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
        try:
            _llm_client.connect()
        except Exception:
            pass
    return _llm_client


# ---------------------------------------------------------------------------
# Minimax AI (fallback when LLM is unavailable)
# ---------------------------------------------------------------------------

def _evaluate_position(board: list[list[int]], x: int, y: int, player: int) -> int:
    """Simple heuristic score for a board position."""
    opponent = WHITE if player == BLACK else BLACK
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    score = 0

    for dx, dy in directions:
        # Count player's pieces in positive direction
        my_count_pos = 0
        blocked_pos = False
        for step in range(1, 5):
            nx, ny = x + dx * step, y + dy * step
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if board[ny][nx] == player:
                    my_count_pos += 1
                else:
                    blocked_pos = True
                    break
            else:
                blocked_pos = True
                break

        # Count player's pieces in negative direction
        my_count_neg = 0
        blocked_neg = False
        for step in range(1, 5):
            nx, ny = x - dx * step, y - dy * step
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if board[ny][nx] == player:
                    my_count_neg += 1
                else:
                    blocked_neg = True
                    break
            else:
                blocked_neg = True
                break

        # Count opponent's pieces in positive direction
        opp_count_pos = 0
        opp_blocked_pos = False
        for step in range(1, 5):
            nx, ny = x + dx * step, y + dy * step
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if board[ny][nx] == opponent:
                    opp_count_pos += 1
                else:
                    opp_blocked_pos = True
                    break
            else:
                opp_blocked_pos = True
                break

        # Count opponent's pieces in negative direction
        opp_count_neg = 0
        opp_blocked_neg = False
        for step in range(1, 5):
            nx, ny = x - dx * step, y - dy * step
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if board[ny][nx] == opponent:
                    opp_count_neg += 1
                else:
                    opp_blocked_neg = True
                    break
            else:
                opp_blocked_neg = True
                break

        my_line = my_count_pos + my_count_neg + 1
        opp_line = opp_count_pos + opp_count_neg + 1

        # Win / threat detection
        if my_line >= 5:
            score += 100000  # Already 5-in-a-row
        elif my_count_pos + my_count_neg == 3:
            # Exactly 4 in a row (not 5 yet) — winning opportunity
            if not (blocked_pos and blocked_neg):
                score += 50000
        elif my_count_pos + my_count_neg == 2 and not (blocked_pos and blocked_neg):
            score += 1000
        elif my_count_pos + my_count_neg == 1 and not (blocked_pos and blocked_neg):
            score += 100
        elif my_count_pos + my_count_neg == 0 and not (blocked_pos and blocked_neg):
            score += 10

        # Block opponent's threats
        if opp_count_pos + opp_count_neg >= 3 and not (opp_blocked_pos and opp_blocked_neg):
            score += 5000

    return score


def _minimax_ai(board: list[list[int]], player: int) -> tuple[int, int, str]:
    """Pick the best move using a simple evaluation heuristic."""
    opponent = WHITE if player == BLACK else BLACK
    best_score = -1
    best_moves: list[tuple[int, int]] = []

    # Only consider positions near existing pieces
    candidates: set[tuple[int, int]] = set()
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            if board[y][x] != EMPTY:
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[ny][nx] == EMPTY:
                            candidates.add((nx, ny))

    if not candidates:
        candidates.add((7, 7))  # Center as default

    for x, y in candidates:
        score = _evaluate_position(board, x, y, player)
        if score > best_score:
            best_score = score
            best_moves = [(x, y)]
        elif score == best_score:
            best_moves.append((x, y))

    x, y = random.choice(best_moves)

    if best_score >= 50000:
        reasoning = f"在 ({x}, {y}) 落子可直接获胜"
    elif best_score >= 5000:
        reasoning = f"在 ({x}, {y}) 落子阻止对方获胜"
    elif best_score >= 1000:
        reasoning = f"在 ({x}, {y}) 落子形成三连"
    elif best_score >= 100:
        reasoning = f"在 ({x}, {y}) 落子形成二连"
    else:
        reasoning = f"评估后在 ({x}, {y}) 落子"

    return x, y, reasoning


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Serve the main game page."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(status="ok")


@app.post("/api/move", response_model=MoveResponse)
async def make_move(request: MoveRequest):
    """
    Generate an AI move.
    Uses LLM when available; falls back to minimax heuristic.
    """
    # Validate board dimensions
    if len(request.board) != BOARD_SIZE:
        raise HTTPException(status_code=400, detail=f"Board must be {BOARD_SIZE}x{BOARD_SIZE}")
    for row in request.board:
        if len(row) != BOARD_SIZE:
            raise HTTPException(status_code=400, detail="Invalid board row length")

    # Find empty positions
    empty_positions = []
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            if request.board[y][x] == EMPTY:
                empty_positions.append((x, y))

    if not empty_positions:
        raise HTTPException(status_code=400, detail="Board is full")

    # Validate player
    player = WHITE if request.player == "white" else BLACK

    # Try LLM first
    x, y, reasoning = None, None, None
    try:
        client = get_llm_client()
        if client.client is not None:
            result = client.generate_move(request.board, request.player)
            x, y = result["x"], result["y"]
            reasoning = result.get("reasoning", "")
            # Validate the returned position
            if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
                raise ValueError("Invalid coordinates from LLM")
            if request.board[y][x] != EMPTY:
                raise ValueError("LLM returned an occupied position")
    except Exception:
        # Fallback to minimax AI
        x, y, reasoning = _minimax_ai(request.board, player)

    # Double-check fallback
    if x is None or request.board[y][x] != EMPTY:
        x, y, reasoning = _minimax_ai(request.board, player)

    return MoveResponse(x=x, y=y, reasoning=reasoning)


@app.post("/api/validate", response_model=ValidateResponse)
async def validate_move(request: ValidateRequest):
    """Validate if a move is legal."""
    if not (0 <= request.x < BOARD_SIZE and 0 <= request.y < BOARD_SIZE):
        return ValidateResponse(valid=False, reason="Out of bounds")
    if request.board[request.y][request.x] != EMPTY:
        return ValidateResponse(valid=False, reason="Position already occupied")
    return ValidateResponse(valid=True)


@app.post("/api/reset")
async def reset_game():
    """Reset the game state."""
    return {"status": "ok", "message": "Game reset successfully"}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9898)
