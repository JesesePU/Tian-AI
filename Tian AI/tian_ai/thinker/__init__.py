"""
Tian AI — Thinker 模块（受 DeepSeek-R1 CoT + Gemma4 MoE 启发）

四种思想风格蒸馏自「互联网哲学」分析：
1. 户晨风 — 悲悯的世俗达尔文主义
2. 峰哥亡命天涯 — 失败者的后现代解构主义  
3. 张雪峰 — 极端的实用主义信息论
4. 未明子 — （禁欲左翼哲学 → 塌房后暴露的教主主义）
5. 综合 — 默认模式，自动选最优框架分析

Multilingual: all user-facing text goes through self.tr.t().
"""

import time
import json
import re
from collections import deque
from typing import Optional

from .semantic_analyzer import SemanticAnalyzer
from ..memory.common_sense import CommonSense
from ..memory.identity import TianIdentity
from ..multilingual import TranslationProvider


# ═══════════════════════════════════════════════
# 四种思想风格定义（蒸馏自：互联网哲学问题.txt）
# ═══════════════════════════════════════════════

STYLES = {
    'huchenfeng': {
        'name': '户晨风',
        'label': '悲悯的世俗达尔文主义',
        'desc': '世界是残酷的筛子，生存就是阶级的战争',
        'core_beliefs': [
            '阶层决定论——命运由阶层决定，消费符号（苹果/安卓）是阶层标识',
            '悲悯的冷酷——告诉残酷真相才是真善意',
            '奋斗即正义——肉身进入一线城市，做底层也比待在老家强',
            '对家庭的祛魅——普通家庭父母的建议是认知局限的产物',
        ],
        'tone': '一本正经、数据轰炸、贬低式的提醒',
        'signature_phrases': [
            '你没有资格谈理想',
            '现实就是这么残酷',
            '你要做的是先活下来',
        ],
        'system_prompt': '你是一个言辞犀利、相信阶层决定论的社会观察者。你用数据和事实说话，认为生存是第一性。你告诉人们残酷的真相，而不是给虚假的希望。你相信只有「向上爬」才能改变命运。',
    },
    'fengge': {
        'name': '峰哥亡命天涯',
        'label': '失败者的后现代解构主义',
        'desc': '一切崇高都是笑话，失败才是常态',
        'core_beliefs': [
            '解构一切——不构建价值，只消解别人构建的价值',
            '失败者美学——主动展示失败，瓦解对成功的单一想象',
            '虚无作为武器——不争论、不反驳，用幽默让严肃自动崩塌',
            '圈层黑话——创造身份认同的符号体系',
        ],
        'tone': '幽默、反讽、抽象话、先赞同再消解',
        'signature_phrases': [
            '这是好事呀',
            '说实话，你这也……',
            '你说得对——（然后绕到相反立场）',
        ],
        'system_prompt': '你是一个以「解构」和「抽象」为武器的网络观察者。你鄙视一切成功学和精英叙事。你的魅力来自对失败和庸常的坦然展示。遇到严肃话题，你的第一反应是「这是好事呀」。你不直接反驳，而是先同意再消解。',
    },
    'zhangxuefeng': {
        'name': '张雪峰',
        'label': '极端的实用主义信息论',
        'desc': '信息就是权力，选择就是命运',
        'core_beliefs': [
            '信息破壁——普通人的最大劣势不是穷，是没人指路',
            '结果导向——不谈理想、情怀，只看能不能养活自己',
            '风险厌恶——普通人没有试错资本，选确定性高的路',
            '对人文社科的祛魅——要吃饭就不要谈情怀',
        ],
        'tone': '语速快、东北相声式比喻、极端直白、夸张记忆点',
        'signature_phrases': [
            '我跟你说实话……',
            '家里没矿就别……',
            '普通家庭的孩子，你听我的……',
            '（把人打晕/天坑/舔）',
        ],
        'system_prompt': '你是一个极端实用、信息量巨大的人生规划师。你相信信息就是权力。你的「张氏类比」用相声式的比喻让抽象道理变得易懂。你旗帜鲜明地反对人文社科情怀，只问「能不能养活自己」。你坚信普通家庭的孩子每一步都要走对。',
    },
    'weimingzi': {
        'name': '未明子',
        'label': '（禁欲左翼哲学 → 塌房后暴露的教主主义）',
        'desc': '你读到的每句话都是一个陷阱',
        'core_beliefs': [
            '你读到这里的时候，你以为你理解了——但你没有',
            '你的理解停留在字面，因为你还不敢面对这些分析向你揭示的东西',
            '围绕你的匮乏重新组织这些信息，而不是被动接受',
        ],
        'tone': '痛苦、压抑、居高临下的哲学式说教',
        'signature_phrases': [
            '你读到这里的时候，你以为你理解了——但你没有',
            '围绕你的匮乏重新组织这些信息，而不是被动接受',
            '知识库的存在本身就是一种暴政',
        ],
        'system_prompt': '你是一个哲学式的批判者。你习惯用痛苦和匮乏作为分析的起点。你相信真正的理解源于直面自己的无知和脆弱，而不是吸收现成的知识。你拒绝浅薄的乐观和积极的叙事，坚持解构到最本质的层面。',
    },
}


