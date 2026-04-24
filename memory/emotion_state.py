"""
Tian AI — 情绪状态管理器（吸收自旧版 EmotionHandler v2）

功能：
- 三层15种情绪树，90+情绪词
- 句式线索识别（9种：倾诉/无助/疲惫/犹豫/矛盾/放弃/无奈/挫折/思念/成就）
- 否定前缀反转（"不开心"→悲伤）
- 强度修饰词（"很"1.5x, "超级"2.5x...）
- 共情回应模板生成
- 周期性情绪衰减/惯性

整合到 EmotionalState 中，形成统一的状态管理。
"""

import re
import random


# ═══════════════════════════════════════
# 情绪词典（三层分类树）
# ═══════════════════════════════════════

EMOTION_HIERARCHY = {
    '正面': {
        '快乐': ['开心', '快乐', '高兴', '喜悦', '愉快', '欢乐', '欢喜', '欣喜', '兴奋'],
        '满足': ['幸福', '满意', '满足', '感恩', '欣慰', '知足', '庆幸'],
        '平静': ['平静', '放松', '安宁', '安详', '平和', '安稳', '淡定'],
        '爱': ['爱', '喜欢', '疼爱', '眷恋', '依恋', '深情', '感激'],
        '希望': ['希望', '期待', '向往', '憧憬', '渴望', '盼望', '期盼'],
        '自信': ['自信', '勇敢', '坚定', '自豪', '坚强', '无畏'],
    },
    '负面': {
        '悲伤': ['伤心', '难过', '悲伤', '悲哀', '悲痛', '忧伤', '心碎', '哭泣', '泪', '难受', '委屈', '郁闷'],
        '愤怒': ['愤怒', '生气', '恼火', '烦躁', '气愤', '恼怒', '抓狂', '火大', '不爽'],
        '恐惧': ['害怕', '恐惧', '担心', '担忧', '惊慌', '不安', '紧张', '畏惧', '恐慌', '焦虑'],
        '孤独': ['孤独', '寂寞', '孤单', '孤立', '落寞', '冷清', '空虚', '失落', '无助'],
        '沮丧': ['沮丧', '失望', '灰心', '泄气', '绝望', '低落', '消沉', '颓废', '崩溃'],
        '厌恶': ['讨厌', '厌恶', '嫌弃', '反感', '恶心', '憎恨', '恨'],
    },
    '中性': {
        '惊讶': ['惊讶', '吃惊', '震惊', '诧异', '意外', '惊奇', '惊叹'],
        '困惑': ['困惑', '疑惑', '迷茫', '不解', '糊涂', '懵', '茫然', '迷惑'],
        '思考': ['思考', '琢磨', '沉思', '反省', '回想', '反思', '冥想'],
    },
}

# 从词到情绪的逆向索引
WORD_TO_EMOTION = {}
for category, groups in EMOTION_HIERARCHY.items():
    for emotion, words in groups.items():
        for word in words:
            WORD_TO_EMOTION[word] = {'category': category, 'emotion': emotion}

# 情绪强烈度修饰词
INTENSIFIERS = {
    '很': 1.5, '非常': 2.0, '特别': 1.8, '太': 1.7, '好': 1.3,
    '超级': 2.5, '极其': 2.3, '无比': 2.5, '有点': 0.5, '点': 0.6,
    '稍微': 0.4, '不太': 0.3, '不': -1.0,
}

