"""
LLM Client for Gomoku AI
Handles communication with vLLM backend (OpenAI-compatible).
Default: LLM_API_URL=http://localhost:8000/v1, LLM_MODEL=/root/.cache/huggingface/Qwen3-4B-quantized.w4a16
"""

import os
import json
import re
from typing import Optional, Dict, Any
from openai import OpenAI


class LLMClient:
    """Client for communicating with LLM backend"""

    def __init__(self, api_url: Optional[str] = None, model: Optional[str] = None):
        self.api_url = api_url or os.getenv("LLM_API_URL", "http://localhost:8000/v1")
        self.model = model or os.getenv("LLM_MODEL", "/root/.cache/huggingface/Qwen3-4B-quantized.w4a16")
        self.client = None

    def connect(self):
        """Initialize the OpenAI client"""
        self.client = OpenAI(
            base_url=self.api_url,
            api_key="dummy"  # Local vLLM doesn't need real key
        )

    def generate_move(self, board: list[list[int]], player: str) -> Dict[str, Any]:
        """
        Generate an AI move based on current board state

        Args:
            board: 2D list representing the board (0=empty, 1=black, 2=white)
            player: Current player ("black" or "white")

        Returns:
            Dict with x, y coordinates and reasoning
        """
        if self.client is None:
            self.connect()

        prompt = self._build_prompt(board, player)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150
        )

        return self._parse_response(response.choices[0].message.content)

    def _build_prompt(self, board: list[list[int]], player: str) -> str:
        """Build the prompt for the LLM"""
        board_str = "\n".join([str(row) for row in board])
        ai_color = "白棋" if player == "white" else "黑棋"

        return f"""你是一个五子棋 AI。请分析当前棋局并给出最佳落子位置。

当前棋盘状态 (0=空, 1=黑棋, 2=白棋):
黑棋先手，你执{ai_color}。

棋盘:
{board_str}

你必须用以下 JSON 格式回复，不能有其他内容：
{{"x": 整数(0-14), "y": 整数(0-14), "reasoning": "你的思考过程(10字以内)"}}

注意：
1. 只回复 JSON，不要有其他文字
2. x 是列索引(左到右0-14)，y 是行索引(上到下0-14)
3. 选择对自己最有利的落子点
4. 确保选择的位置是空位"""

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse the LLM response to extract move coordinates"""
        # Try to extract JSON from the response
        try:
            # Try direct JSON parsing
            data = json.loads(content)
            return {
                "x": int(data.get("x", 7)),
                "y": int(data.get("y", 7)),
                "reasoning": str(data.get("reasoning", ""))
            }
        except json.JSONDecodeError:
            pass

        # Try regex extraction
        match = re.search(r'"x"\s*:\s*(\d+)', content)
        y_match = re.search(r'"y"\s*:\s*(\d+)', content)

        if match and y_match:
            return {
                "x": int(match.group(1)),
                "y": int(y_match.group(1)),
                "reasoning": "Parsed from response"
            }

        # Default fallback
        return {
            "x": 7,
            "y": 7,
            "reasoning": "Default fallback"
        }


# Global client instance
llm_client = LLMClient()