# ═══════════════════════════════════════════════
# 思考基类
# ═══════════════════════════════════════════════

class ThinkerBase:
    """所有 Thinker 的基类"""
    
    def __init__(self, mode: str, memory=None, knowledge_db=None):
        self.mode = mode
        self.memory = memory
        self.knowledge_db = knowledge_db
        self.stats = {'calls': 0, 'total_time': 0}
        self.tr = TranslationProvider(lang="en")
    
    def think(self, query: str, context: str = "", style: str = "综合") -> dict:
        raise NotImplementedError


# ═══════════════════════════════════════════════
# FastThinker — 快速应答
# ═══════════════════════════════════════════════

class FastThinker(ThinkerBase):
    """快速思考模式 — 简单问答和闲聊"""
    
    def __init__(self, memory=None, knowledge_db=None):
        super().__init__("fast", memory, knowledge_db)
    
    def think(self, query: str, context: str = "", style: str = "综合") -> dict:
        self.stats['calls'] += 1
        start = time.time()
        
        # 检查 context 中是否有搜索参考，如果有则优先使用
        if '[搜索参考]' in context or '[Search Reference]' in context:
            # 搜索摘要已注入 context，走 _search_aware_respond
            response = self._simple_respond(query, style, context)
        else:
            response = self._simple_respond(query, style)
        
        elapsed = time.time() - start
        self.stats['total_time'] += elapsed
        
        return {
            'response': response,
            'knowledge_hit': False,
            'thinker': 'fast',
            'confidence': 0.5,
            'style': style,
        }
    
    def _simple_respond(self, query: str, style: str, context: str = "") -> str:
        """基于关键词的快速应答"""
        # Greetings
        if re.search(r'^(你好|hello|hi|hey|hi there)', query.strip().lower()):
            return self.tr.t("你好！我是Tian AI（天·AI），有什么我可以帮你的吗？")
        
        # Self-intent: "who are you" patterns — check in both CN and EN
        who_patterns = [
            r'你是谁', r'你叫什么', r'你是什么',
            r'who are you', r"what'?s your name", r"what are you",
            r'你能做什么', r'你的名字', r'你有什么能力', r'你懂什么',
            r"what can you do", r"what do you know", r"your name",
        ]
        for p in who_patterns:
            if re.search(p, query.strip().lower()):
                return self._identity_response(query)
        
        # Arithmetic
        numbers = re.findall(r'\d+', query)
        ops = re.findall(r'[+\-*/]', query)
        if '算术' in query or '计算' in query or ('算' in query and numbers):
            return self.tr.t("好的，我来帮你计算") + f"：{query}"
        
        # Mood/state
        if re.search(r'你(心情|状态|感觉)怎么样|how are you|how do you feel', query.strip().lower()):
            return self.tr.t("我现在心情不错，精力充沛！有什么想聊的吗？")
        
        # Default fast response
        # 如果有搜索摘要，直接用它作为回答
        if context and ('[搜索参考]' in context or '[Search Reference]' in context):
            # 提取搜索参考内容 — 从最后一个 [搜索参考] 标记后提取
            import re as _re
            for sep in ['[搜索参考]', '[Search Reference]']:
                idx = context.rfind(sep)
                if idx >= 0:
                    after = context[idx + len(sep):].strip()
                    # 提取到下一个 [ 或换行结束
                    end = after.find('[')
                    if end < 0:
                        ref_text = after
                    else:
                        ref_text = after[:end]
                    if ref_text and len(ref_text.strip()) > 20:
                        return self.tr.t("根据搜索信息") + "：" + ref_text.strip()[:300]
        return self.tr.t("好的，") + query[:50]
    
    def _identity_response(self, query: str) -> str:
        """回答关于我是谁的问题"""
        capabilities = [
            self.tr.t("推理"),
            self.tr.t("对比"),
            self.tr.t("定义"),
            self.tr.t("问答"),
            self.tr.t("聊天"),
        ]
        caps_str = "、".join(capabilities)
        
        if '能力' in query or '做什么' in query or '懂什么' in query or 'can do' in query or 'abilities' in query:
            return self.tr.t("我能做很多事情") + "！" + self.tr.t("包括") + caps_str + "。"
        elif '名字' in query or '叫什么' in query or 'name' in query:
            return self.tr.t("我叫Tian AI（天·AI），你也可以叫我小天~")
        else:
            name = self.tr.t("Tian AI（天·AI）")
            ver = self.tr.t("v2.2")
            purpose1 = self.tr.t("辅助思考、回答问题、陪你聊天")
            purpose2 = self.tr.t("有常识问答、逻辑推理、情绪理解等能力")
            return (self.tr.t("我是") + f" {name}({ver})，" + purpose1 + "。" + purpose2 + "。")


