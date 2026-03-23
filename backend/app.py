# backend/app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import time
from llm_engine import chat_with_gold_data
from tools import get_gold_market_data

# 初始化Flask应用
app = Flask(__name__, static_folder='../frontend')

# 核心修复：增强CORS配置，适配Render跨域
CORS(app, resources={
    r"/api/*": {
        "origins": ["*"],  # 生产环境可改为你的Render域名
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type", "Accept"],
        "max_age": 3600
    }
})


# 增加全局请求超时处理
@app.before_request
def before_request():
    request.start_time = time.time()


# ===================== API接口 =====================
@app.route('/api/chat', methods=['POST'])
def chat_api():
    try:
        # 限制请求大小
        if request.content_length and request.content_length > 1024 * 1024:
            return jsonify({"reply": "请求体过大"}), 413

        # 解析JSON（宽松模式）
        data = request.get_json(silent=True)  # 修复：silent=True避免解析失败抛异常
        if not data:
            return jsonify({"reply": "请求体不是有效的JSON格式"}), 400

        if 'messages' not in data:
            return jsonify({"reply": "缺少messages字段"}), 400

        user_messages = data['messages']
        if not isinstance(user_messages, list):
            return jsonify({"reply": "messages必须是数组"}), 400

        # 调用LLM引擎
        reply = chat_with_gold_data(user_messages)
        return jsonify({"reply": reply})

    except Exception as e:
        print(f"❌ /api/chat 异常: {str(e)}")
        # 友好的错误提示
        return jsonify({"reply": f"服务器处理异常：{str(e)[:100]}"}), 500


@app.route('/api/gold-data', methods=['GET'])
def get_gold_data_api():
    """独立的金价数据接口"""
    try:
        gold_data = get_gold_market_data()
        if 'error' in gold_data:
            return jsonify({"error": gold_data['error']}), 500
        return jsonify(gold_data)
    except Exception as e:
        print(f"❌ /api/gold-data 异常: {str(e)}")
        return jsonify({"error": f"获取金价失败：{str(e)[:100]}"}), 500


# ===================== 静态文件路由 =====================
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


# ===================== 启动服务 =====================
if __name__ == '__main__':
    print("⏳ 预加载黄金行情数据...")
    initial_data = get_gold_market_data()

    if 'error' in initial_data:
        print(f"❌ 预加载失败: {initial_data['error']}")
    else:
        print(f"✅ 预加载成功 | 当前金价: ${initial_data['current_price']}")

    # 适配Render部署的端口配置
    port = int(os.environ.get('PORT', 8000))
    # 核心修复：关闭debug模式，增加线程数，适配Render
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True,  # 启用多线程处理请求
        timeout=10  # 请求超时时间
    )