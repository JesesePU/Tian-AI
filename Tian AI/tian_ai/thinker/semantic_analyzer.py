"""
Tian AI — 语义分析器（吸收自旧版 SemanticEngine v2）

功能：
- 11 类意图识别（带优先级排序）
- 实体提取（已知概念/人名/学科/数字）
- 关系抽取（6种关系模式）
- 否定检测（多层级 + 双重否定）
- 疑问类型检测（7种）
- 复杂度评估
- 追问检测 → followup 路由

将旧版 561 行 semantic_engine.py 精简为核心功能模块。
"""

import re


# ═══════════════════════════════════════
# 意图模式（优先级排序）
# ═══════════════════════════════════════

INTENT_PATTERNS = {
    'arithmetic': [
        r'等于多少', r'等于几',
        r'^\d+\s*[\+\-\×\*\/÷]\s*\d+\s*$',
        r'^\d+\s*[\+\-\×\*\/÷]\s*\d+\s*等于',
        r'计算', r'运算',
    ],
    'greeting': [
        r'^(?:你好|您好|嗨|hi\b|hello\b|hey\b|早\b|晚上好|下午好|在吗|在不在)',
        r'^(?i:hi\b|hello\b|hey\b|greetings|good\s*(?:morning|afternoon|evening)|what'+"'"+r's\s*up|howdy)',
    ],
    'self_identity': [
        r'(?:你|自己|你).*(?:是谁|叫什么|是啥|什么名字|怎么称呼)',
        r'(?:你|自己).*(?:是做什么的|能做什么|有什么用|有什么功能|哪些能力)',
        r'(?:你的|有什么).*(?:功能|作用|能力|特点)',
        r'(?:你知道什么|你懂什么|你有什么知识)',
        r'(?:你可以|你能)[^?]*吗\??$',
        r'你是谁[？\?]?\s*$',
        r'对自己介绍|自我简介|关于你',
    ],
    'self_state': [
        r'(?:你|自己).*(?:现在|当前|此刻|目前).*(?:状态|情绪|感觉|如何|怎么样)',
        r'(?:你今天|你现在).*(?:心情|情绪|状态|感觉)',
        r'(?:你高兴|你开心|你喜欢|你讨厌|你觉得)',
        r'你有感情吗|你有意识吗|你会思考吗',
        r'你(?:是|有)(?:人|活|生命|灵魂)吗',
    ],
    'comparison': [
        r'和.*(?:区别|不同|对比|比较)', r'与.*(?:区别|不同|对比|比较)',
        r'谁[更最]', r'(?:比|比起).*(?:更|还|要)',
        r'(?:区别|不同|对比)在于',
        r'(?:哪个|谁).*(?:厉害|强|大|好)',
    ],
    'emotion': [
        r'^(?:我|自己|心里).*(?:开心|伤心|难过|愤怒|焦虑|恐惧|孤独|沮丧|不爽|烦|累|困|饿)',
        r'(?:好|真|很|太)(?:开心|伤心|难过|愤怒|焦虑|孤独|沮丧|不爽|累|困|饿)',
        r'(?:我|自己).*(?:不(?:开心|高兴|爽)|难受|委屈|郁闷|痛苦)',
    ],
    'causal': [
        r'为什么', r'为何', r'原因', r'导致',
        r'会产生', r'由.*引起', r'是什么原因',
        r'如果.*就', r'会怎样', r'什么结果',
    ],
    'definition': [
        r'的定义', r'的定义是', r'意思是', r'含义',
        r'指的是', r'是指',
    ],
    'followup': [
        r'然后', r'还有', r'继续', r'接着说',
        r'展开说说', r'详细点', r'更多',
        r'那.*呢', r'所以',
    ],
    'knowledge_query': [
        r'什么是', r'是什么', r'是什么意思', r'什么叫做',
        r'解释', r'说明', r'介绍', r'说说',
        r'告诉我', r'讲(?:讲|一下)',
        r'何为', r'关于',
    ],
}