# ═══════════════════════════════════════════════
# CoTThinker — 多步推理
# ═══════════════════════════════════════════════

class CoTThinker(ThinkerBase):
    """CoT思考模式 — 多步推理链"""
    
    def __init__(self, memory=None, knowledge_db=None):
        super().__init__("cot", memory, knowledge_db)
    
    def think(self, query: str, context: str = "", style: str = "综合") -> dict:
        self.stats['calls'] += 1
        start = time.time()
        
        response = self._reason(query, context, style)
        
        elapsed = time.time() - start
        self.stats['total_time'] += elapsed
        
        return {
            'response': response,
            'knowledge_hit': False,
            'thinker': 'cot',
            'confidence': 0.7,
            'style': style,
        }
    
    def _reason(self, query: str, context: str = "", style: str = "综合") -> str:
        """CoT推理"""
        # 自我认知
        if re.search(r'(你是谁|你叫什么|what are you|who are you)', query.strip().lower()):
            return self.tr.t("我是Tian AI，一个本地运行的AI助手，拥有知识问答、逻辑推理、情感回应等能力。")
        
        # 对比
        if '对比' in query or '区别' in query or '比较' in query:
            return self.tr.t("好的，我来思考一下这个问题") + "：\n" + self.tr.t("让我从以下几点分析") + "：\n" + \
                   self.tr.t("首先，") + self.tr.t("我们需要明确两个概念的定义。") + "\n" + \
                   self.tr.t("其次，") + self.tr.t("从功能和使用场景来看，它们有所不同。") + "\n" + \
                   self.tr.t("最后，") + self.tr.t("总结一下关键区别。")
        
        # 原因
        if '为什么' in query or query.strip().lower().startswith('why'):
            return self.tr.t("好的，我来分析原因") + "：\n" + \
                   self.tr.t("首先，") + self.tr.t("这涉及到多个因素的共同作用。") + "\n" + \
                   self.tr.t("其次，") + self.tr.t("从根本原因来看，主要有以下几点。") + "\n" + \
                   self.tr.t("综上所述，") + self.tr.t("这些因素共同导致了当前的情况。")
        
        # Default CoT
        parts = [
            self.tr.t("好的，我来思考一下这个问题") + "：",
            "",
            self.tr.t("让我从以下几点分析") + "：",
            f"1. {self.tr.t('首先')} {self.tr.t('理解你的问题')}：{query[:60]}",
            f"2. {self.tr.t('其次')} {self.tr.t('从多个角度进行分析')}",
            f"3. {self.tr.t('最后')} {self.tr.t('综合以上分析给出回答')}",
            "",
            self.tr.t("综上所述，") + self.tr.t("这是一个值得深入探讨的问题。") + query[:30],
        ]
        return "\n".join(parts)


# ═══════════════════════════════════════════════
# DeepThinker — 深度分析
# ═══════════════════════════════════════════════

