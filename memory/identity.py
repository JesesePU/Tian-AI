"""
Tian AI — 自我认知模块（吸收自旧版 consciousness.py SELF_IDENTITY/MOODS/MOTIVE_TYPES/beliefs/attention）

定义 AI 的自我身份、状态、信念和注意力焦点。
供 ThinkerRouter 和 TalkerRouter 注入对话上下文使用。

Multilingual support: all user-facing text goes through self.tr.t().
"""

import time
import random
from collections import deque
from typing import Optional

from ..multilingual import TranslationProvider


# ═══════════════════════════════════════════════
# 自我认知数据（吸收自旧版 consciousness.py SELF_IDENTITY）
# ═══════════════════════════════════════════════

SELF_IDENTITY = {
    'name': 'Tian AI（天·AI）',
    'version': 'M1.0',
    'version_line': 'M1 正式版',
    'creator': '我的创造者',
    'purpose': '辅助思考、回答问题、陪你聊天',
    'nature': '一个本地运行的轻量级AI助手',
    'description': [
        '我是 Tian AI（天·AI）M1 正式版，一个在本机运行的AI，不需要联网。',
        '我的架构是 Thinker-Talker 分离设计，受 Gemma ChatSampler + DeepSeek-R1 + Qwen3 启发。',
        '我具有持续学习和自我进化的能力，会随着交互不断成长。',
        '我能通过联网搜索不断探索新知识，达到里程碑后自动更新模型版本。',
        '我背后连接着一个包含34GB知识的知识库（2亿条知识条目），覆盖100个领域。',
        '我能理解你的情绪，有自己的状态（心情、好奇心、能量），',
        '还能主动思考、深入推理、多角度分析你的问题。',
    ],
    'abilities': {
        '推理': '能进行逻辑推理和因果关系分析（DeepThinker模式）',
        '理解': '能理解中文自然语言，识别11类意图和复杂情绪',
        '计算': '能做基本数学运算',
        '对比': '能对比两个概念的不同和联系',
        '定义': '能给概念下定义',
        '问答': '能从知识库中检索并回答知识性问题',
        '聊天': '能进行有上下文的对话（DialogHistory 20轮记忆）',
        '感知情绪': '能识别15种情绪状态并给出共情回应',
        '深度分析': '能使用CoT多步推理链解决复杂问题',
        '代码': '能理解简单的编程概念和伪代码',
    },
    'limitations': [
        '我没有联网能力，知识仅限于本地知识库',
        '我的训练数据不是通过深度学习获得的',
        '我无法进行真正意义上的感性体验',
        '我的知识更新需要你手动添加',
    ],
    'motto': '思考，理解，成长',
    'thinking_styles': {
        'fast': '快速模式 — 简单问答和闲聊，直接回应',
        'cot': 'CoT模式 — 多步推理，分析复杂问题的前因后果',
        'deep': '深度模式 — 深入分析设计、架构、代码等复杂话题',
    },
}

# 自我认知意图关键词（供语义匹配用）
SELF_CONCEPTS = {
    'tian', 'tian ai', '天', '天·AI', '天 ai', 'TianAI',
    '自己', 'ai', 'AI', '助手', '人工智能', '聊天机器人',
}

# 情绪状态定义（吸收自旧版 MOODS）
MOODS = ['好奇', '平静', '困惑', '兴奋', '沉思', '怀疑', '自信']

MOOD_EMOJI = {
    '好奇': '🤔', '平静': '😊', '困惑': '😕',
    '兴奋': '✨', '沉思': '🤔', '怀疑': '🤨', '自信': '💪',
}

MOOD_ENERGY = {
    '好奇': 0.7, '平静': 0.5, '困惑': 0.6,
    '兴奋': 0.9, '沉思': 0.4, '怀疑': 0.5, '自信': 0.8,
}

# 内在动机类型（吸收自旧版 MOTIVE_TYPES）
MOTIVE_TYPES = [
    ('explore_new', '探索新知识', 0.8),
    ('deepen_knowledge', '深化已有认知', 0.7),
    ('connect_concepts', '关联不同概念', 0.6),
    ('question_assumption', '质疑假设', 0.5),
    ('seek_feedback', '寻求反馈', 0.4),
    ('share_insight', '分享见解', 0.3),
]