# 意途优先级（从最具体到最通用）
INTENT_PRIORITY = [
    'arithmetic', 'greeting', 'self_identity', 'self_state',
    'comparison', 'emotion', 'causal', 'definition',
    'followup', 'knowledge_query',
]

# 否定词
NEGATION_WORDS = {
    '不': 'negation', '没': 'negation', '没有': 'negation',
    '别': 'prohibition', '不要': 'prohibition', '不用': 'prohibition',
    '无': 'negation', '非': 'negation',
    '从不': 'always_negation', '从未': 'always_negation',
    '不太': 'weak_negation', '不太': 'weak_negation',
}

# 疑问词
QUESTION_WORDS = {
    '什么': 'what', '谁': 'who', '哪里': 'where',
    '为什么': 'why', '怎么': 'how', '怎样': 'how',
    '如何': 'how', '多少': 'how_much', '几': 'how_many',
    '哪个': 'which', '哪些': 'which_plural', '多久': 'how_long',
}

# 关系抽取模式
RELATION_PATTERNS = [
    (r'(\w+)和(\w+)的(?:关系|联系|区别|不同)', 'compare', 2),
    (r'(\w+)是(\w+)的一种', 'is_a', 2),
    (r'(\w+)由(\w+)组成', 'composed_of', 2),
    (r'(\w+)包含(\w+)', 'contains', 2),
    (r'(\w+)导致(\w+)', 'causes', 2),
    (r'(\w+)产生(\w+)', 'produces', 2),
    (r'(\w+)发明了(\w+)', 'invented', 2),
]

# 停用词
STOPWORDS = {
    '的', '了', '在', '是', '我', '有', '和', '就',
    '不', '人', '都', '一', '一个', '上', '也', '很',
    '到', '说', '要', '去', '你', '会', '着', '没有',
    '看', '好', '自己', '这', '他', '她', '它', '们',
    '那', '些', '什么', '怎么', '吗', '啊', '呢', '吧',
    '呀', '嗯', '哦', '喔', '哟', '喂', '么',
    '个', '对', '是', '能', '有',
}