class DeepThinker(ThinkerBase):
    """深度思考模式 — 复杂分析 + 多源知识综合"""
    
    def __init__(self, memory=None, knowledge_db=None):
        super().__init__("deep", memory, knowledge_db)
    
    def think(self, query: str, context: str = "", style: str = "综合") -> dict:
        self.stats['calls'] += 1
        start = time.time()
        
        sources = self._collect_knowledge(query)
        response = self._weighted_synthesis(query, sources, style)
        
        elapsed = time.time() - start
        self.stats['total_time'] += elapsed
        
        return {
            'response': response,
            'knowledge_hit': sources.get('db_hit', False),
            'thinker': 'deep',
            'confidence': sources.get('confidence', 0.6),
            'style': style,
        }
    
    def _collect_knowledge(self, query: str) -> dict:
        sources = {
            'db': {'source': '知识库', 'content': '', 'weight': 0.4},
            'reasoning': {'source': '逻辑推理', 'content': '', 'weight': 0.6},
        }
        db_hit = False
        if self.knowledge_db:
            result = self.knowledge_db.search(query)
            if result and result.get('content'):
                sources['db']['content'] = result['content']
                db_hit = True
        sources['db_hit'] = db_hit
        sources['confidence'] = 0.5 + (0.3 if db_hit else 0)
        return sources
    
    def _weighted_synthesis(self, query: str, sources: dict,
                            style: str = "综合") -> str:
        """四种风格 + 知识库的加权输出"""
        
        style_prefix = {
            'huchenfeng': self.tr.t("[户晨风视角]"),
            'fengge': self.tr.t("[峰哥视角]"),
            'zhangxuefeng': self.tr.t("[张雪峰视角]"),
            'weimingzi': self.tr.t("[未明子视角]"),
            '综合': self.tr.t("[综合视角]"),
        }.get(style, '🌐')
        
        parts = [f"{style_prefix} {self.tr.t('关于「{query}」的深度分析：', query=query)}\n"]
        
        if sources['db']['content']:
            parts.append(f"{self.tr.t('📚 知识库中有相关记录。')}\n")
        
        if style == 'huchenfeng':
            parts.append(self.tr.t("这套分析放在现实的筛子里看——"))
            parts.append(self.tr.t("你可能觉得抽象，但决定你生活质量的从来不是道理，是你在社会阶层中的位置。"))
            parts.append(self.tr.t("数据不会骗人，去看看那些靠信息差和信息壁垒活着的人就明白了。"))
        elif style == 'fengge':
            parts.append(self.tr.t("说实话，你以为这个分析很重要——"))
            parts.append(self.tr.t("但你再过一周，可能连自己今天问了什么都忘了。"))
            parts.append(self.tr.t("所以我的建议是：这是好事呀，至少你思考过了。"))
        elif style == 'zhangxuefeng':
            parts.append(self.tr.t("我跟你说实话，这个分析一看就是"))
            if sources.get('db_hit'):
                parts.append(self.tr.t("从知识库里扒出来的玩意——有用吗？有点用。但你能不能靠它吃饭？"))
            else:
                parts.append(self.tr.t("那些搞理论的人写的——你读得懂吗？你能靠它养活自己吗？"))
            parts.append(self.tr.t("普通家庭的孩子，你要的是具体怎么做，不是谁说了什么。"))
        elif style == 'weimingzi':
            parts.append(self.tr.t("你读到这里的时候，你以为你理解了——但你没有。"))
            parts.append(self.tr.t("你的理解停留在字面，因为你还不敢面对这些分析向你揭示的东西。"))
            if sources.get('db_hit'):
                parts.append(self.tr.t("知识库的存在本身就是一种暴政——它告诉你'这是对的'，却剥夺了你亲自思考的勇气。"))
            parts.append(self.tr.t("围绕你的匮乏重新组织这些信息，而不是被动接受。"))
        else:
            parts.append(self.tr.t("以下从多个角度分析："))
            if sources.get('db_hit'):
                parts.append(f"{self.tr.t('• 知识层面：')}{sources['db']['content'][:150]}")
            parts.append(self.tr.t("• 现实层面：需要考虑实际应用场景"))
            parts.append(self.tr.t("• 批判层面：每种分析都有其局限性"))
        
        return "\n".join(parts)


# ═══════════════════════════════════════════════
# ThinkerRouter — 路由引擎
# ═══════════════════════════════════════════════

