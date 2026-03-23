# backend/app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS  # 👈 新增 CORS
import os
from llm_engine import chat_with_gold_data
from tools import get_gold_market_data

app = Flask(__name__, static_folder='../frontend')
CORS(app)  # 👈 启用 CORS


@app.route('/api/chat', methods=['POST'])
def chat_api():
    try:
        # 调试日志（部署时可保留）
        print("📥 请求头:", dict(request.headers))
        print("📥 原始请求体:", request.get_data(as_text=True))

        data = request.get_json(force=True)  # 👈 强制解析 JSON

        if not data:
            return jsonify({"reply": "请求体不是有效的 JSON"}), 400

        if 'messages' not in data:
            return jsonify({"reply": "缺少 messages 字段"}), 400

        user_messages = data['messages']
        if not isinstance(user_messages, list):
            return jsonify({"reply": "messages 必须是数组"}), 400

        reply = chat_with_gold_data(user_messages)
        return jsonify({"reply": reply})
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


if __name__ == '__main__':
    print("⏳ 预加载黄金行情数据...")
    get_gold_market_data()

    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)