# backend/app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from llm_engine import chat_with_gold_data
from tools import get_gold_market_data  # 使用优化后的tools.py

# 初始化Flask应用，保留原有静态文件目录配置
app = Flask(__name__, static_folder='../frontend')
CORS(app)  # 保留CORS配置，解决跨域问题


@app.route('/api/chat', methods=['POST'])
def chat_api():
    try:
        # 调试日志（保留原有调试逻辑）
        print("📥 请求头:", dict(request.headers))
        print("📥 原始请求体:", request.get_data(as_text=True))

        # 强制解析JSON（保留原有逻辑）
        data = request.get_json(force=True)

        if not data:
            return jsonify({"reply": "请求体不是有效的 JSON"}), 400

        if 'messages' not in data:
            return jsonify({"reply": "缺少 messages 字段"}), 400

        user_messages = data['messages']
        if not isinstance(user_messages, list):
            return jsonify({"reply": "messages 必须是数组"}), 400

        # 调用LLM引擎（保留原有核心逻辑）
        reply = chat_with_gold_data(user_messages)
        return jsonify({"reply": reply})

    # 保留原有异常处理，优化错误提示
    except ValueError as e:
        print("❌ 数据格式错误:", str(e))
        return jsonify({"reply": f"请求参数错误: {str(e)}"}), 400
    except Exception as e:
        print("❌ 服务器异常:", str(e))
        return jsonify({"reply": f"服务器错误: {str(e)}"}), 500


@app.route('/')
def home():
    # 保留原有静态文件路由，指向frontend目录下的chat.html
    return send_from_directory(app.static_folder, 'chat.html')


@app.route('/manifest.json')
def manifest():
    # 保留PWA相关文件路由
    return send_from_directory('../frontend', 'manifest.json')


@app.route('/sw.js')
def service_worker():
    # 保留Service Worker文件路由
    return send_from_directory('../frontend', 'sw.js')


@app.route('/icon-<path:filename>')
def icons(filename):
    # 保留图标文件路由
    return send_from_directory('../frontend', f'icon-{filename}')


# 新增：单独的金价数据接口（可选，用于前端主动刷新）
@app.route('/api/gold-data', methods=['GET'])
def get_gold_data_api():
    """独立的金价数据接口，便于前端直接获取结构化数据"""
    try:
        gold_data = get_gold_market_data()
        if 'error' in gold_data:
            return jsonify({"error": gold_data['error']}), 500
        return jsonify(gold_data)
    except Exception as e:
        return jsonify({"error": f"获取金价失败: {str(e)}"}), 500


if __name__ == '__main__':
    # 预加载黄金行情数据（保留原有逻辑）
    print("⏳ 预加载黄金行情数据...")
    initial_data = get_gold_market_data()

    # 打印预加载结果，便于调试时效性
    if 'error' in initial_data:
        print(f"❌ 预加载失败: {initial_data['error']}")
    else:
        print(
            f"✅ 预加载成功 | 当前金价: ${initial_data['current_price']} | 数据时间: {initial_data['timestamp']} | 延迟: {initial_data['data_delay_minutes']}分钟")

    # 保留原有端口配置逻辑
    port = int(os.environ.get('PORT', 8000))
    print(f"🚀 服务器启动中... 访问地址: http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)  # 生产环境建议关闭debug