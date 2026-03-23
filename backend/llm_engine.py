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
    """使用 OpenAI 兼容模式调用火山引擎，增强金价数据容错"""
    # 定义工具描述（保留原有结构）
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_gold_market_data",
                "description": "获取国际黄金(XAU/USD)的实时市场数据，包含当前价格、24小时高低点、RSI、MACD等技术指标。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    ]

    try:
        # 第一次调用：尝试触发工具（保留原有OpenAI兼容逻辑）
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=300,
            temperature=0.1
        )

        response_message = response.choices[0].message

        # 检查是否需要调用工具（核心逻辑保留）
        if hasattr(response_message, 'tool_calls') and response_message.tool_calls:
            tool_call = response_message.tool_calls[0]
            if tool_call.function.name == "get_gold_market_data":
                # 导入并调用金价工具（增强异常处理）
                from tools import get_gold_market_data
                data = get_gold_market_data()  # ✅ 每次都实时获取！

                # ========== 核心优化：处理金价数据异常 ==========
                if "error" in data:
                    # 构建友好的错误响应，替代原始错误码
                    error_msg = data["error"]
                    # 分类提示不同错误类型
                    if "Too many requests" in error_msg:
                        friendly_error = f"⚠️ 金价接口调用频率超限（Twelve Data免费版限制）\n请1分钟后再试，或升级API套餐提升限额。"
                    elif "网络请求" in error_msg:
                        friendly_error = f"⚠️ 网络异常，无法连接金价服务器\n请检查网络或稍后重试。"
                    elif "解析异常" in error_msg:
                        friendly_error = f"⚠️ 金价数据格式异常，接口返回非标准数据\n建议检查API密钥有效性。"
                    else:
                        friendly_error = f"⚠️ 获取实时金价失败：{error_msg}\n请稍后重试。"

                    # 构建带错误提示的工具响应（保持JSON格式）
                    tool_response_message = {
                        "role": "tool",
                        "content": json.dumps({
                            "error": True,
                            "message": friendly_error,
                            "raw_error": error_msg
                        }, ensure_ascii=False),
                        "tool_call_id": tool_call.id
                    }
                else:
                    # 数据正常时，构建原始工具响应（保留所有字段）
                    tool_response_message = {
                        "role": "tool",
                        "content": json.dumps(data, ensure_ascii=False),
                        "tool_call_id": tool_call.id
                    }

                # 继续对话（保留原有逻辑）
                new_messages = messages + [response_message, tool_response_message]
                final_response = client.chat.completions.create(
                    model=MODEL,
                    messages=new_messages,
                    max_tokens=500,
                    temperature=0.1
                )
                return final_response.choices[0].message.content or "分析完成。"

        # 无工具调用时的默认响应（保留）
        return response_message.content or "我暂时无法回答，请稍后再试。"

    # ========== 增强全局异常处理 ==========
    except ImportError as e:
        return f"异常: 工具模块导入失败 - {str(e)}"
    except KeyError as e:
        return f"异常: 响应数据格式错误 - 缺失字段 {str(e)}"
    except Exception as e:
        return f"异常: {str(e)}"