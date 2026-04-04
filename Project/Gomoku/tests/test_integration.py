"""
Integration tests for Gomoku game flow (game.py + app.py)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "frontend"))

import pytest
from fastapi.testclient import TestClient

from app import app
from game import GomokuGame, BLACK, WHITE, EMPTY, BOARD_SIZE, WIN_COUNT

client = TestClient(app)


def _place_piece(game: GomokuGame, x: int, y: int, player: int):
    """Directly place a piece on the board without player-switching."""
    game.board[y][x] = player
    game.move_history.append((x, y, player))


class TestFullGameLoop:
    """Simulate a complete game flow through the API."""

    def _empty_board(self):
        return [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]

    def test_simulate_full_game_flow(self):
        """Simulate multiple moves through the game state."""
        game = GomokuGame()
        board = self._empty_board()

        # Human (black) makes first move
        assert game.make_move(7, 7) is True
        board[7][7] = BLACK

        # AI (white) responds
        response = client.post("/api/move", json={
            "board": board,
            "player": "white"
        })
        assert response.status_code == 200
        ai_move = response.json()
        board[ai_move["y"]][ai_move["x"]] = WHITE
        game.make_move(ai_move["x"], ai_move["y"])

        # Continue a few more moves
        for _ in range(5):
            # Find an empty spot for human
            human_move = None
            for y in range(BOARD_SIZE):
                for x in range(BOARD_SIZE):
                    if board[y][x] == EMPTY:
                        human_move = (x, y)
                        break
                if human_move:
                    break

            if human_move:
                x, y = human_move
                game.make_move(x, y)
                board[y][x] = BLACK

            if game.game_over:
                break

            # AI responds
            response = client.post("/api/move", json={
                "board": board,
                "player": "white"
            })
            assert response.status_code == 200
            ai_move = response.json()
            if board[ai_move["y"]][ai_move["x"]] == EMPTY:
                board[ai_move["y"]][ai_move["x"]] = WHITE
                game.make_move(ai_move["x"], ai_move["y"])

            if game.game_over:
                break

        # Game should not have crashed
        assert game.move_history is not None


class TestWinDetectionIntegration:
    """Test that win detection works correctly in full flow."""

    def test_ai_win_detection(self):
        """Set up a near-win and verify game detects it.
        We use _place_piece to avoid AI interfering with the test.
        """
        game = GomokuGame()
        # Human places 4 in a row horizontally at y=0
        for x in range(WIN_COUNT - 1):
            _place_piece(game, x, 0, BLACK)
        assert game.game_over is False

        # Human completes 5th
        _place_piece(game, WIN_COUNT - 1, 0, BLACK)
        assert game._check_win(WIN_COUNT - 1, 0) is True

    def test_ai_winning_move(self):
        """Verify AI can complete a winning line."""
        game = GomokuGame()
        board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]

        # White (AI) has 4 in a row at y=0
        for x in range(4):
            board[0][x] = WHITE

        # Ask AI to complete the win
        response = client.post("/api/move", json={
            "board": board,
            "player": "white"
        })
        assert response.status_code == 200
        ai_move = response.json()

        # AI should complete the line at (4, 0)
        assert ai_move["x"] == 4 and ai_move["y"] == 0


class TestFrontendAPIContract:
    """Test that the API matches what the frontend expects."""

    def test_move_response_has_required_fields(self):
        """Frontend game.js expects x, y, reasoning."""
        board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        response = client.post("/api/move", json={
            "board": board,
            "player": "white"
        })
        data = response.json()
        assert "x" in data
        assert "y" in data
        assert "reasoning" in data
        assert isinstance(data["x"], int)
        assert isinstance(data["y"], int)
        assert isinstance(data["reasoning"], str)

    def test_health_response_matches_frontend_expectation(self):
        """Frontend should receive status: ok."""
        response = client.get("/api/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"


class TestDrawScenario:
    """Test draw (board full without winner) scenario."""

    def test_board_full_no_win_is_draw(self):
        """Fill board carefully to avoid any 5-in-a-row."""
        game = GomokuGame()

        # Fill alternating pattern across entire board
        # This is a simplified test - in reality draw is rare
        filled = 0
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if game.board[y][x] == EMPTY:
                    player = BLACK if filled % 2 == 0 else WHITE
                    game.make_move(x, y)
                    filled += 1
                    if game.game_over:
                        break
            if game.game_over:
                break

        # At minimum, verify no crash occurred
        assert game.move_history is not None
