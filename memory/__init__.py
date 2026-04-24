"""
Tian AI — Memory 模块（知识库 + 情绪状态 + 记忆管理）

适配原 miniGPT 的 34GB SQLite 知识库 + Consciousness 状态系统。
保持向后兼容，同时提供更清晰的接口。
"""

import sqlite3
import time
import json
import re
import os
from collections import deque


# ─── 知识库适配器 ──────────────────────────
class KnowledgeBase:
    """
    34GB SQLite 知识库适配器
    
    原 miniGPT 知识库结构：
    - 表: concepts (concept, key, content, domain, confidence)
    - key 格式: 概念名+问法组合（30种问法）
    - 查询: WHERE key=? 全索引扫描（0.04-0.1s）
    
    使用说明：
    - 通过软链接访问 knowledge_base.db
    - 只读操作，不修改数据库
    """
    
    def __init__(self, db_path: str = 'knowledge_base.db'):
        self.db_path = self._resolve_path(db_path)
        self.conn = None
        self._connect()
        self._verify_schema()
    
    def _resolve_path(self, path: str) -> str:
        candidates = [
            path,
            os.path.join(os.path.dirname(__file__), '..', '..', path),
            os.path.expanduser(f'~/miniGPT_project/miniGPT/{path}'),
        ]
        for c in candidates:
            norm = os.path.normpath(c)
            if os.path.exists(norm):
                return norm
        return path
    
    def _connect(self):
        try:
            self.conn = sqlite3.connect(f'file:{self.db_path}?mode=ro',
                                        uri=True, check_same_thread=False)
            self.conn.execute("PRAGMA query_only = 1")
        except sqlite3.OperationalError:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode = WAL")
    
    def _verify_schema(self):
        try:
            cursor = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
        except Exception:
            tables = []
    
    def search(self, query: str, limit: int = 3) -> dict:
        if not self.conn:
            return None
        try:
            cursor = self.conn.execute(
                "SELECT concept, content, domain, confidence FROM concepts "
                "WHERE concept=? LIMIT 1",
                (query.strip(),)
            )
            row = cursor.fetchone()
            if row:
                return {'content': row[1], 'concept': row[0],
                        'domain': row[2], 'confidence': row[3]}
            chars = re.findall(r'[\u4e00-\u9fff]', query)
            if chars:
                like_pattern = '%' + '%'.join(chars[:6]) + '%'
                cursor = self.conn.execute(
                    "SELECT concept, content, domain, confidence FROM concepts "
                    "WHERE concept LIKE ? LIMIT ?",
                    (like_pattern, limit)
                )
                rows = cursor.fetchall()
                if rows:
                    best = rows[0]
                    return {'content': best[1], 'concept': best[0],
                            'domain': best[2], 'confidence': best[3]}
            return None
        except Exception:
            return None
    
    def close(self):
        if self.conn:
            self.conn.close()


# ─── 情绪状态（增强版 — 从 emotion_state.py 导入） ──────
from .emotion_state import EmotionalState, MOODS, MOOD_EMOJI, MOOD_ENERGY


# ─── 短时记忆 ──────────────────────────────
class ShortTermMemory:
    """
    短期记忆 — 最近 N 轮对话 + 临时上下文
    """
    
    def __init__(self, maxlen: int = 10):
        self.messages = deque(maxlen=maxlen)
        self.topics = []        # 最近话题列表
        self.agent_mode = False
        self.last_agent_action = ""
    
    def add(self, role: str, content: str):
        self.messages.append({
            'role': role,
            'content': content,
            'time': time.time(),
        })


# ─── 长时记忆 ──────────────────────────────
class LongTermMemory:
    """
    长期记忆 — 重要知识 + 用户偏好 + 学习内容
    存储到 JSON 文件中，保持持久化
    """
    
    def __init__(self, path: str = 'memory_store.json'):
        self.path = path
        self.facts = {}
        self.user_prefs = {}
        self.learned = []
        self._load()
    
    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.facts = data.get('facts', {})
                    self.user_prefs = data.get('user_prefs', {})
                    self.learned = data.get('learned', [])
            except (json.JSONDecodeError, IOError):
                pass
    
    def save(self):
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump({
                    'facts': self.facts,
                    'user_prefs': self.user_prefs,
                    'learned': self.learned[-100:],
                }, f, ensure_ascii=False, indent=2)
        except IOError:
            pass
