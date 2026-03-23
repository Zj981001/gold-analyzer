# backend/app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from llm_engine import chat_with_gold_data
from tools import get_gold_market_data  # 现在调用的是无递归的正确函数

app = Flask(__name__, static_folder='../frontend')
CORS(app)


@app.route('/api/chat', methods=['POST'])
def chat_api():
    try:
        print("📥 请求头:", dict(request.headers))
        print("📥 原始请求体:", request.get_data(as_text=True))

        data = request.get_json(force=True)

        if not data:
            return jsonify({"reply": "请求体不是有效的 JSON"}), 400

        if 'messages' not in data:
            return jsonify({"reply": "缺少 messages 字段"}), 400

        user_messages = data['messages']
        if not isinstance(user_messages, list):
            return jsonify({"reply": "messages 必须是数组"}), 400

        reply = chat_with_gold_data(user_messages)
        return jsonify({"reply": reply})

    except ValueError as e:
        print("❌ 数据格式错误:", str(e))
        return jsonify({"reply": f"请求参数错误: {str(e)}"}), 400
    except Exception as e:
        print("❌ 服务器异常:", str(e))
        return jsonify({"reply": f"服务器错误: {str(e)}"}), 500


@app.route('/')
def home():
    return send_from_directory(app.static_folder, 'chat.html')


@app.route('/manifest.json')
def manifest():
    return send_from_directory('../frontend', 'manifest.json')


@app.route('/sw.js')
def service_worker():
    return send_from_directory('../frontend', 'sw.js')


@app.route('/icon-<path:filename>')
def icons(filename):
    return send_from_directory('../frontend', f'icon-{filename}')


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
    print("⏳ 预加载黄金行情数据...")
    initial_data = get_gold_market_data()

    if 'error' in initial_data:
        print(f"❌ 预加载失败: {initial_data['error']}")
    else:
        print(
            f"✅ 预加载成功 | 当前金价: ${initial_data['current_price']} | 数据时间: {initial_data['timestamp']} | 延迟: {initial_data['data_delay_minutes']}分钟")

    port = int(os.environ.get('PORT', 8000))
    print(f"🚀 服务器启动中... 访问地址: http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)