from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class MoveRecord:
    step_id: int
    player: str
    x: int
    y: int
    board_snapshot: List[List[int]]
    reasoning: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class HistoryRecorder:
    def __init__(self) -> None:
        self.records: List[MoveRecord] = []

    def reset(self) -> None:
        self.records = []

    def record_move(
        self,
        player: str,
        x: int,
        y: int,
        board_snapshot: List[List[int]],
        reasoning: Optional[str] = None,
    ) -> MoveRecord:
        record = MoveRecord(
            step_id=len(self.records) + 1,
            player=player,
            x=x,
            y=y,
            board_snapshot=copy.deepcopy(board_snapshot),
            reasoning=reasoning,
        )
        self.records.append(record)
        return record

    def get_history(self) -> List[Dict[str, Any]]:
        return [
            {
                "step_id": r.step_id,
                "player": r.player,
                "x": r.x,
                "y": r.y,
                "reasoning": r.reasoning,
                "timestamp": r.timestamp,
            }
            for r in self.records
        ]

    def get_step(self, step_id: int) -> Optional[MoveRecord]:
        for r in self.records:
            if r.step_id == step_id:
                return r
        return None

    def get_recent_context(self, n: int = 6) -> List[Dict[str, Any]]:
        recent = self.records[-n:]
        return [
            {
                "step_id": r.step_id,
                "player": r.player,
                "x": r.x,
                "y": r.y,
                "reasoning": r.reasoning,
            }
            for r in recent
        ]

    def build_explain_context(self, step_id: int) -> Dict[str, Any]:
        step = self.get_step(step_id)
        if step is None:
            raise ValueError(f"step_id {step_id} not found")

        return {
            "step_id": step.step_id,
            "player": step.player,
            "move": {"x": step.x, "y": step.y},
            "reasoning": step.reasoning,
            "recent_moves": self.get_recent_context(),
            "board_snapshot": step.board_snapshot,
        }

    def build_review_context(self) -> Dict[str, Any]:
        candidate_turning_points = []

        for r in self.records:
            if r.player == "ai" and r.reasoning:
                text = r.reasoning.lower()
                if "block" in text or "win" in text or "threat" in text:
                    candidate_turning_points.append(
                        f"Step {r.step_id}: AI moved at ({r.x}, {r.y}) - {r.reasoning}"
                    )

        return {
            "total_steps": len(self.records),
            "history": self.get_history(),
            "recent_moves": self.get_recent_context(10),
            "candidate_turning_points": candidate_turning_points[:5],
        }