# backend/llm_engine.py
import os
import sys

sys.path.append(os.path.dirname(__file__))
from openai import OpenAI
import json

# 从环境变量读取配置（注意：变量名是 'ARK_API_KEY'）
API_KEY = os.getenv("ARK_API_KEY")
MODEL = os.getenv("VOLC_MODEL", "ep-20260320085554-f72dc")

# 初始化 OpenAI 兼容客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=API_KEY,
)


def chat_with_gold_data(messages):
    """使用火山引擎大模型进行带工具调用的对话"""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_gold_market_data",
                "description": "获取国际黄金(XAU/USD)的实时市场数据，包括价格、RSI、MACD等技术指标",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    ]

    try:
        # 第一次调用：看是否需要工具
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=300,  # 👈 从500降到300
            temperature=0.1,
            timeout=10  # 👈 显式设置超时
        )

        message = response.choices[0].message

        # 检查是否需要调用工具
        if hasattr(message, 'tool_calls') and message.tool_calls:
            tool_call = message.tool_calls[0]
            if tool_call.function.name == "get_gold_market_data":
                from tools import get_gold_market_data
                data = get_gold_market_data()

                # 构建工具响应
                tool_response_message = {
                    "role": "tool",
                    "content": json.dumps(data, ensure_ascii=False),
                    "tool_call_id": tool_call.id
                }

                # 将工具结果加入对话历史
                new_messages = messages + [message.to_dict(), tool_response_message]

                # 第二次调用：生成最终回答
                final_response = client.chat.completions.create(
                    model=MODEL,
                    messages=new_messages,
                    tools=tools,
                    max_tokens=500,
                    temperature=0.1
                )
                final_message = final_response.choices[0].message
                return final_message.content or "分析完成，但无内容返回。"

        # 无需工具调用
        return message.content or "我暂时无法回答，请稍后再试。"

    except Exception as e:
        return f"火山引擎调用失败: {str(e)}"
