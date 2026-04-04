"""
Tests for Gomoku API endpoints (app.py)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "frontend"))

import pytest
from fastapi.testclient import TestClient

from app import app, _minimax_ai
from game import BLACK, WHITE, EMPTY, BOARD_SIZE

client = TestClient(app)


class TestHealthEndpoint:
    """Test GET /api/health."""

    def test_health_returns_ok(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestRootEndpoint:
    """Test GET / (serves index.html)."""

    def test_root_returns_html(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestMoveEndpoint:
    """Test POST /api/move."""

    def _empty_board(self):
        return [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]

    def test_move_returns_200(self):
        board = self._empty_board()
        response = client.post("/api/move", json={
            "board": board,
            "player": "white"
        })
        assert response.status_code == 200

    def test_move_returns_valid_coordinates(self):
        board = self._empty_board()
        response = client.post("/api/move", json={
            "board": board,
            "player": "white"
        })
        data = response.json()
        assert "x" in data and "y" in data
        assert 0 <= data["x"] < BOARD_SIZE
        assert 0 <= data["y"] < BOARD_SIZE

    def test_move_returns_reasoning(self):
        board = self._empty_board()
        response = client.post("/api/move", json={
            "board": board,
            "player": "white"
        })
        data = response.json()
        assert "reasoning" in data
        assert isinstance(data["reasoning"], str)

    def test_move_board_full_returns_400(self):
        board = [[WHITE] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        response = client.post("/api/move", json={
            "board": board,
            "player": "white"
        })
        assert response.status_code == 400
        assert "full" in response.json()["detail"].lower()

    def test_move_invalid_board_dimensions_returns_400(self):
        board = [[EMPTY] * 10 for _ in range(10)]  # Wrong size
        response = client.post("/api/move", json={
            "board": board,
            "player": "white"
        })
        assert response.status_code == 400

    def test_move_invalid_row_length_returns_400(self):
        board = [[EMPTY] * 16 for _ in range(BOARD_SIZE)]  # Row too long
        response = client.post("/api/move", json={
            "board": board,
            "player": "white"
        })
        assert response.status_code == 400

    def test_move_black_player_uses_white_constant(self):
        board = self._empty_board()
        response = client.post("/api/move", json={
            "board": board,
            "player": "black"
        })
        assert response.status_code == 200


class TestValidateEndpoint:
    """Test POST /api/validate."""

    def _empty_board(self):
        return [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]

    def test_validate_valid_move(self):
        board = self._empty_board()
        response = client.post("/api/validate", json={
            "board": board,
            "x": 0,
            "y": 0
        })
        assert response.status_code == 200
        assert response.json()["valid"] is True

    def test_validate_occupied_position(self):
        board = self._empty_board()
        board[0][0] = BLACK
        response = client.post("/api/validate", json={
            "board": board,
            "x": 0,
            "y": 0
        })
        assert response.status_code == 200
        assert response.json()["valid"] is False
        assert "occupied" in response.json()["reason"].lower()

    def test_validate_out_of_bounds(self):
        board = self._empty_board()
        response = client.post("/api/validate", json={
            "board": board,
            "x": BOARD_SIZE,
            "y": 0
        })
        assert response.status_code == 200
        assert response.json()["valid"] is False
        assert "bounds" in response.json()["reason"].lower()


class TestResetEndpoint:
    """Test POST /api/reset."""

    def test_reset_returns_ok(self):
        response = client.post("/api/reset")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestMinimaxAI:
    """Test the minimax AI helper function."""

    def test_minimax_returns_valid_coords(self):
        board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        x, y, reasoning = _minimax_ai(board, WHITE)
        assert 0 <= x < BOARD_SIZE
        assert 0 <= y < BOARD_SIZE

    def test_minimax_avoids_occupied_positions(self):
        board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        board[7][7] = BLACK
        x, y, _ = _minimax_ai(board, WHITE)
        assert board[y][x] == EMPTY

    def test_minimax_prioritizes_win(self):
        """Place 4 in a row for AI to complete."""
        board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        # White has 4 in a row at y=0
        for x in range(4):
            board[0][x] = WHITE
        x, y, reasoning = _minimax_ai(board, WHITE)
        assert board[y][x] == EMPTY
        # Should place in row y=0 (adjacent to existing line)
        assert y == 0

    def test_minimax_blocks_opponent_win(self):
        """Place 4 in a row for opponent; AI should block."""
        board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        # Black has 4 in a row at y=0
        for x in range(4):
            board[0][x] = BLACK
        x, y, reasoning = _minimax_ai(board, WHITE)
        assert board[y][x] == EMPTY
        # Should block in row y=0
        assert y == 0

    def test_minimax_returns_reasoning(self):
        board = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        _, _, reasoning = _minimax_ai(board, WHITE)
        assert isinstance(reasoning, str)
        assert len(reasoning) > 0
