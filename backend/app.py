# backend/app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS  # 👈 新增：CORS 支持
import os
from llm_engine import chat_with_gold_data
from tools import get_gold_market_data

app = Flask(__name__, static_folder='../frontend')
CORS(app)  # 👈 启用 CORS，允许前端跨域请求


@app.route('/api/chat', methods=['POST'])
def chat_api():
    try:
        data = request.json
        if not data or 'messages' not in data:
            return jsonify({"reply": "无效请求"}), 400

        user_messages = data['messages']
        reply = chat_with_gold_data(user_messages)
        return jsonify({"reply": reply})
    except Exception as e:
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
    get_gold_market_data()  # 👈 提前预加载，确保首次调用更快

    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