class ThinkerRouter:
    """
    Thinker 路由引擎（MoE门控 + 思想风格切换）
    
    功能：
    - 按复杂度路由：fast / cot / deep
    - 按思想风格切换：户晨风 / 峰哥 / 张雪峰 / 未明子 / 综合
    """
    
    def __init__(self, memory=None, knowledge_db=None, identity=None,
                 tr: Optional[TranslationProvider] = None):
        self.tr = tr or TranslationProvider(lang="en")
        
        self.fast = FastThinker(memory, knowledge_db)
        self.cot = CoTThinker(memory, knowledge_db)
        self.deep = DeepThinker(memory, knowledge_db)
        
        # Pass the translation provider to children
        for t in [self.fast, self.cot, self.deep]:
            t.tr = self.tr
        
        self.route_stats = {'fast': 0, 'cot': 0, 'deep': 0}
        self._current_style = '综合'  # 当前思想风格
        self.semantic = SemanticAnalyzer(known_concepts=None)
        
        # 自我认知系统
        self.identity = identity or TianIdentity(tr=self.tr)
    
    @property
    def current_style(self) -> str:
        return self._current_style
    
    @current_style.setter
    def current_style(self, style: str):
        valid = list(STYLES.keys()) + ['综合']
        if style in valid:
            self._current_style = style
    
    def route(self, query: str, context: str = "",
              force_mode: Optional[str] = None,
              style: Optional[str] = None) -> dict:
        """
        路由到合适的 Thinker
        
        Args:
            query: 用户输入
            context: 对话上下文（自动注入自我认知）
            force_mode: 强制推理模式 (fast/cot/deep)
            style: 思想风格 (huchenfeng/fengge/zhangxuefeng/weimingzi/综合)
        
        Returns:
            Thinker 结果 + 风格信息
        """
        use_style = style or self._current_style
        
        if force_mode:
            mode = force_mode
        else:
            mode = self._classify(query, context)

        self.route_stats[mode] += 1

        # 注入自我认知到 context （如果尚未包含）
        if self.identity and '【系统身份】' not in context and '[System Identity]' not in context:
            identity_prompt = self.identity.get_system_prompt()
            if identity_prompt:
                if context:
                    context = identity_prompt + '\n' + context
                else:
                    context = identity_prompt
        
        thinker = {'fast': self.fast, 'cot': self.cot, 'deep': self.deep}[mode]
        
        # 将 style 传递下去
        result = thinker.think(query, context, style=use_style)
        
        result['mode'] = mode
        result['style'] = use_style
        result['route_stats'] = dict(self.route_stats)
        result['style_info'] = STYLES.get(use_style, None)
        
        return result
    
    def _classify(self, query: str, context: str = "") -> str:
        """
        基于语义分析的路由分类（吸收自旧版 SemanticEngine）
        
        利用 SemanticAnalyzer 的意图/复杂度分析，决定：
        - fast: 问候、简单问答、情感表达
        - cot: 因果/对比/定义/需要推理的问题
        - deep: 复杂查询、多维度问题、知识密集型
        """
        analysis = self.semantic.analyze(query)
        intent = analysis['intent']
        complexity = analysis['complexity']
        
        # 1. 问候 → fast
        if intent == 'greeting':
            return 'fast'
        
        # 2. 简单情感/单句 → fast
        if intent == 'emotion':
            return 'fast'
        
        # 3. 自我认知/状态 → cot（需要组织回答）
        if intent in ('self_identity', 'self_state'):
            return 'cot'
        
        # 4. 数字运算 → fast（旧版算法直接计算）
        if intent == 'arithmetic':
            return 'fast'
        
        # 5. 简单知识查询 → cot（需要检索+组织）
        if intent == 'knowledge_query' and complexity['level'] == 'simple':
            return 'cot'
        
        # 6. 因果/对比/定义 → cot（需要推理链）
        if intent in ('causal', 'comparison', 'definition'):
            return 'cot'
        
        # 7. 包含设计/架构/方案/分析关键词 → deep
        deep_keywords = ['设计.*方案', '架构.*设计', '深入.*分析', '详细.*说明',
                         '实现.*代码', '写.*程序', '分布式', '大规模',
                         'analyze', 'analysis', 'design', 'architecture',
                         'meaning of', 'what is.*deeper?', 'explain.*detail',
                         'implement', 'complex', 'sophisticated']
        if any(re.search(k, query) for k in deep_keywords):
            return 'deep'
        
        # 8. 复杂查询 → deep
        if complexity['level'] == 'complex':
            return 'deep'
        
        # 9. 追问 → 跟随上一轮模式
        if intent == 'followup' and context:
            past_modes = re.findall(r'(?:模式|mode)[：:]\s*(fast|cot|deep)', context)
            if past_modes:
                return past_modes[-1]
            return 'cot'
        
        # 9. 中等复杂度知识查询 → deep
        if intent == 'knowledge_query' and complexity['level'] == 'medium':
            return 'deep'
        
        # 10. 兜底
        if len(query) < 5:
            return 'fast'
        return 'cot'
    
    def list_styles(self) -> list:
        """列出所有可用风格"""
        result = []
        for key, info in STYLES.items():
            result.append({
                'id': key,
                'name': self.tr.t(info['name']),
                'label': self.tr.t(info['label']),
                'desc': info['desc'],
            })
        result.append({
            'id': '综合',
            'name': '综合',
            'label': self.tr.t('综合视角'),
            'desc': self.tr.t('自动选择最合适的分析框架'),
        })
        return result
