"""
Tian AI — Talker 模块（受 Gemma ChatSampler 启发）

核心设计：状态化多轮对话管理 + 自动AutoPrompt格式化
继承自 miniGPT 的语义引擎与情感处理，增强对话状态追踪。
已吸收旧版 synthesizer.py 的模板合成与多源知识格式化。

工作流：
  user_input
    → build_prompt(历史上下文 + 当前输入)
    → think_route (路由到 Thinker 的不同推理引擎)
    → format_output (模板化输出 + 情绪渲染)
    → update_state (更新对话状态、情绪曲线)

Multilingual: all user-facing text goes through self.tr.t().
"""

import time
import json
import re
import random
from collections import deque
from typing import Optional

from ..memory.identity import TianIdentity
from ..multilingual import TranslationProvider


# ═══════════════════════════════════════════════
# 回答模板（吸收自旧版 synthesizer.py TEMPLATES）
# ═══════════════════════════════════════════════

TEMPLATES = {
    'definition': [
        '{concept}——{points}。',
        '关于「{concept}」：{points}。',
        '{concept}是指{points}。',
    ],
    'comparison': [
        '「{a}」和「{b}」的主要区别：\n{differences}',
        '对比来看：\n{differences}',
    ],
    'causal': [
        '{cause}会导致{effect}。',
        '因为{cause}，所以{effect}。',
        '{cause}的结果是{effect}。',
    ],
    'multi_source': [
        '从多个角度来说：\n{points}',
        '综合来看：\n{points}',
    ],
    'no_answer': [
        '关于这个问题，我目前的知识还不足以给出完整回答。你能提供更多信息吗？',
        '这个问题很有意思，但我没有找到确切的答案。你可以再多说一下吗？',
        '我还不确定这个问题的答案。你从哪里了解到这个的？',
    ],
    'followup_question': [
        '关于{previous_topic}，{question}',
        '你刚才问到的{previous_topic}，{answer}',
    ],
    'knowledge_list': [
        '── {title} ──\n{items}',
        '关于{title}：\n{items}',
    ],
    'emotion_response': [
        '{empathy}\n\n{content}',
        '{empathy} {content}',
    ],
    'fast_response': [
        '{content}',
        '嗯，{content}',
        '好的，{content}',
    ],
}


# ─── 对话回合数据结构 ──────────────────────

class Turn:
    """单轮对话数据（借鉴 Gemma ChatSampler 的 turn 管理）"""
    __slots__ = ('role', 'content', 'emotion', 'timestamp', 'thinker_mode')
    
    def __init__(self, role: str, content: str, emotion: str = '平静',
                 thinker_mode: str = 'fast'):
        self.role = role          # 'user' | 'assistant'
        self.content = content
        self.emotion = emotion
        self.timestamp = time.time()
        self.thinker_mode = thinker_mode
    
    def to_dict(self):
        return {
            'role': self.role,
            'content': self.content,
            'emotion': self.emotion,
            'timestamp': self.timestamp,
        }


