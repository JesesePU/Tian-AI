#!/usr/bin/env python3
"""Tian AI — Flask API Server (升级自 miniGPT)"""
import os
import sys
import json
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from flask import Flask, jsonify, request
from tian_ai import TianAI

app = Flask(__name__)

# CORS
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

# 初始化 AI
db_path = os.path.join(project_root, 'knowledge_base.db')
ai = TianAI(db_path=db_path)


@app.route('/')
def index():
    styles = ai.list_styles()
    return jsonify({
        'name': 'Tian AI',
        'version': '2.0',
        'status': 'running',
        'current_style': ai.thinker.current_style,
        'styles': styles,
        'endpoints': {
            '/': '系统信息',
            '/chat': 'POST - 对话接口',
            '/status': 'GET - 系统状态',
            '/style': 'GET/POST - 查看/切换推理风格',
            '/reset': 'POST - 重置对话历史',
        }
    })


@app.route('/status')
def status():
    return jsonify(ai.get_status())


@app.route('/style', methods=['GET', 'POST'])
def handle_style():
    """查看或切换推理风格"""
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        style = data.get('style', '综合')
        try:
            msg = ai.set_style(style)
            return jsonify({
                'status': 'ok',
                'message': msg,
                'current_style': ai.thinker.current_style,
                'all_styles': ai.list_styles(),
            })
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
    
    # GET: 返回当前风格和所有可选风格
    return jsonify({
        'current_style': ai.thinker.current_style,
        'styles': ai.list_styles(),
    })


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    user_input = data.get('message', '')
    force_mode = data.get('mode')
    style = data.get('style')  # 每次请求可选覆盖风格

    if not user_input:
        return jsonify({'error': '请提供 message 字段'}), 400

    result = ai.chat(user_input, force_mode=force_mode, style=style)
    return jsonify(result)


@app.route('/reset', methods=['POST'])
def reset():
    """重置对话历史"""
    ai.short_term.messages.clear()
    return jsonify({'status': 'ok', 'message': '对话历史已重置'})


if __name__ == '__main__':
    print(f"✨ Tian AI Server starting...")
    print(f"   DB: {db_path}")
    print(f"   Style: {ai.thinker.current_style}")
    print(f"   Py: {sys.version.split()[0]}")
    print(f"   Listening on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
