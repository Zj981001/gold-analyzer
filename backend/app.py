# backend/app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from llm_engine import chat_with_gold_data
from tools import get_gold_market_data

# 初始化Flask应用
app = Flask(__name__, static_folder='../frontend')

# 增强CORS配置，适配Render跨域
CORS(app, resources={
    r"/api/*": {
        "origins": ["*"],
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type", "Accept"],
        "max_age": 3600
    }
})


# ===================== 核心修复：给装饰器添加唯一endpoint名，避免路由冲突 =====================
def timeout_limit(seconds=10, endpoint=None):
    def decorator(f):
        # 关键修复：为每个装饰器生成唯一的endpoint名，避免重名
        f.endpoint = endpoint if endpoint else f.__name__

        def wrapped(*args, **kwargs):
            return f(*args, **kwargs)

        wrapped.__name__ = f.__name__  # 保留原函数名，进一步避免冲突
        return wrapped

    return decorator


# ===================== API接口（修复路由冲突） =====================
@app.route('/api/chat', methods=['POST'], endpoint='chat_api')
@timeout_limit(10, endpoint='chat_api')
def chat_api():
    try:
        # 限制请求大小
        if request.content_length and request.content_length > 1024 * 1024:
            return jsonify({"reply": "请求体过大"}), 413

        # 宽松JSON解析，避免解析失败抛异常
        data = request.get_json(silent=True)
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
        return jsonify({"reply": f"服务器处理异常：{str(e)[:100]}"}), 500


@app.route('/api/gold-data', methods=['GET'], endpoint='gold_data_api')
@timeout_limit(10, endpoint='gold_data_api')
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


# ===================== 启动服务（彻底移除错误参数） =====================
if __name__ == '__main__':
    print("⏳ 预加载黄金行情数据...")
    initial_data = get_gold_market_data()

    if 'error' in initial_data:
        print(f"❌ 预加载失败: {initial_data['error']}")
    else:
        print(f"✅ 预加载成功 | 当前金价: ${initial_data['current_price']}")

    # 适配Render部署的端口配置（仅保留Flask支持的参数）
    port = int(os.environ.get('PORT', 8000))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True  # 启用多线程处理并发请求
    )