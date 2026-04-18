import copy
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from game import GomokuGame, BLACK, WHITE, EMPTY, BOARD_SIZE
from llm_client import LLMClient
from history import HistoryRecorder
from rag.retriever import RAGRetriever


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RAG_DIR = BASE_DIR / "rag"
KNOWLEDGE_PATH = RAG_DIR / "knowledge.json"

app = FastAPI(title="Gomoku Current Session API")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass
class CurrentSessionStore:
    game: GomokuGame
    history: HistoryRecorder

    def reset(self) -> None:
        self.game = GomokuGame()
        self.history = HistoryRecorder()


current_session = CurrentSessionStore(
    game=GomokuGame(),
    history=HistoryRecorder(),
)

retriever = RAGRetriever(KNOWLEDGE_PATH)

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


class HealthResponse(BaseModel):
    status: str


class NewGameResponse(BaseModel):
    board: list[list[int]]
    current_player: str
    game_over: bool


class PlayTurnRequest(BaseModel):
    x: int
    y: int


class PlayTurnResponse(BaseModel):
    board: list[list[int]]
    human_move: dict
    ai_move: Optional[dict] = None
    reasoning: Optional[str] = None
    winner: Optional[str] = None
    game_over: bool


class WhyRequest(BaseModel):
    step_id: int
    question: str = "Why did AI move here?"


class WhyResponse(BaseModel):
    explanation: str
    evidence: list[str]
    alternatives: list[str] = []


class ReviewRequest(BaseModel):
    pass


class ReviewResponse(BaseModel):
    summary: str
    turning_points: list[str]
    mistakes: list[str]
    suggestions: list[str]
    evidence: list[str]


class MoveRequest(BaseModel):
    board: list[list[int]]
    player: str


class MoveResponse(BaseModel):
    x: int
    y: int
    reasoning: str


class ValidateRequest(BaseModel):
    board: list[list[int]]
    x: int
    y: int


class ValidateResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None


def winner_to_text(winner: Optional[int]) -> Optional[str]:
    if winner == BLACK:
        return "human"
    if winner == WHITE:
        return "ai"
    return None


def _safe_json_loads(content: str) -> Optional[dict]:
    try:
        return json.loads(content)
    except Exception:
        pass

    try:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(content[start:end + 1])
    except Exception:
        pass
    return None


def llm_explain_move(question: str, step_context: dict, retrieved_chunks: list[dict]) -> dict:
    client = get_llm_client()
    if client.client is None:
        client.connect()

    prompt = f"""
You are a Gomoku explanation assistant.

Question:
{question}

Step context:
{json.dumps(step_context, ensure_ascii=False)}

Retrieved strategy evidence:
{json.dumps(retrieved_chunks, ensure_ascii=False)}

Return JSON only:
{{
  "explanation": "brief explanation",
  "evidence": ["evidence 1", "evidence 2"],
  "alternatives": ["optional alternative move"]
}}
"""

    response = client.client.chat.completions.create(
        model=client.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=350,
    )
    parsed = _safe_json_loads(response.choices[0].message.content)
    if parsed:
        return parsed

    return {
        "explanation": step_context.get("reasoning") or "AI chose this move based on the current board situation.",
        "evidence": [c["text"] for c in retrieved_chunks[:2]],
        "alternatives": [],
    }


def llm_review_game(review_context: dict, retrieved_chunks: list[dict]) -> dict:
    client = get_llm_client()
    if client.client is None:
        client.connect()

    prompt = f"""
You are a Gomoku review assistant.

Game review context:
{json.dumps(review_context, ensure_ascii=False)}

Retrieved strategy evidence:
{json.dumps(retrieved_chunks, ensure_ascii=False)}

Return JSON only:
{{
  "summary": "one sentence summary",
  "turning_points": ["point 1", "point 2"],
  "mistakes": ["mistake 1", "mistake 2"],
  "suggestions": ["suggestion 1", "suggestion 2"],
  "evidence": ["evidence 1", "evidence 2"]
}}
"""

    response = client.client.chat.completions.create(
        model=client.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500,
    )
    parsed = _safe_json_loads(response.choices[0].message.content)
    if parsed:
        return parsed

    return {
        "summary": "This game can be improved by paying more attention to forced threats.",
        "turning_points": review_context.get("candidate_turning_points", [])[:2],
        "mistakes": ["A possible threat was not answered early enough."],
        "suggestions": ["Prioritize blocking immediate threats before expanding attack."],
        "evidence": [c["text"] for c in retrieved_chunks[:2]],
    }


