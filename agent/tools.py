#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
miniGPT Agent 工具系统
可注册的工具集合：shell、Python、文件操作、知识库等
"""

import subprocess
import os
import sys
import json
import shlex
import tempfile
import traceback

# ─── 工具注册表 ─────────────────────────────
_REGISTRY = {}

def register(name, description, func, params=None):
    """注册一个工具"""
    _REGISTRY[name] = {
        'name': name,
        'description': description,
        'function': func,
        'params': params or [],
    }

def list_tools():
    """列出所有可用工具"""
    return [
        {'name': t['name'], 'description': t['description'], 'params': t['params']}
        for t in _REGISTRY.values()
    ]

def call_tool(name, **kwargs):
    """调用工具"""
    if name not in _REGISTRY:
        return {'error': f'未知工具: {name}，可用工具: {list(_REGISTRY.keys())}'}
    tool = _REGISTRY[name]
    try:
        result = tool['function'](**kwargs)
        return {'success': True, 'result': result}
    except Exception as e:
        return {'success': False, 'error': str(e), 'traceback': traceback.format_exc()}


# ══════════════════════════════════════════
# 内置工具实现
# ══════════════════════════════════════════

def _tool_shell(command, timeout=30):
    """执行 shell 命令"""                           
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, 'PATH': '/data/data/com.termux/files/usr/bin:' + os.environ.get('PATH', '')},
            executable='/data/data/com.termux/files/usr/bin/bash',
        )
        output = result.stdout
        if result.stderr:
            output += '\n[stderr]\n' + result.stderr
        return {
            'stdout': result.stdout[:5000],
            'stderr': result.stderr[:2000],
            'exit_code': result.returncode,
            'output': output[:7000],
        }
    except subprocess.TimeoutExpired:
        return {'error': f'命令执行超时 ({timeout}s)', 'stdout': '', 'stderr': '', 'exit_code': -1}
    except Exception as e:
        return {'error': str(e), 'stdout': '', 'stderr': '', 'exit_code': -1}

def _tool_python(code, timeout=30):
    """执行 Python 代码"""
    try:
        # 创建临时文件
        import tempfile, textwrap
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            # 包裹代码确保能捕获 print
            wrapped = textwrap.dedent(f"""\