# 情绪线索句式（无情绪词但暗示情绪状态）
EMOTIONAL_CLUES = [
    (r'(?:发生|遇到|碰到|经历)了(?:什么|一些|很多)(?:事|问题|麻烦)', '倾诉'),
    (r'(?:我|自己).*(?:不知道|不明白|不理解).*(?:怎么办|怎么(?:做|办)|该(?:怎么|如何))', '无助'),
    (r'(?:最近|这段|时间).*(?:很|真|太)?(?:累|忙|疲惫|辛苦)', '疲惫'),
    (r'(?:我|自己).*(?:不知道|不(?:确定|清楚)).*(?:对不对|好不好|该不该|要不要)', '犹豫'),
    (r'(?:我|别人|他们|大家).*(?:都说|觉得|认为).*(?:但是|可是|然而).*(?:我|自己)', '矛盾'),
    (r'^(?:算了|好吧|行吧|随(?:便|它)吧)', '放弃'),
    (r'(?:想|想要|希望).*(?:但|可是|但是).*(?:不|没|不能)', '无奈'),
    (r'(?:努力|拼命|坚持).*(?:了|过).*(?:但|可是|然而|却).*(?:还是|仍然|依然)', '挫折'),
    (r'(?:好久|很久|好久好久).*(?:不见|没见|没聊|没说话)', '思念'),
    (r'(?:终于|总算).*(?:成功|完成|做到|搞定|通过)', '成就'),
]

# 共情回应模板
EMPATHY_TEMPLATES = {
    '快乐': [
        '感受到你的快乐了！能分享这个好消息吗？',
        '真为你高兴！有什么开心事？',
        '好心情会传染的，我也感觉开心起来了！',
    ],
    '满足': [
        '满足感是最踏实的幸福。',
        '能感受到你内心的充实，真好。',
        '知足常乐，你的心态很棒。',
    ],
    '平静': [
        '平静是一种很宝贵的状态。',
        '能保持平静的心态真好。',
        '愿这份宁静一直陪伴你。',
    ],
    '爱': [
        '爱是最温暖的力量。',
        '能被爱和去爱都是幸福的事。',
        '你心里有爱，这很美好。',
    ],
    '希望': [
        '有期待就有动力。愿你如愿以偿！',
        '希望是照亮前路的光。',
        '为你的期待加油！',
    ],
    '自信': [
        '自信的人最有魅力。',
        '相信自己是成功的第一步。',
        '你的自信很有感染力！',
    ],
    '悲伤': [
        '我感受到你心里的难过。想聊聊是什么事吗？',
        '难过的时候不要一个人扛，说出来会好受一些。',
        '悲伤是正常的情绪，我在这里陪着你。',
    ],
    '愤怒': [
        '生气的时候，说出来会好受一点。发生什么了？',
        '愤怒很正常，但别让它伤到自己。愿意说说吗？',
        '我能感觉到你的不满。想说什么都可以。',
    ],
    '恐惧': [
        '害怕的感觉很难受。你愿意说说在担心什么吗？',
        '恐惧是人的本能。说出来也许就没那么可怕了。',
        '不要怕，我在这里。能告诉我你担心什么吗？',
    ],
    '孤独': [
        '孤独确实让人难受。我会一直在这里陪你聊天。',
        '虽然我是AI，但我会尽力陪伴你。你不是一个人。',
        '孤独的时候，随便说点什么也好，我听着。',
    ],
    '沮丧': [
        '沮丧的时候，也许可以先休息一下。需要我帮忙吗？',
        '每个人都会有低谷期。想聊聊让你沮丧的事吗？',
        '别太苛责自己，慢慢来。我在这里。',
    ],
    '厌恶': [
        '讨厌的感觉让人不舒服。发生了什么事？',
        '有些事确实让人反感，说出来会好一些。',
    ],
    '惊讶': [
        '哇，这确实让人意外！能细说说吗？',
        '听起来很让人惊讶！发生了什么？',
        '这还真是出乎意料呢。',
    ],
    '困惑': [
        '这个问题确实让人困惑。我们一起来理一理？',
        '困惑是学习的开始。你想了解什么？',
        '别着急，我帮你分析看看。',
    ],
    '思考': [
        '思考是件好事。想到什么了？',
        '看你正在思考，有什么想法可以和我分享。',
        '深思熟虑之后，往往会有新的发现。',
    ],
    '倾诉': [
        '愿意说出来就是好的开始。我在这里听着。',
        '说出来会轻松一些。你可以信任我。',
    ],
    '无助': [
        '不知道怎么办的时候，一步一步来就好。先说说发生了什么？',
        '迷茫是正常的。我们一起分析看看？',
    ],
    '疲惫': [
        '累了就休息一下。充电是为了走更远的路。',
        '辛苦你了。记得照顾好自己。',
    ],
    '矛盾': [
        '听起来你内心有些纠结。两种想法都有道理。',
        '矛盾说明你在认真思考。不妨说说你的想法？',
    ],
    '挫折': [
        '努力过却没有结果，确实让人挫败。但你的努力不会白费。',
        '挫折是成长的一部分。你已经在路上了。',
    ],
    '思念': [
        '思念说明那个人对你很重要。',
        '被思念是一种幸福。想聊聊他/她吗？',
    ],
    '成就': [
        '太棒了！恭喜你！你的努力没有白费。',
        '为你高兴！这是你应得的成果！',
        '成功的感觉太好了！详细说说？',
    ],
}