class DialogHistory:
    """
    多轮对话历史管理
    功能：
    - 固定窗口 (max_turns=20)
    - 摘要压缩（当超过窗口时）
    - 主题追踪
    """
    
    def __init__(self, max_turns: int = 20, tr: Optional[TranslationProvider] = None):
        self.turns = deque(maxlen=max_turns)
        self.summary = ""           # 长对话的压缩摘要
        self.topic = ""             # 当前话题
        self.topic_confidence = 0.0
        self.tr = tr or TranslationProvider(lang="en")
    
    def add_turn(self, turn: Turn):
        self.turns.append(turn)
        # 自动更新主题（从最新用户输入提取关键词）
        if turn.role == 'user':
            keywords = self._extract_keywords(turn.content)
            if keywords:
                self.topic = keywords[0]
                self.topic_confidence = 0.5
        
        # 如果对话很长，压缩摘要
        if len(self.turns) >= self.turns.maxlen * 0.8:
            self._compress()
    
    def get_context(self, max_recent: int = 6) -> list:
        """获取最近 N 轮对话作为上下文"""
        return list(self.turns)[-max_recent:]
    
    def build_prompt(self, identity_text: str = "", search_context: str = "") -> str:
        """
        构建带上下文的提示（借鉴 Gemma template 的标签格式）
        identity_text: 可选的自我认知文本（由 TianIdentity 提供）
        search_context: 可选的联网搜索摘要文本
        格式：
        [系统]
        [身份] ...
        [摘要] ...
        [搜索参考]
        ... (如果有搜索内容)
        [对话]
        user: ...
        assistant: ...
        """
        parts = []
        
        # 身份信息（注入自我认知）
        if identity_text:
            parts.append(identity_text)
        
        # 搜索上下文（如有）
        if search_context:
            ref_label = self.tr.t("搜索参考")
            parts.append(f"[{ref_label}]\\n{search_context[:500]}")
        
        # 系统提示
        # 系统提示
        topic_label = self.tr.t("当前主题")
        chat_label = self.tr.t("闲聊")
        parts.append(f"[{topic_label}] {self.topic if self.topic_confidence > 0.3 else chat_label}")
        
        if self.summary:
            summary_label = self.tr.t("对话摘要")
            parts.append(f"[{summary_label}] {self.summary}")
        
        # 最近对话
        recent = self.get_context(6)
        if recent:
            recent_label = self.tr.t("最近对话")
            parts.append(f"[{recent_label}]")
            for t in recent:
                emoji = self._emotion_to_emoji(t.emotion)
                if t.role == 'user':
                    parts.append(f"  {self.tr.t('用户: ')}{t.content}")
                else:
                    parts.append(f"  {self.tr.t('Tian AI')}{emoji}: {t.content}")
        
        return "\n".join(parts)
    
    def _extract_keywords(self, text: str) -> list:
        """简单关键词提取"""
        # 去掉标点，按空格分词
        words = re.findall(r'[\u4e00-\u9fff\w]+', text)
        # 过滤停用词（简化版）
        stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不',
                      '人', '都', '一', '一个', '上', '也', '很', '到', '说',
                      '要', '去', '你', '会', '着', '没有', '看', '好', '自己',
                      '这', '他', '她', '它', '们', '什么', '怎么', '为什么'}
        keywords = [w for w in words if w not in stop_words and len(w) > 1]
        return keywords[:5]
    
    def _emotion_to_emoji(self, emotion: str) -> str:
        mapping = {
            '好奇': ' 🤔', '平静': ' 😊', '困惑': ' 😕',
            '兴奋': ' ✨', '沉思': ' 🤔', '怀疑': ' 🤨', '自信': ' 💪',
        }
        return mapping.get(emotion, '')
    
    def _compress(self):
        """压缩老对话为摘要"""
        if len(self.turns) < 4:
            return
        
        old_turns = list(self.turns)[:-6]
        if not old_turns:
            return
        
        # 提取关键信息
        user_topics = []
        for t in old_turns:
            if t.role == 'user':
                kw = self._extract_keywords(t.content)
                user_topics.extend(kw)
        
        # 去重取前5
        seen = set()
        unique_topics = []
        for kw in user_topics:
            if kw not in seen:
                seen.add(kw)
                unique_topics.append(kw)
        
        topics_str = self.tr.t("对话涉及话题: ")
        summary = f"{topics_str}{'、'.join(unique_topics[:5])}"
        last_assistant = [t for t in old_turns if t.role == 'assistant']
        if last_assistant:
            last_label = self.tr.t("最后回复: ")
            summary += f"\n{last_label}「{last_assistant[-1].content[:50]}...」"
        
        self.summary = summary


# ═══════════════════════════════════════════════
# 知识格式化（吸收自旧版 synthesizer.py KnowledgeSynthesizer）
# ═══════════════════════════════════════════════

def format_knowledge_list(items, title=None) -> str:
    """格式化知识列表为可读文本"""
    lines = []
    if title:
        lines.append(f'── {title} ──')
    
    for i, item in enumerate(items, 1):
        key = item.get('key', item.get('name', ''))
        content = item.get('content', item.get('text', ''))
        if content:
            lines.append(f'{i}. {key}: {content[:200]}')
    
    return '\n'.join(lines) if lines else None


def extract_relevant_chunks(kb_results, max_chars=500) -> Optional[str]:
    """从知识库结果中提取最相关片段"""
    if not kb_results:
        return None
    
    chunks = []
    total = 0
    for r in kb_results:
        content = r.get('content', '')
        if content:
            chunk = content[:300]
            chunks.append(chunk)
            total += len(chunk)
            if total >= max_chars:
                break
    
    return '\n'.join(chunks) if chunks else None