import sys, json, math, random, re, os, collections, datetime, itertools, functools
sys.path.insert(0, '{shlex.quote(os.path.dirname(os.path.abspath(__file__)))}')
{code}
""")
            f.write(wrapped)
            tmp_path = f.name
        result = subprocess.run(
            [sys.executable, '-u', tmp_path],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'},
        )
        os.unlink(tmp_path)
        output = result.stdout
        if result.stderr:
            output += '\n[stderr]\n' + result.stderr
        return {
            'stdout': result.stdout[:5000],
            'stderr': result.stderr[:2000],
            'exit_code': result.returncode,
            'output': output[:7000],
        }
    except subprocess.TimeoutExpired:
        return {'error': f'Python超时 ({timeout}s)', 'stdout': '', 'stderr': '', 'exit_code': -1}
    except Exception as e:
        return {'error': str(e), 'stdout': '', 'stderr': '', 'exit_code': -1}

def _tool_read_file(path, offset=0, limit=100):
    """读取文件内容"""
    try:
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            return {'error': f'文件不存在: {path}'}
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        total = len(lines)
        start = offset if offset >= 0 else max(0, total + offset)
        end = min(start + limit, total)
        content = ''.join(lines[start:end])
        return {
            'total_lines': total,
            'showing': f'lines {start+1}-{end} of {total}',
            'content': content,
        }
    except Exception as e:
        return {'error': str(e)}

def _tool_write_file(path, content, append=False):
    """写入文件内容"""
    try:
        path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        mode = 'a' if append else 'w'
        with open(path, mode, encoding='utf-8') as f:
            f.write(content)
        return {'success': True, 'size': len(content), 'mode': 'append' if append else 'write'}
    except Exception as e:
        return {'error': str(e)}

def _tool_search_files(pattern, path='.', target='content'):
    """搜索文件"""
    import subprocess
    try:
        cmd = f"grep -rn '{pattern}' '{path}' --include='*.py' --include='*.html' --include='*.css' --include='*.js' --include='*.txt' --include='*.json' --include='*.md' --include='*.sh' --include='*.yml' --include='*.yaml' --include='*.conf' --include='*.cfg' --include='*.ini' --include='*.toml' 2>/dev/null | head -30"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout or result.stderr
        matches = [l for l in output.split('\n') if l.strip()]
        return {'matches': len(matches), 'results': matches[:30]}
    except Exception as e:
        return {'error': str(e)}

def _tool_list_dir(path='.', detail=False):
    """列出目录内容"""
    try:
        path = os.path.expanduser(path)
        items = os.listdir(path)
        if detail:
            details = []
            for item in sorted(items):
                fp = os.path.join(path, item)
                try:
                    stat = os.stat(fp)
                    details.append({
                        'name': item,
                        'type': 'dir' if os.path.isdir(fp) else 'file',
                        'size': stat.st_size,
                        'modified': stat.st_mtime,
                    })
                except:
                    details.append({'name': item, 'type': '?', 'size': 0, 'modified': 0})
            return {'items': details, 'count': len(details)}
        return {'items': sorted(items), 'count': len(items)}
    except Exception as e:
        return {'error': str(e)}

def _tool_knowledge_query(concept):
    """查询知识库中关于某个概念的信息"""
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'knowledge_base.db')
    if not os.path.exists(db_path):
        return {'error': '知识库不存在'}
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # 用 30 种问法模板
    templates = [
        f"我想了解{concept}", f"讲一下{concept}", f"通俗解释{concept}",
        f"{concept}是什么", f"什么是{concept}", f"定义{concept}",
        f"介绍{concept}", f"科普{concept}", f"快速认识{concept}",
        f"从零了解{concept}", f"我需要知道{concept}", f"告诉我{concept}",
        f"解释{concept}", f"关于{concept}", f"分析{concept}",
        f"简述{concept}", f"描述{concept}", f"说明{concept}",
        f"概述{concept}", f"总结{concept}", f"评价{concept}",
        f"讨论{concept}", f"讲解{concept}", f"能不能讲一下{concept}",
        f"简单说说{concept}", f"{concept}相关知识", f"{concept}的核心内容",
        f"{concept}的原理", f"{concept}的基础知识", f"{concept}指什么",
    ]
    results = []
    for tmpl in templates:
        try:
            c.execute("SELECT key, content, domain FROM knowledge WHERE key = ? LIMIT 1", (tmpl,))
            row = c.fetchone()
            if row:
                results.append({'key': row[0], 'content': row[1], 'domain': row[2]})
        except:
            continue
        if len(results) >= 3:
            break
    conn.close()
    if results:
        return {'concept': concept, 'results': results, 'hits': len(results)}
    return {'concept': concept, 'results': [], 'hits': 0}


# ─── 注册所有工具 ────────────────────────────

register(
    'shell', '执行 shell 命令（bash，Termux 环境）',
    _tool_shell,
    params=[
        {'name': 'command', 'type': 'string', 'description': '要执行的 shell 命令', 'required': True},
        {'name': 'timeout', 'type': 'integer', 'description': '超时秒数', 'default': 30},
    ],
)

register(
    'python', '执行 Python 代码片段（可导入标准库和项目模块）',
    _tool_python,
    params=[
        {'name': 'code', 'type': 'string', 'description': 'Python 代码', 'required': True},
        {'name': 'timeout', 'type': 'integer', 'description': '超时秒数', 'default': 30},
    ],
)

register(
    'read_file', '读取文件内容，支持行范围',
    _tool_read_file,
    params=[
        {'name': 'path', 'type': 'string', 'description': '文件路径', 'required': True},
        {'name': 'offset', 'type': 'integer', 'description': '起始行（0=开头，负数=从末尾算）', 'default': 0},
        {'name': 'limit', 'type': 'integer', 'description': '最多读取行数', 'default': 100},
    ],
)

register(
    'write_file', '写入或追加文件内容',
    _tool_write_file,
    params=[
        {'name': 'path', 'type': 'string', 'description': '文件路径', 'required': True},
        {'name': 'content', 'type': 'string', 'description': '文件内容', 'required': True},
        {'name': 'append', 'type': 'boolean', 'description': '是否追加而不是覆盖', 'default': False},
    ],
)

register(
    'search_files', '搜索文件内容（grep），支持正则',
    _tool_search_files,
    params=[
        {'name': 'pattern', 'type': 'string', 'description': '搜索模式（正则）', 'required': True},
        {'name': 'path', 'type': 'string', 'description': '搜索路径', 'default': '.'},
    ],
)

register(
    'list_dir', '列出目录内容',
    _tool_list_dir,
    params=[
        {'name': 'path', 'type': 'string', 'description': '目录路径', 'default': '.'},
        {'name': 'detail', 'type': 'boolean', 'description': '是否显示详细信息', 'default': False},
    ],
)

register(
    'knowledge_query', '查询本地知识库关于某个概念的信息',
    _tool_knowledge_query,
    params=[
        {'name': 'concept', 'type': 'string', 'description': '要查询的概念名称', 'required': True},
    ],
)
