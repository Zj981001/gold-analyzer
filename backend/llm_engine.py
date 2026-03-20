# backend/llm_engine.py
import os
import json
from dashscope import Generation

API_KEY = os.getenv("ARK_API_KEY")
MODEL = os.getenv("VOLC_MODEL", "ep-20260320085554-f72dc")


def chat_with_gold_data(messages):
    """使用 DashScope 调用火山引擎大模型（正确工具调用格式）"""
    # ✅ 正确的 DashScope 工具格式
    tools = [
        {
            "name": "get_gold_market_data",
            "description": "获取国际黄金(XAU/USD)的实时市场数据，包括价格、RSI、MACD等技术指标",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    ]

    try:
        response = Generation.call(
            model=MODEL,
            api_key=API_KEY,
            messages=messages,
            tools=tools,  # ✅ 直接传 tools 列表
            tool_choice="auto",
            result_format='message',
            max_tokens=300,
            temperature=0.1
        )

        if response.status_code == 200:
            message = response.output.choices[0].message

            # 检查是否需要调用工具
            if 'tool_calls' in message and message['tool_calls']:
                tool_call = message['tool_calls'][0]
                if tool_call['function']['name'] == "get_gold_market_data":
                    from tools import get_gold_market_data
                    data = get_gold_market_data()

                    # 构建工具响应（DashScope 要求 role="tool"）
                    tool_response_message = {
                        "role": "tool",
                        "content": json.dumps(data, ensure_ascii=False),
                        "tool_call_id": tool_call['id']
                    }

                    # 继续对话
                    new_messages = messages + [message, tool_response_message]
                    final_response = Generation.call(
                        model=MODEL,
                        api_key=API_KEY,
                        messages=new_messages,
                        result_format='message',
                        max_tokens=500,
                        temperature=0.1
                    )
                    if final_response.status_code == 200:
                        final_msg = final_response.output.choices[0].message
                        return final_msg.get('content', '分析完成。')
                    else:
                        return f"二次调用失败: {final_response.code} - {final_response.message}"

            return message.get('content', '我暂时无法回答，请稍后再试。')
        else:
            return f"DashScope 调用失败: {response.code} - {response.message}"

    except Exception as e:
        return f"异常: {str(e)}"