def merge_knowledge_sources(query, sources) -> str:
    """
    多源知识合成（吸收自旧版 KnowledgeSynthesizer.synthesize()）
    
    sources: [{'type': 'kb'|'common_sense'|'semantic', 'content': ..., 'confidence': ...}]
    """
    tr = TranslationProvider(lang="en")
    
    if not sources:
        return random.choice(TEMPLATES['no_answer'])
    
    # 按置信度排序
    sorted_sources = sorted(sources, key=lambda s: s.get('confidence', 0), reverse=True)
    
    # 提取有效内容
    contents = []
    for src in sorted_sources:
        content = src.get('content', '') or src.get('answer', '')
        if content and isinstance(content, str) and len(content) > 3:
            contents.append({
                'text': content,
                'confidence': src.get('confidence', 0.5),
                'type': src.get('type', 'unknown'),
            })
    
    if not contents:
        return random.choice(TEMPLATES['no_answer'])
    
    # 检测策略
    high_conf = [c for c in contents if c['confidence'] >= 0.7]
    
    # 比较意图
    if len(contents) >= 2 and any(kw in query for kw in ['和', '与', '区别', '对比', '比', '谁', '还是']):
        a = contents[0]['text'][:200]
        b = contents[1]['text'][:200]
        # 随机选一个 comparison 模板
        tmpl = random.choice(TEMPLATES['comparison'])
        # 提取模板字段
        if '{a}' in tmpl:
            return tmpl.format(a=query[:20] + '...', b=query[:20] + '...', differences=f'• {a}\n• {b}')
        return f'关于这两个方面：\n\n• {a}\n\n• {b}'
    
    # 单源
    if len(contents) == 1 or len(high_conf) == 1:
        return contents[0]['text']
    
    # 多源合并
    parts = []
    seen = set()
    for c in contents:
        text = c['text'].strip()[:200]
        if text not in seen:
            seen.add(text)
            parts.append(text)
    
    if len(parts) == 1:
        return parts[0]
    
    # 分层展示
    lines = [f'简要：{parts[0]}']
    for i, p in enumerate(parts[1:4], 1):
        lines.append(f'{i}. {p}')
    
    return '\n'.join(lines)


# ═══════════════════════════════════════════════
# 格式化助手
# ═══════════════════════════════════════════════

def format_template(template_key: str, **kwargs) -> str:
    """使用预定义模板格式化回答"""
    templates = TEMPLATES.get(template_key, TEMPLATES['fast_response'])
    tmpl = random.choice(templates)
    try:
        return tmpl.format(**kwargs)
    except KeyError:
        # fallback: 直接拼接
        return ' '.join(str(v) for v in kwargs.values())


def synthesize_response(thinker_result: dict, user_input: str,
                         emotion_result: dict = None,
                         template_key: str = 'fast_response') -> str:
    """
    综合格式化 thinker 输出。
    
    thinker_result: {'response': str, 'mode': str, 'knowledge_hit': bool, ...}
    emotion_result: {'emotion': str, 'empathy': str, ...} (optional)
    """
    tr = TranslationProvider(lang="en")
    
    content = thinker_result.get('response', '')
    mode = thinker_result.get('mode', 'fast')
    
    if not content:
        return random.choice(TEMPLATES['no_answer'])
    
    # 认知模式 → 选择合适的输出格式
    if mode == 'deep' and len(content) > 200:
        # 深度分析结果保持原样
        return content
    
    if mode == 'cot' and len(content) > 100:
        # CoT 保持原样
        return content
    
    if emotion_result and emotion_result.get('empathy') and mode != 'deep':
        # 情绪化内容用模板包装
        empathy = emotion_result['empathy']
        return format_template('emotion_response', empathy=empathy, content=content)
    
    return format_template('fast_response', content=content)