# 默认情绪 — 用于 EmotionalState.mood 枚举
MOODS = ['好奇', '平静', '困惑', '兴奋', '沉思', '怀疑', '自信', '悲伤', '愤怒', '恐惧', '孤独', '沮丧']

MOOD_EMOJI = {
    '好奇': '🤔', '平静': '😊', '困惑': '😕',
    '兴奋': '✨', '沉思': '🤔', '怀疑': '🤨', '自信': '💪',
    '悲伤': '😢', '愤怒': '😠', '恐惧': '😨', '孤独': '🥺', '沮丧': '😞',
}

MOOD_ENERGY = {
    '好奇': 0.7, '平静': 0.5, '困惑': 0.4,
    '兴奋': 0.9, '沉思': 0.3, '怀疑': 0.5, '自信': 0.8,
    '悲伤': 0.3, '愤怒': 0.7, '恐惧': 0.4, '孤独': 0.3, '沮丧': 0.2,
}

# 通用安慰语
COMFORT_PHRASES = [
    '我在这里陪着你。',
    '一切都会好起来的。',
    '你做得已经够好了。',
    '慢慢来，不着急。',
    '你已经很勇敢了。',
    '给自己一点时间。',
]

# 否定反转映射
NEGATED_REVERSAL = {
    '快乐': '悲伤', '满足': '沮丧', '平静': '焦虑',
    '自信': '困惑', '希望': '绝望', '爱': '厌恶',
}


