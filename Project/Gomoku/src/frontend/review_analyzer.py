"""Review analyzer: key moments + winrate approximation."""

from __future__ import annotations

from typing import Dict, List
from game import BLACK, WHITE, BOARD_SIZE, EMPTY


class ReviewAnalyzer:
    def __init__(self) -> None:
        self.directions = [(1, 0), (0, 1), (1, 1), (1, -1)]

    def extract_key_moments(self, full_records: List) -> List[Dict]:
        key_moments: List[Dict] = []
        if not full_records:
            return key_moments

        # 使用 eval_score 来识别转折点
        for idx, record in enumerate(full_records):
            prev_score = full_records[idx - 1].eval_score if idx > 0 else 0.0
            curr_score = record.eval_score if record.eval_score is not None else 0.0
            delta = curr_score - prev_score
            
            # 如果评分变化较大，认为是关键时刻
            if abs(delta) >= 10.0 or idx == 0 or idx == len(full_records) - 1:
                key_moments.append(
                    {
                        "step_id": record.step_id,
                        "player": record.player,
                        "move": {"x": record.x, "y": record.y},
                        "delta": round(delta, 2),
                        "reasoning": record.reasoning or "",
                    }
                )
        return key_moments[:8]

    def build_winrate_series(self, full_records: List) -> List[Dict]:
        series: List[Dict] = []
        if not full_records:
            return series

        for record in full_records:
            score = record.eval_score if record.eval_score is not None else 0.0
            winrate_ai = self._score_to_winrate(score)
            series.append(
                {
                    "step": record.step_id,
                    "winrate_ai": round(winrate_ai, 1),
                    "player": record.player,
                }
            )
        return series

    def evaluate_board_for_ai(self, board: List[List[int]]) -> float:
        """评估棋盘，返回 AI 的评分 (-100 to 100)"""
        ai = WHITE
        human = BLACK
        score = 0.0
        center = BOARD_SIZE // 2

        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                piece = board[y][x]
                if piece == EMPTY:
                    continue
                
                local = self._evaluate_piece(board, x, y, piece)
                # 中心控制奖励
                distance = abs(x - center) + abs(y - center)
                center_bonus = max(0, 4 - distance * 0.5)
                
                if piece == ai:
                    score += local + center_bonus
                else:
                    score -= local + center_bonus
                    
        return max(-100.0, min(100.0, score))

    def _evaluate_piece(self, board: List[List[int]], x: int, y: int, player: int) -> float:
        total = 0.0
        for dx, dy in self.directions:
            count = 1
            open_ends = 0

            # 正向探测
            nx, ny = x + dx, y + dy
            while 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[ny][nx] == player:
                count += 1
                nx += dx
                ny += dy
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[ny][nx] == EMPTY:
                open_ends += 1

            # 反向探测
            nx, ny = x - dx, y - dy
            while 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[ny][nx] == player:
                count += 1
                nx -= dx
                ny -= dy
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[ny][nx] == EMPTY:
                open_ends += 1

            # 基于连子数和两端开放情况评分
            if count >= 5:
                total += 100
            elif count == 4:
                total += 80 if open_ends == 2 else 30
            elif count == 3:
                total += 20 if open_ends == 2 else 5
            elif count == 2:
                total += 5 if open_ends == 2 else 1
                
        return total

    @staticmethod
    def _score_to_winrate(score: float) -> float:
        # 将评分映射到胜率 (0-100)
        return max(5.0, min(95.0, 50 + score * 0.45))