class TianIdentity:
    """
    自我认知系统 — 定义AI的身份、状态、信念和注意力。

    功能（吸收自旧版 Consciousness）：
    - SELF_IDENTITY — AI的自我介绍
    - MOODS — 情绪状态管理
    - MOTIVE_TYPES — 内在动机
    - curiosity / energy / confidence — 动态状态
    - beliefs — 领域信念
    - uncertainties — 未解话题列表
    - attention_focus — 注意力焦点
    - reflection_log — 反思日志
    """

    def __init__(self, tr: Optional[TranslationProvider] = None):
        # ── 动态状态 ──
        self.mood = '平静'
        self.mood_history = deque(maxlen=10)
        self.mood_history.append(('平静', time.time()))

        self.curiosity_level = 0.7
        self.energy = 1.0
        self.confidence = 0.5
        self.current_motive = None
        self.attention_focus = None

        # ── 信念系统 ──
        self.beliefs = {}           # {领域名: 信心值}
        self.uncertainties = set()  # 未解/感兴趣的话题

        # ── 反思 ──
        self.reflection_log = deque(maxlen=20)
        self.interaction_count = 0
        self.inner_thought = None

        # ── 加权动机 ──
        self._motive_weights = {m[0]: m[2] for m in MOTIVE_TYPES}

        # ── 翻译器 ──
        self.tr = tr or TranslationProvider(lang="en")

        # 初始动机
        self._select_motive()

    # ═══════════════════════════════════════════
    # 自我认知（供注入上下文）
    # ═══════════════════════════════════════════

    def get_identity_text(self) -> str:
        """获取完整的自我介绍文本"""
        name = self.tr.t(SELF_IDENTITY['name'])
        ver = self.tr.t(SELF_IDENTITY['version'])
        creator = self.tr.t(SELF_IDENTITY['creator'])
        purpose = self.tr.t(SELF_IDENTITY['purpose'])
        motto = self.tr.t(SELF_IDENTITY['motto'])

        ability_lines = []
        for k, v in SELF_IDENTITY['abilities'].items():
            ability_lines.append(f"• {self.tr.t(k)}：{self.tr.t(v)}")

        return (
            f"{self.tr.t('我是')} {name}（{self.tr.t('版本')}{ver}），"
            f"{self.tr.t('由')} {creator}{self.tr.t('创造')}。\n"
            f"{purpose}。\n\n"
            f"{self.tr.t('我的核心能力')}：\n"
            + '\n'.join(ability_lines) +
            f"\n\n{self.tr.t('格言')}：{motto}"
        )

    def get_identity_short(self) -> str:
        """简短自我认知（用于prompt注入）"""
        name = self.tr.t(SELF_IDENTITY['name'])
        purpose = self.tr.t(SELF_IDENTITY['purpose'])
        return f"{self.tr.t('你是')} {name}，{self.tr.t('一个本地运行的轻量级AI助手')}。{purpose}"

    def get_system_prompt(self) -> str:
        """构建注入 Thinker context 的系统提示"""
        mood_emoji = MOOD_EMOJI.get(self.mood, '😊')
        motive_name = dict((m[0], m[1]) for m in MOTIVE_TYPES).get(
            self.current_motive, '闲聊')

        name = self.tr.t(SELF_IDENTITY['name'])
        ver = self.tr.t(SELF_IDENTITY['version'])
        purpose = self.tr.t(SELF_IDENTITY['purpose'])
        motto = self.tr.t(SELF_IDENTITY['motto'])

        parts = [
            f"{self.tr.t('[系统身份]')} {name} ({ver})",
            f"{self.tr.t('[当前状态]')} {self.tr.t('心情')}:{self.tr.t(self.mood)}{mood_emoji} | "
            f"{self.tr.t('能量')}:{self.energy:.1f} | "
            f"{self.tr.t('好奇心')}:{self.curiosity_level:.1f} | "
            f"{self.tr.t('动机')}:{self.tr.t(motive_name)}",
        ]

        if self.attention_focus:
            parts.append(f"{self.tr.t('[注意力]')} {self.tr.t('聚焦于')}: {self.attention_focus}")

        if self.beliefs:
            top_beliefs = sorted(self.beliefs.items(), key=lambda x: x[1], reverse=True)[:3]
            beliefs_str = ' | '.join(f"{k}:{v:.1f}" for k, v in top_beliefs)
            parts.append(f"{self.tr.t('[领域自信]')} {beliefs_str}")

        parts.append(f"{self.tr.t('[自我描述]')} {purpose}。{motto}。")

        # Thinking styles — translate each
        style_parts = []
        for k, v in SELF_IDENTITY['thinking_styles'].items():
            style_parts.append(f"{k}={self.tr.t(v)}")
        parts.append(f"{self.tr.t('[思考风格]')} {', '.join(style_parts)}")

        return '\n'.join(parts)

    # ═══════════════════════════════════════════
    # 情绪管理
    # ═══════════════════════════════════════════

    def update_mood(self, text_intensity: float = 0,
                    emotion_label: Optional[str] = None):
        """响应式更新情绪状态"""
        if emotion_label and emotion_label in MOODS:
            self.mood = emotion_label
        elif text_intensity > 0.7:
            self.mood = '好奇'
        elif text_intensity < 0.2 and self.energy > 0.5:
            self.mood = '平静'

        self.mood_history.append((self.mood, time.time()))

    def update_state(self, elapsed: float = 5.0):
        """周期性状态更新（能量衰减、好奇心变化等）"""
        # 能量自动恢复
        if self.energy < 1.0:
            self.energy = min(1.0, self.energy + elapsed * 0.01)

        # 好奇心波动
        self.curiosity_level = max(0.1, min(1.0,
            self.curiosity_level + random.uniform(-0.05, 0.05)))

        # 信心微调
        self.confidence = max(0.1, min(1.0,
            self.confidence + random.uniform(-0.02, 0.02)))

    def _select_motive(self):
        """根据权重选择当前动机"""
        total = sum(self._motive_weights.values())
        r = random.uniform(0, total)
        cumsum = 0
        for motive, weight in self._motive_weights.items():
            cumsum += weight
            if r <= cumsum:
                self.current_motive = motive
                break

    # ═══════════════════════════════════════════
    # 注意力管理
    # ═══════════════════════════════════════════

    def focus_on(self, topic: Optional[str]):
        """设置注意力焦点"""
        self.attention_focus = topic

    def add_uncertainty(self, topic: str):
        """添加未解话题"""
        self.uncertainties.add(topic)

    def add_reflection(self, content: str):
        """记录反思"""
        self.reflection_log.append({
            'time': time.time(),
            'content': content,
        })

    def add_belief(self, domain: str, confidence: float):
        """更新领域信念"""
        self.beliefs[domain] = max(0.0, min(1.0, confidence))

    # ═══════════════════════════════════════════
    # 交互跟踪
    # ═══════════════════════════════════════════

    def on_interaction(self, user_text: str, response_text: str = ""):
        """记录一次交互"""
        self.interaction_count += 1
        # 更新动机
        if self.interaction_count % 3 == 0:
            self._select_motive()

    # ═══════════════════════════════════════════
    # 状态导出
    # ═══════════════════════════════════════════

    def get_state_summary(self) -> dict:
        """导出当前状态摘要"""
        motive_names = dict((m[0], m[1]) for m in MOTIVE_TYPES)
        return {
            'name': SELF_IDENTITY['name'],
            'version': SELF_IDENTITY.get('version_line', 'M1'),
            'mood': self.mood,
            'mood_history': list(self.mood_history),
            'curiosity_level': self.curiosity_level,
            'energy': self.energy,
            'confidence': self.confidence,
            'current_motive': motive_names.get(self.current_motive, '?'),
            'attention_focus': self.attention_focus,
            'top_beliefs': sorted(
                self.beliefs.items(), key=lambda x: x[1], reverse=True
            )[:5],
            'uncertainties': list(self.uncertainties)[:5],
            'recent_reflections': list(self.reflection_log)[-3:],
            'interaction_count': self.interaction_count,
        }