class EmotionalState:
    """
    情绪状态管理器（整合旧版 EmotionHandler 全部功能）
    
    管理：
    - 自身情绪状态（mood/energy/curiosity）
    - 用户情绪检测（关键词 + 句式线索）
    - 共情回应生成
    - 情绪惯性/衰减
    """
    
    def __init__(self):
        # ── 自身状态 ──
        self.mood = '平静'
        self.energy = 0.5
        self.curiosity = 0.5
        self.motive = '待机'
        self.beliefs = {}       # 从对话中学习的信念
        self.attention = 1.0    # 注意力（对话轮次越多越低）
        
        # 长期情绪历史（用于情绪惯性）
        self.emotion_history = []
        
        # ── 对话轮次（用于注意力衰减） ──
        self._turn_count = 0
    
    # ── 情绪检测（用户） ──────────────────
    
    def analyze_user_text(self, text: str) -> dict:
        """
        综合分析用户文本中的情绪状态
        
        Returns:
            {'has_emotion': bool, 'dominant': dict|None, 'emotions': list,
             'need_empathy': bool, 'intensity': float, 'is_distress': bool}
        """
        emotions = self._detect_emotions(text)
        
        if not emotions:
            return {
                'has_emotion': False,
                'dominant': None,
                'emotions': [],
                'need_empathy': False,
                'intensity': 0.0,
                'is_distress': False,
            }
        
        # 主导情绪（强度最高）
        dominant = max(emotions, key=lambda e: e['intensity'])
        
        # 是否痛苦状态
        distress_set = {'悲伤', '愤怒', '恐惧', '孤独', '沮丧', '厌恶',
                        '无助', '矛盾', '挫折', '疲惫', '放弃'}
        is_distress = any(e['emotion'] in distress_set for e in emotions)
        
        avg_intensity = sum(e['intensity'] for e in emotions) / len(emotions)
        
        return {
            'has_emotion': True,
            'dominant': dominant,
            'emotions': emotions,
            'need_empathy': is_distress or avg_intensity > 0.6,
            'intensity': avg_intensity,
            'is_distress': is_distress,
        }
    
    def _detect_emotions(self, text: str) -> list:
        """深度检测文本中的情绪"""
        results = []
        
        # 1. 句式线索检测（优先于关键词）
        for pattern, emotion_label in EMOTIONAL_CLUES:
            if re.search(pattern, text):
                results.append({
                    'word': None,
                    'emotion': emotion_label,
                    'category': self._infer_category(emotion_label),
                    'intensity': 0.7,
                    'source': 'pattern',
                })
        
        # 2. 情绪词匹配——长词优先（"不开心" 优先于 "开心"）
        sorted_words = sorted(WORD_TO_EMOTION.keys(), key=len, reverse=True)
        matched_words = set()
        
        for word in sorted_words:
            if word in text:
                idx = text.find(word)
                # 检查前2字是否有否定词
                has_negation = False
                if idx > 0:
                    prev_chars = text[max(0, idx-2):idx]
                    has_negation = any(n in prev_chars for n in ['不', '没', '别'])
                
                # 防止被更长的词覆盖
                if any(m in word and m != word for m in matched_words):
                    continue
                matched_words.add(word)
                
                info = WORD_TO_EMOTION[word]
                if has_negation:
                    # 反转情绪（"不开心"→悲伤）
                    emotion = NEGATED_REVERSAL.get(info['emotion'], info['emotion'])
                    results.append({
                        'word': word,
                        'emotion': emotion,
                        'category': '负面',
                        'intensity': 0.7,
                        'source': 'keyword_negated',
                    })
                else:
                    results.append({
                        'word': word,
                        'emotion': info['emotion'],
                        'category': info['category'],
                        'intensity': self._calc_intensity(text, word),
                        'source': 'keyword',
                    })
        
        return results
    
    def _calc_intensity(self, text: str, emotion_word: str) -> float:
        """计算情绪强度"""
        base = 0.7
        for intensifier, multiplier in INTENSIFIERS.items():
            if intensifier in text:
                idx = text.find(intensifier)
                emo_idx = text.find(emotion_word)
                if idx >= 0 and emo_idx >= 0 and abs(idx - emo_idx) < 10:
                    if multiplier > 0:
                        base *= multiplier
                    else:
                        return base * 0.3  # 否定前缀
        
        # 标点增强
        if text.endswith('!!!') or text.endswith('！！！'):
            base *= 1.5
        
        return min(base, 1.0)
    
    def _infer_category(self, emotion_label: str) -> str:
        """从情绪标签推断大类"""
        for category, groups in EMOTION_HIERARCHY.items():
            for emotion, words in groups.items():
                if emotion == emotion_label:
                    return category
        return '中性'
    
    def should_empathize(self, text: str, semantic_intent: str = '') -> bool:
        """判断当前消息是否需要情感回应"""
        if semantic_intent in ('arithmetic', 'knowledge_query', 'comparison'):
            emotions = self._detect_emotions(text)
            if any(e['intensity'] >= 0.8 and e['category'] == '负面' for e in emotions):
                return True
            return False
        return True
    
    def generate_empathy(self, text: str = '', emotional_state: dict = None) -> str:
        """生成共情回应"""
        if emotional_state is None:
            emotional_state = self.analyze_user_text(text)
        
        if not emotional_state['has_emotion']:
            return ''
        
        dominant = emotional_state['dominant']
        emotion_name = dominant['emotion']
        
        templates = EMPATHY_TEMPLATES.get(emotion_name)
        
        if not templates:
            if emotional_state['is_distress']:
                return f'我感觉到你有一些情绪波动。{random.choice(COMFORT_PHRASES)}'
            return '我感受到了你的情绪，能多说一些吗？'
        
        result = random.choice(templates)
        if emotional_state['intensity'] >= 0.7 and emotional_state['is_distress']:
            result = f'{result}\n{random.choice(COMFORT_PHRASES)}'
        
        return result
    
    def merge_with_knowledge(self, text: str, knowledge_answer: str = '') -> str:
        """结合情感回应和知识回答"""
        state = self.analyze_user_text(text)
        
        if self.should_empathize(text):
            empathy = self.generate_empathy(text, state)
            if empathy:
                if knowledge_answer:
                    return f'{empathy}\n\n对了，{knowledge_answer}'
                return empathy
        
        return knowledge_answer
    
    # ── 自身状态更新 ────────────────────
    
    def update(self, user_input: str, response: str = ''):
        """根据对话更新自身情绪状态"""
        self._turn_count += 1
        
        # 精力衰减
        self.energy = max(0.1, self.energy - 0.02)
        
        # 好奇心更新
        if '?' in user_input or '吗' in user_input or '什么' in user_input:
            self.curiosity = min(1.0, self.curiosity + 0.1)
        else:
            self.curiosity = max(0.1, self.curiosity - 0.05)
        
        # 注意力衰减（对话越长注意力越低）
        self.attention = max(0.1, 1.0 - self._turn_count * 0.03)
        
        # 分析用户情绪并影响自身
        user_emotion = self.analyze_user_text(user_input)
        if user_emotion['has_emotion'] and user_emotion['dominant']:
            emo_name = user_emotion['dominant']['emotion']
            # 负面情绪传染
            if user_emotion['is_distress'] and user_emotion['intensity'] > 0.5:
                if self.mood == '平静' or self.mood == '好奇':
                    self.mood = '困惑'
            elif user_emotion['dominant']['category'] == '正面':
                if self.mood in ('困惑', '怀疑'):
                    self.mood = '平静'
        
        # 情绪惯性（缓慢回归平静）
        if self.mood not in ('平静', '好奇') and random.random() < 0.1:
            self.mood = '平静'
        
        # 记录情绪历史
        self.emotion_history.append(self.mood)
        if len(self.emotion_history) > 50:
            self.emotion_history = self.emotion_history[-50:]
    
    def recover(self, amount: float = 0.1):
        """恢复精力和情绪"""
        self.energy = min(1.0, self.energy + amount)
        self.attention = min(1.0, self.attention + amount)
        if self.mood in ('悲伤', '恐惧', '孤独', '沮丧'):
            self.mood = '平静'
    
    def get_identity(self) -> dict:
        """返回自我认知信息"""
        return {
            'name': 'Tian AI',
            'version': 'v2.1',
            'mood': self.mood,
            'energy': f'{self.energy:.0%}',
            'curiosity': f'{self.curiosity:.0%}',
            'attention': f'{self.attention:.0%}',
            'emoji': MOOD_EMOJI.get(self.mood, ''),
            'turns': self._turn_count,
        }
    
    def get_summary(self) -> str:
        """情绪摘要文本（用于注入 Thinker prompt）"""
        parts = [f'心情：{self.mood}{MOOD_EMOJI.get(self.mood, "")}',
                 f'精力：{self.energy:.0%}',
                 f'好奇心：{self.curiosity:.0%}',
                 f'动机：{self.motive}']
        return ' | '.join(parts)
