"""
LLM Client for Gomoku AI
Handles communication with vLLM backend (OpenAI-compatible).
Default: LLM_API_URL=http://localhost:8000/v1, LLM_MODEL=/root/.cache/huggingface/Qwen3-4B-quantized.w4a16
"""

import os
import json
import re
from typing import Optional, Dict, Any, List
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
            api_key="dummy"
        )

    def generate_move(self, board: list[list[int]], player: str) -> Dict[str, Any]:
        if self.client is None:
            self.connect()

        prompt = self._build_prompt(board, player)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150
        )

        return self._parse_move_response(response.choices[0].message.content)

    def generate_review(self, review_context: Dict[str, Any], retrieved_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self.client is None:
            self.connect()

        prompt = f"""你是一名五子棋复盘助手。

请根据以下复盘上下文与策略依据，输出结构化复盘结果。

复盘上下文：
{json.dumps(review_context, ensure_ascii=False)}

检索到的策略依据：
{json.dumps(retrieved_chunks, ensure_ascii=False)}

你必须只输出 JSON：
{{
  "summary": "一句话总结",
  "turning_points": ["转折点1", "转折点2"],
  "mistakes": ["失误1", "失误2"],
  "suggestions": ["建议1", "建议2"],
  "evidence": ["依据1", "依据2"]
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=500
        )

        return self._parse_json_response(response.choices[0].message.content, {
            "summary": "This game can be improved by paying more attention to forced threats.",
            "turning_points": [],
            "mistakes": [],
            "suggestions": [],
            "evidence": [c["text"] for c in retrieved_chunks[:2]]
        })

    def generate_personality_test(self, review_result: Dict[str, Any], retrieved_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self.client is None:
            self.connect()

        prompt = f"""你是“五子棋下棋人格测试”生成助手。

你必须严格遵守以下规则：
1. 只输出一个 JSON 对象
2. 不要输出任何分析过程
3. 不要输出“好的”“首先”“根据”等解释性文字
4. 不要输出 Markdown
5. 不要输出代码块
6. 如果信息不足，也必须输出合法 JSON

复盘结果：
{json.dumps(review_result, ensure_ascii=False)}

检索到的人格/棋风知识：
{json.dumps(retrieved_chunks, ensure_ascii=False)}

输出格式必须严格为：
{{
  "personality_type": "稳健防守型 / 激进进攻型 / 均衡理性型 / 机会主义型 / 冲动冒险型 / 慢热成长型",
  "title": "一个简短的人格称号",
  "description": "2-3句的人格描述",
  "strengths": ["优势1", "优势2"],
  "risks": ["风险1", "风险2"],
  "advice": ["建议1", "建议2"],
  "fun_comment": "一句轻松的点评"
}}

现在直接输出 JSON，不要输出其他内容。
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=700
        )

        content = response.choices[0].message.content
        print("=== personality raw content ===")
        print(content)

        return self._parse_json_response(response.choices[0].message.content, {
            "personality_type": "待进一步分析",
            "title": "棋风观察中",
            "description": "当前模型输出格式异常，因此暂时给出一份基础棋风画像。",
            "strengths": ["具备一定局面理解能力"],
            "risks": ["暂时无法稳定识别主要风格特征"],
            "advice": ["建议继续完成更多对局以获得更稳定的画像"],
            "fun_comment": "你的棋风还在云雾中，继续下几盘让它更清晰。"
        })

    def _build_prompt(self, board: list[list[int]], player: str) -> str:
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

    def _parse_move_response(self, content: str) -> Dict[str, Any]:
        try:
            data = json.loads(content)
            return {
                "x": int(data.get("x", 7)),
                "y": int(data.get("y", 7)),
                "reasoning": str(data.get("reasoning", ""))
            }
        except json.JSONDecodeError:
            pass

        match = re.search(r'"x"\s*:\s*(\d+)', content)
        y_match = re.search(r'"y"\s*:\s*(\d+)', content)

        if match and y_match:
            return {
                "x": int(match.group(1)),
                "y": int(y_match.group(1)),
                "reasoning": "Parsed from response"
            }

        return {
            "x": 7,
            "y": 7,
            "reasoning": "Default fallback"
        }

    def _parse_json_response(self, content: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
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

        return fallback


llm_client = LLMClient()