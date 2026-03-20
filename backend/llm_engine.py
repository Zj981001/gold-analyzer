# backend/llm_engine.py
import os
import json
from openai import OpenAI

# 初始化 OpenAI 客户端（兼容火山引擎）
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.getenv("ARK_API_KEY")
)

MODEL = os.getenv("VOLC_MODEL", "ep-20260320085554-f72dc")


def chat_with_gold_data(messages):
    """使用 OpenAI 兼容模式调用火山引擎"""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_gold_market_data",
                "description": "获取国际黄金(XAU/USD)的实时市场数据...",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    ]

    try:
        # 第一次调用：尝试触发工具
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",  # ✅ OpenAI 支持 auto
            max_tokens=300,
            temperature=0.1
        )

        response_message = response.choices[0].message

        # 检查是否需要调用工具
        if response_message.tool_calls:
            tool_call = response_message.tool_calls[0]
            if tool_call.function.name == "get_gold_market_data":
                from tools import get_gold_market_data
                data = get_gold_market_data()

                # 构建工具响应
                tool_response_message = {
                    "role": "tool",
                    "content": json.dumps(data, ensure_ascii=False),
                    "tool_call_id": tool_call.id
                }

                # 继续对话
                new_messages = messages + [response_message, tool_response_message]
                final_response = client.chat.completions.create(
                    model=MODEL,
                    messages=new_messages,
                    max_tokens=500,
                    temperature=0.1
                )
                return final_response.choices[0].message.content or "分析完成。"

        return response_message.content or "我暂时无法回答，请稍后再试。"

    except Exception as e:
        return f"异常: {str(e)}"