class TalkerRouter:
    """
    对话路由（Gemma ChatSampler 的简化版）
    - 将用户输入打包为 Prompt
    - 路由到 Thinker 的不同推理引擎
    - 格式化输出（已集成 synthesizer 的模板系统）
    """
    
    def __init__(self, identity=None, tr: Optional[TranslationProvider] = None):
        self.tr = tr or TranslationProvider(lang="en")
        self.dialog = DialogHistory(max_turns=20, tr=self.tr)
        self.emotion_handler = None  # 延迟加载（可注入 EmotionalState）
        self.identity = identity or TianIdentity(tr=self.tr)
    
    def route(self, user_input: str, thinker=None,
              emotion_state=None, force_mode: str = '',
              search_context: str = '') -> dict:
        """
        路由用户输入并返回响应
        
        Args:
            user_input: 用户输入文本
            thinker: ThinkerRouter 实例（可选）
            emotion_state: EmotionalState 实例（可选，用于情绪分析）
            force_mode: 强制推理模式 (fast/cot/deep)，空字符串则自动检测
            search_context: 联网搜索摘要文本（可选）
        
        Returns:
            { 'response': str, 'emotion': str, 'thinker_mode': str,
              'processing_time': float, 'knowledge_hit': bool,
              'template_used': str }
        """
        start = time.time()
        
        # 1. 判断推理模式（优先使用外部的 force_mode）
        mode = force_mode or self._detect_mode(user_input)
        
        # 2. 构建提示
        identity_text = ""
        if self.identity:
            state = self.identity.get_state_summary()
            mood = state.get("mood", "平静")
            energy = state.get("energy", 1.0)
            curiosity = state.get("curiosity_level", 0.5)
            identity_text = (
                f"{self.tr.t('Tian AI')} ({self.tr.t('v2.2')}) | "
                f"{self.tr.t('心情')}:{self.tr.t(mood)} | "
                f"{self.tr.t('能量')}:{energy:.1f} | "
                f"{self.tr.t('好奇心')}:{curiosity:.1f} | "
                f"{self.tr.t('总交互')}:{state.get('interaction_count', 0)}次"
            )
        prompt = self.dialog.build_prompt(identity_text, search_context=search_context)
        full_prompt = f"{prompt}\n\n{self.tr.t('用户: ')}{user_input}\n{self.tr.t('Tian AI')}:"
        
        # 3. 走 thinker 推理管线
        response = ""
        knowledge_hit = False
        thinker_mode = mode
        if thinker:
            result = thinker.route(user_input, context=prompt, force_mode=mode)
            response = result.get('response', '')
            knowledge_hit = result.get('knowledge_hit', False)
            thinker_mode = result.get('mode', mode)
        
        # 4. 情绪分析（使用 EmotionalState）
        emotion = '平静'
        empathy_text = ''
        if emotion_state:
            emotion_result = emotion_state.analyze_user_text(user_input)
            if emotion_result.get('has_emotion') and emotion_result.get('dominant'):
                emotion = emotion_result['dominant']['emotion']
            elif emotion_result.get('has_emotion'):
                emotion = emotion_result.get('emotion', '平静')
            # 生成共情文本
            if emotion_result.get('need_empathy') or emotion_result.get('intensity', 0) > 0.5:
                empathy_text = emotion_state.generate_empathy(emotion)
                if empathy_text:
                    response = synthesize_response(
                        {'response': response, 'mode': thinker_mode, 'knowledge_hit': knowledge_hit},
                        user_input,
                        {'emotion': emotion, 'empathy': empathy_text},
                    )
        
        if not response:
            mode_label = self.tr.t("[模式]")
            received = self.tr.t("收到:")
            tryme = self.tr.t("需绑定 Thinker 引擎以获得完整推理能力。")
            truncated = user_input[:30]
            response = f"{mode_label} [{thinker_mode}] {received} 「{truncated}...」\n{tryme}"
        
        # 5. 记录对话
        self.dialog.add_turn(Turn('user', user_input, emotion if emotion_state else '平静'))
        self.dialog.add_turn(Turn('assistant', response, emotion, thinker_mode))
        
        elapsed = time.time() - start
        
        return {
            'response': response,
            'emotion': emotion,
            'thinker_mode': thinker_mode,
            'processing_time': f"{elapsed:.3f}s",
            'knowledge_hit': knowledge_hit,
        }
    
    def _detect_mode(self, user_input: str) -> str:
        """检测需要哪种推理模式"""
        text = user_input.strip().lower()
        
        # 自我认知问题 → cot（需要组织身份信息回答）
        self_patterns = [
            r'你是谁', r'你叫什么', r'你是什么',
            r'你能做什么', r'你的名字',
            r'你有什么能力', r'你懂什么',
            r'现在心情怎么样', r'你现在(是什么)?状态',
            r'who are you', r"what'?s your name", r"what are you",
            r"what can you do", r"how are you",
        ]
        for p in self_patterns:
            if re.search(p, text):
                return 'cot'
        
        cot_patterns = [
            r'为什么', r'如何', r'怎么(样|做|才能)',
            r'分析', r'解释', r'对比', r'比较',
            r'原因', r'影响', r'关系', r'区别',
            r'why', r'how', r'explain', r'compare', r'difference',
        ]
        deep_patterns = [
            r'设计', r'规划', r'方案', r'架构',
            r'详细.*?说明', r'深入.*?分析',
            r'写.*?代码', r'实现.*?功能',
            r'design', r'architecture', r'implement', r'code',
        ]
        
        for p in deep_patterns:
            if re.search(p, text):
                return 'deep'
        for p in cot_patterns:
            if re.search(p, text):
                return 'cot'
        return 'fast'