def _evaluate_position(board: list[list[int]], x: int, y: int, player: int) -> int:
    opponent = WHITE if player == BLACK else BLACK
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    score = 0

    for dx, dy in directions:
        my_count = 0
        opp_count = 0

        for step in range(1, 5):
            nx, ny = x + dx * step, y + dy * step
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if board[ny][nx] == player:
                    my_count += 1
                else:
                    break

        for step in range(1, 5):
            nx, ny = x - dx * step, y - dy * step
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if board[ny][nx] == player:
                    my_count += 1
                else:
                    break

        for step in range(1, 5):
            nx, ny = x + dx * step, y + dy * step
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if board[ny][nx] == opponent:
                    opp_count += 1
                else:
                    break

        for step in range(1, 5):
            nx, ny = x - dx * step, y - dy * step
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if board[ny][nx] == opponent:
                    opp_count += 1
                else:
                    break

        if my_count >= 4:
            score += 100000
        elif my_count == 3:
            score += 10000
        elif my_count == 2:
            score += 1000
        elif my_count == 1:
            score += 100

        if opp_count >= 4:
            score += 50000
        elif opp_count == 3:
            score += 5000
        elif opp_count == 2:
            score += 500

    return score


def _minimax_ai(board: list[list[int]], player: int) -> tuple[int, int, str]:
    best_score = -1
    best_moves = []

    candidates = set()
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            if board[y][x] != EMPTY:
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[ny][nx] == EMPTY:
                            candidates.add((nx, ny))

    if not candidates:
        candidates.add((7, 7))

    for x, y in candidates:
        score = _evaluate_position(board, x, y, player)
        if score > best_score:
            best_score = score
            best_moves = [(x, y)]
        elif score == best_score:
            best_moves.append((x, y))

    x, y = random.choice(best_moves)

    if best_score >= 50000:
        reasoning = f"Move ({x}, {y}) blocks a major threat or creates a winning line."
    elif best_score >= 10000:
        reasoning = f"Move ({x}, {y}) strengthens an immediate tactical sequence."
    elif best_score >= 1000:
        reasoning = f"Move ({x}, {y}) improves local attack or defense."
    else:
        reasoning = f"Move ({x}, {y}) is chosen by heuristic evaluation."

    return x, y, reasoning


@app.get("/")
async def root():
    if (STATIC_DIR / "index.html").exists():
        return FileResponse(STATIC_DIR / "index.html")
    raise HTTPException(status_code=404, detail="index.html not found")


@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@app.post("/api/new-game", response_model=NewGameResponse)
async def new_game():
    current_session.reset()
    return NewGameResponse(
        board=current_session.game.board,
        current_player="black",
        game_over=False,
    )


@app.post("/api/play-turn", response_model=PlayTurnResponse)
async def play_turn(request: PlayTurnRequest):
    game = current_session.game
    history = current_session.history

    if game.game_over:
        raise HTTPException(status_code=400, detail="current game is already over")

    if not game.is_valid_move(request.x, request.y):
        raise HTTPException(status_code=400, detail="invalid human move")

    game.make_move(request.x, request.y)
    human_record = history.record_move(
        player="human",
        x=request.x,
        y=request.y,
        board_snapshot=game.board,
        reasoning=None,
    )

    if game.game_over:
        return PlayTurnResponse(
            board=game.board,
            human_move={"x": request.x, "y": request.y, "step_id": human_record.step_id},
            ai_move=None,
            reasoning=None,
            winner=winner_to_text(game.winner),
            game_over=True,
        )

    try:
        ai_result = get_llm_client().generate_move(game.board, "white")
        ai_x = int(ai_result.get("x", 7))
        ai_y = int(ai_result.get("y", 7))
        ai_reasoning = str(ai_result.get("reasoning", ""))
    except Exception:
        ai_x, ai_y, ai_reasoning = _minimax_ai(game.board, WHITE)

    if not game.is_valid_move(ai_x, ai_y):
        ai_x, ai_y, ai_reasoning = _minimax_ai(game.board, WHITE)

    game.make_move(ai_x, ai_y)
    ai_record = history.record_move(
        player="ai",
        x=ai_x,
        y=ai_y,
        board_snapshot=game.board,
        reasoning=ai_reasoning,
    )

    return PlayTurnResponse(
        board=game.board,
        human_move={"x": request.x, "y": request.y, "step_id": human_record.step_id},
        ai_move={"x": ai_x, "y": ai_y, "step_id": ai_record.step_id},
        reasoning=ai_reasoning,
        winner=winner_to_text(game.winner),
        game_over=game.game_over,
    )