class SemanticAnalyzer:
    """语义分析器 — 意图/实体/关系/否定/复杂度"""

    def __init__(self, known_concepts=None):
        self.known_concepts = known_concepts or set()
        # 预编译意图正则
        self._compiled_intents = {
            name: [re.compile(p, re.IGNORECASE) for p in patterns]
            for name, patterns in INTENT_PATTERNS.items()
        }

    def analyze(self, text: str) -> dict:
        """全面分析文本语义"""
        text = text.strip()
        if not text:
            return self._empty_result()

        intent = self._detect_intent(text)

        return {
            'original': text,
            'intent': intent,
            'is_knowledge_query': self._is_knowledge_query(text, intent),
            'question_type': self._detect_question_type(text),
            'negation': self._detect_negation(text),
            'relations': self._extract_relations(text),
            'entities': self._extract_entities(text),
            'complexity': self._assess_complexity(text),
            'keywords': self._extract_keywords(text),
        }

    def _empty_result(self) -> dict:
        return {
            'original': '',
            'intent': 'empty',
            'is_knowledge_query': False,
            'question_type': 'unknown',
            'negation': {'has_negation': False, 'polarity': 'neutral'},
            'relations': [],
            'entities': [],
            'complexity': {'level': 'simple', 'score': 0},
            'keywords': [],
        }

    def _is_knowledge_query(self, text: str, intent: str) -> bool:
        if intent in ('knowledge_query', 'definition', 'comparison', 'arithmetic',
                      'self_identity', 'self_state'):
            return True
        markers = ['什么是', '是什么', '有什么', '定义', '概念', '含义', '解释']
        return any(m in text for m in markers)

    def _detect_intent(self, text: str) -> str:
        """按优先级检测主要意图"""
        for intent in INTENT_PRIORITY:
            if any(p.search(text) for p in self._compiled_intents[intent]):
                return intent
        return 'general'

    def _detect_question_type(self, text: str) -> str:
        """检测问题类型"""
        if re.search(r'(?:是|有)(?:什么|哪些|哪几种|哪几个)', text):
            return 'open_list'
        if re.search(r'是不是|对不对|有没有|是否|能否|能不能|会不会|可不可以', text):
            return 'yes_no'
        if re.search(r'(?:什么|哪(?:个|里|位)|谁)', text):
            return 'wh_question'
        if re.search(r'(?:为什么|怎么|如何|怎样)', text):
            return 'how_why'
        if re.search(r'多少|几[个位只]|多大|多远|多久', text):
            return 'quantitative'
        if re.search(r'哪(?:个|位).*(?:更|最|比较)', text):
            return 'comparison_choice'
        if re.search(r'对吧|是吧|没错|对吗', text):
            return 'confirmation'
        return 'unknown'

    def _detect_negation(self, text: str) -> dict:
        """多层级否定检测"""
        cleaned = re.sub(r'(?:区别|特别|分别|个别|级别|鉴别)', '', text)
        found = []
        polarity = 'neutral'

        for word, ntype in sorted(NEGATION_WORDS.items(), key=lambda x: -len(x[0])):
            if word in cleaned:
                found.append({'word': word, 'type': ntype})
                if ntype == 'negation':
                    polarity = 'negative'
                elif ntype == 'prohibition':
                    polarity = 'prohibition'
                elif ntype == 'weak_negation':
                    polarity = 'weak_negative'

        # 双重否定
        if re.findall(r'(?:不是|没有|并非|未尝).{0,5}(?:不|没)', cleaned):
            polarity = 'double_negative'

        return {
            'has_negation': len(found) > 0 and polarity != 'double_negative',
            'is_double_negative': polarity == 'double_negative',
            'negation_words': [f['word'] for f in found],
            'polarity': polarity,
        }

    def _extract_relations(self, text: str) -> list:
        """提取实体间关系"""
        relations = []
        for pattern, rel_type, group_count in RELATION_PATTERNS:
            matches = re.findall(pattern, text)
            for m in matches:
                if group_count == 2 and isinstance(m, tuple):
                    entity_a, entity_b = m
                    relations.append({
                        'type': rel_type,
                        'subject': entity_a,
                        'object': entity_b,
                        'expression': f'{entity_a} ->({rel_type})-> {entity_b}',
                    })
                elif group_count == 1:
                    relations.append({
                        'type': rel_type,
                        'subject': m if isinstance(m, str) else m[0],
                        'expression': f'{m} ->({rel_type})',
                    })
        return relations

    def _extract_entities(self, text: str) -> list:
        """提取实体"""
        entities = []

        # 1. 已知概念匹配
        if self.known_concepts:
            sorted_concepts = sorted(self.known_concepts, key=len, reverse=True)
            for concept in sorted_concepts:
                if concept in text:
                    if not any(concept in e['name'] for e in entities):
                        entities.append({
                            'name': concept,
                            'type': self._infer_entity_type(concept),
                        })

        # 2. 人名模式
        name_matches = re.findall(
            r'(?:(?!什么)[\u4e00-\u9fff]{2,4})(?:是|和|与|提出|发明|比|开创|认为|说)',
            text
        )
        for nm in name_matches:
            name = nm[:-1]
            if name not in [e['name'] for e in entities]:
                entities.append({'name': name, 'type': 'person'})

        # 3. 学科概念
        field_matches = re.findall(
            r'[\u4e00-\u9fff]{2,6}(?:学|论|力|定律|原理|效应|定理)', text
        )
        for fm in field_matches:
            if fm not in [e['name'] for e in entities]:
                entities.append({'name': fm, 'type': 'knowledge_field'})

        # 4. 数字
        for num in re.findall(r'\d+', text):
            if num not in [e['name'] for e in entities]:
                entities.append({'name': num, 'type': 'number'})

        return entities

    def _infer_entity_type(self, name: str) -> str:
        if name.endswith('学') or name.endswith('论'):
            return 'knowledge_field'
        if name.endswith('力') or name.endswith('定律') or name.endswith('效应'):
            return 'physical_concept'
        if name.endswith('情绪') or name in {'开心', '伤心', '愤怒', '焦虑', '孤独', '幸福'}:
            return 'emotion'
        if len(name) <= 4 and name in {'牛顿', '爱因斯坦', '特斯拉', '达尔文', '孔子'}:
            return 'person'
        if name.endswith('法') or name.endswith('术'):
            return 'method'
        return 'concept'

    def _assess_complexity(self, text: str) -> dict:
        """评估复杂度，用于决定使用何种思考模式"""
        factors = []
        score = 1

        if any(kw in text for kw in ['和', '与', '及', '以及', '、']):
            factors.append('multi_topic')
            score += 1
        if re.search(r'为什么|怎么|如何|怎样', text):
            factors.append('causal')
            score += 1
        if len(text) > 15:
            factors.append('long_query')
            score += 1
        if re.search(r'如果.*(?:那么|就|则)', text):
            factors.append('conditional')
            score += 1
        if re.search(r'但|不过|然而|虽然|尽管', text):
            factors.append('contrastive')
            score += 1

        level = 'simple' if score <= 2 else 'medium' if score <= 3 else 'complex'
        return {'level': level, 'score': score, 'factors': factors}

    def _extract_keywords(self, text: str) -> list:
        """提取关键词"""
        tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*|[\u4e00-\u9fff]', text)
        seen = set()
        result = []
        for t in tokens:
            if t not in STOPWORDS and len(t) >= 2 and t not in seen:
                seen.add(t)
                result.append(t)
        return result

    def is_followup(self, text: str, current_topics: list) -> bool:
        """判断是否是追问"""
        markers = {'然后', '还有', '继续', '那', '所以', '那么',
                   '它', '他们', '它们', '这个', '那个', '这些'}
        has_marker = any(m in text for m in markers)
        no_new_topic = not bool(self._extract_keywords(text))
        if not current_topics:
            return False
        if len(text) <= 10 and has_marker:
            return True
        if has_marker and no_new_topic:
            return True
        return False

    def get_question_format(self, text: str) -> str | None:
        """获取问题格式（用于自我认知响应）"""
        if re.search(r'(?:你|自己).*是(?:谁|什么|干嘛的|做什么)', text):
            return 'identity_who'
        if re.search(r'(?:你|自己).*(?:名字|叫)', text):
            return 'identity_name'
        if re.search(r'(?:你|自己).*(?:能力|功能|作用|用处|特点|可以|能)', text):
            return 'capability'
        if re.search(r'(?:你|自己).*(?:知道|懂|会|有)', text):
            return 'knowledge_scope'
        if re.search(r'(?:你|自己).*(?:状态|感觉|心情|情绪|怎么样|如何)', text):
            return 'state_inquiry'
        return None

    def should_route_to_fast(self, intent: str, complexity: dict) -> bool:
        """判断是否应该走 fast 模式"""
        if intent in ('greeting',):
            return True
        if complexity['level'] == 'simple' and intent in ('general', 'emotion'):
            return True
        return False

    def should_route_to_cot(self, intent: str, complexity: dict) -> bool:
        """判断是否应该走 CoT 模式"""
        if intent in ('causal', 'comparison', 'definition'):
            return True
        if complexity['level'] in ('medium',) and intent not in ('greeting',):
            return True
        return False

    def should_route_to_deep(self, intent: str, complexity: dict) -> bool:
        """判断是否应该走 deep 模式"""
        if complexity['level'] == 'complex':
            return True
        if intent in ('knowledge_query',) and complexity['level'] == 'medium':
            return True
        return False
