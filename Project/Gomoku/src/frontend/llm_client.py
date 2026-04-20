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


def safe_json_loads(content: str) -> Optional[dict]:
    try:
        return json.loads(content)
    except Exception:
        pass

    try:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(content[start : end + 1])
    except Exception:
        pass
    return None


class LLMClient:
    """Client for communicating with LLM backend"""

    def __init__(self, api_url: Optional[str] = None, model: Optional[str] = None):
        self.api_url = api_url or os.getenv("LLM_API_URL", "http://localhost:8000/v1")
        self.model = model or os.getenv(
            "LLM_MODEL", "/root/.cache/huggingface/Qwen3-4B-quantized.w4a16"
        )
        self.client = None

    def connect(self):
        """Initialize the OpenAI client"""
        self.client = OpenAI(
            base_url=self.api_url, api_key="dummy"  # Local vLLM doesn't need real key
        )

    # 使用 deepseek 测试
    # def __init__(self, api_url: Optional[str] = None, model: Optional[str] = None):
    #     # DeepSeek API地址
    #     self.api_url = api_url or os.getenv(
    #         "LLM_API_URL", "https://api.deepseek.com/v1"
    #     )

    #     # DeepSeek模型名
    #     self.model = model or os.getenv("LLM_MODEL", "deepseek-chat")

    #     self.client = None

    # def connect(self):
    #     """Initialize DeepSeek client"""
    #     self.client = OpenAI(
    #         base_url=self.api_url,
    #         api_key="KEY",
    #     )

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
            max_tokens=150,
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
                "reasoning": str(data.get("reasoning", "")),
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
                "reasoning": "Parsed from response",
            }

        # Default fallback
        return {"x": 7, "y": 7, "reasoning": "Default fallback"}

    # 很冗长的prompt，并且输出不是特别稳定，是否有更优解？
    def generate_move_top3(self, question, board, current_player, chunks):
        if self.client is None:
            self.connect()
        context = "\n".join([c["text"] for c in chunks])
        board_str = "\n".join([" ".join(map(str, row)) for row in board])
        prompt = f"""
你是五子棋AI（黑=1，白=2）

棋盘：
{board_str}

任务：
结合RAG知识库{context}给出“最多3个合法落子”

规则（必须遵守）：

1. 防守点必须在对手连子的延长线上
2. 连子必须：
   - 同色
   - 连续（等差斜线如(1,1)(2,2)(3,3)/横线/竖线）

3. 如果无法找到3个合法点：
    只输出合法点（可以少于3个）

4. 禁止：（违反则删除该点并重新找）
- 使用白棋参与黑棋连子
- 使用黑棋参与白棋连子
- 不共线连子
- 不连续连子
- 编造连子


【斜线判断（必须执行）】

当声称“斜向连子”时，必须满足：

- 所有点满足：|Δrow| == |Δcol|
- 且步长一致（等差）
- 且连续（不能跳格）

示例（合法）：
(4,6)(5,5)(6,4)

验证：
(5-4,5-6)= (1,-1)
(6-5,4-5)= (1,-1) 

示例（非法）：
(4,6)(5,7)(7,5) （不等差/不连续）

若不满足以上条件：
必须判定为“非斜线”，该落子无效，删掉重新找

------------------------
【坐标合法性强制规则（最高优先级）】
------------------------

在生成每个落子点的 reason 时：

如果出现以下任一情况：

1. 所列坐标不共线
2. 所列坐标不连续（存在跳格）
3. 使用了对手棋子参与己方连子
4. reason 中出现“错误说明”（例如：不连续、错误、应为等）

必须执行：

- 立即判定该落子无效
- 删除该落子
- 重新选择新的落子
- 重新生成 reason

禁止：
- 输出包含错误坐标的解释
- 输出“虽然不对但是…”这种补救说明
- 在最终结果中保留任何错误分析

最终输出中：
所有坐标必须完全正确，且无需解释其正确性

------------------------
【reason结构（必须严格按此格式）】
------------------------

每个落子必须包含三个部分（缺一不可）：

① 防守价值（必须有）
- 明确说明是否阻挡对手哪一条连子
- 必须写出对手连子坐标 + 被堵的位置

② 进攻价值（必须有）
- 必须说明与己方哪些棋子形成连子
- 必须写出完整连子坐标
- 必须说明“最长连子”（如三连 > 二连）

③ 优先级理由（必须有）
- 说明为什么它排在当前这个位置（第1 / 第2 / 第3）
- 必须和其他点做对比（例如：比另一个点更优/更弱）

------------------------

示例（必须接近这种结构）：

“先堵住白棋(6,5)(6,6)(6,7)向(6,4)的延长线，不然下一步就会被冲四。同时，这一步还能和黑棋(4,6)(5,5)连成一条斜向三连，是当前唯一的攻防兼备点，因此优先级最高。”

------------------------

禁止：

- 只写防守不写进攻
- 不写坐标
- 不说明为什么排第几
- 三个点理由结构完全一样


------------------------
【输出格式（严格）】
------------------------

格式：
{{
  "top3": [
    {{
      "move": [row, col],
      "reason": "基于真实棋盘的解释"
    }}
  ]
}}

"""

        # ===== 调 LLM =====
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        content = safe_json_loads(response.choices[0].message.content)

        print("LLM RAW OUTPUT:", content)

        # ===== 解析 JSON =====
        if content:
            try:
                return content
            except:
                # fallback
                return {
                    "top3": [
                        {"move": [7, 7], "reason": "默认中心位置（fallback）"},
                        {"move": [6, 7], "reason": "局部扩展（fallback）"},
                        {"move": [8, 7], "reason": "平衡布局（fallback）"},
                    ]
                }

    def generate_qa_answer(self, question, chunks):
        context = "\n".join([c["text"] for c in chunks])

        prompt = f"""
你是一个五子棋讲解助手。

以下是参考知识：
{context}

用户问题：{question}

请直接回答这个问题。

要求：
1. 只输出最终答案
2. 不要重复题目或提示词
3. 不要输出“你是一个…”之类内容
4. 用简洁自然语言解释

答案：
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        answer = safe_json_loads(response.choices[0].message.content)

        return answer


# Global client instance
llm_client = LLMClient()