@app.post("/api/why", response_model=WhyResponse)
async def why_move(request: WhyRequest):
    history = current_session.history

    try:
        step_context = history.build_explain_context(request.step_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    query = f"{request.question} {step_context.get('reasoning', '')} defense threat center review"
    chunks = retriever.retrieve(query, top_k=3)

    try:
        result = llm_explain_move(
            question=request.question,
            step_context=step_context,
            retrieved_chunks=chunks,
        )
    except Exception:
        result = {
            "explanation": step_context.get("reasoning") or "AI chose this move based on the current board situation.",
            "evidence": [c["text"] for c in chunks[:2]],
            "alternatives": [],
        }

    if "evidence" not in result:
        result["evidence"] = [c["text"] for c in chunks[:2]]
    if "alternatives" not in result:
        result["alternatives"] = []

    return WhyResponse(**result)


@app.post("/api/review", response_model=ReviewResponse)
async def review_game(_: ReviewRequest):
    game = current_session.game
    history = current_session.history

    review_context = history.build_review_context()
    review_context["winner"] = winner_to_text(game.winner)
    review_context["game_over"] = game.game_over

    chunks = retriever.retrieve("review mistakes turning points defense threat", top_k=4)

    try:
        result = llm_review_game(
            review_context=review_context,
            retrieved_chunks=chunks,
        )
    except Exception:
        result = {
            "summary": "This game can be improved by paying more attention to forced threats.",
            "turning_points": review_context.get("candidate_turning_points", [])[:2],
            "mistakes": ["A possible threat was not answered early enough."],
            "suggestions": ["Prioritize blocking immediate threats before expanding attack."],
            "evidence": [c["text"] for c in chunks[:2]],
        }

    if "turning_points" not in result:
        result["turning_points"] = review_context.get("candidate_turning_points", [])[:2]
    if "mistakes" not in result:
        result["mistakes"] = []
    if "suggestions" not in result:
        result["suggestions"] = []
    if "evidence" not in result:
        result["evidence"] = [c["text"] for c in chunks[:2]]

    return ReviewResponse(**result)


@app.get("/api/history")
async def get_history():
    return {"history": current_session.history.get_history()}


@app.post("/api/move", response_model=MoveResponse)
async def make_move(request: MoveRequest):
    board = request.board
    player_str = request.player.lower()
    player = BLACK if player_str == "black" else WHITE

    try:
        result = get_llm_client().generate_move(board, player_str)
        x, y = int(result["x"]), int(result["y"])
        reasoning = str(result.get("reasoning", ""))
    except Exception:
        x, y, reasoning = _minimax_ai(board, player)

    if board[y][x] != EMPTY:
        x, y, reasoning = _minimax_ai(board, player)

    return MoveResponse(x=x, y=y, reasoning=reasoning)


@app.post("/api/validate", response_model=ValidateResponse)
async def validate_move(request: ValidateRequest):
    game = GomokuGame(board=copy.deepcopy(request.board))
    if not (0 <= request.x < BOARD_SIZE and 0 <= request.y < BOARD_SIZE):
        return ValidateResponse(valid=False, reason="Out of bounds")
    if request.board[request.y][request.x] != EMPTY:
        return ValidateResponse(valid=False, reason="Cell is already occupied")
    if game.game_over:
        return ValidateResponse(valid=False, reason="Game is already over")
    return ValidateResponse(valid=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)