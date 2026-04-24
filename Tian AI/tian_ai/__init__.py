"""
Tian AI M1 — 核心入口（TianAI 主类）
Thinker-Talker 分离架构主调度器

M1 正式版 — 三层付费体系：
  - Free  : 不限提问 + 每天10图片/音频
  - Pro   : 深度思考 + 每周50额度
  - Plus  : 月卡/年卡不限量

高级进化：
  - 持续搜索和学习，累计经验值 (XP)
  - 达到里程碑自动更新模型版本 (M1.0 → M1.1 → M1.2 ...)
  - 跟踪话题探索深度

用法：
    from tian_ai import TianAI
    ai = TianAI()
    result = ai.chat("Hello!")
"""

import time
import re
from typing import Optional, Any

from .multilingual import TranslationProvider, set_language
from .thinker import ThinkerRouter
from .talker import TalkerRouter
from .search import search_and_summarize
from .memory import KnowledgeBase, EmotionalState, ShortTermMemory, LongTermMemory
from .memory.identity import TianIdentity, MOODS, MOOD_EMOJI, MOOD_ENERGY, SELF_IDENTITY
from .tier import TierManager
from .evolution import EvolutionEngine
from .auth import AuthSystem


__version__ = "M1.0"
__all__ = ["TianAI"]


class TianAI:
    """
    Tian AI M1 — 全能型本地AI主类

    Thinker-Talker 分离架构，集成：
    - 四种思想风格（户晨风/峰哥/张雪峰/未明子/综合）
    - 三种推理模式（Fast/Cot/Deep）
    - 34GB 知识库检索
    - 联网搜索（DuckDuckGo）
    - 情绪感知和理解
    - 多语言支持（默认英文）
    - 短期/长期记忆
    - 三层付费体系（Free/Pro/Plus）
    - 高级进化（持续学习，自动更新版本）
    """

    def __init__(self,
                 knowledge_db_path: str = 'knowledge_base.db',
                 memory_store_path: str = 'memory_store.json',
                 lang: str = "en",
                 enable_search: bool = True):

        # ── 翻译器（默认英文） ──
        self.tr = TranslationProvider(lang=lang)
        set_language(lang)

        # ── 自我认知 ──
        self.identity = TianIdentity(tr=self.tr)

        # ── 付费体系 ──
        self.tier = TierManager(tr=self.tr)

        # ── 高级进化 ──
        self.evolution = EvolutionEngine(tr=self.tr)

        # ── 用户登录 ──
        self.auth = AuthSystem(tr=self.tr)

        # ── 知识库 ──
        self.knowledge_db = None
        try:
            self.knowledge_db = KnowledgeBase(knowledge_db_path)
        except Exception:
            pass  # 可离线运行

        # ── 记忆系统 ──
        self.short_term = ShortTermMemory(maxlen=10)
        self.long_term = LongTermMemory(path=memory_store_path)
        self.emotion_state = EmotionalState()

        # ── 推理引擎 ──
        self.thinker = ThinkerRouter(
            memory=self.short_term,
            knowledge_db=self.knowledge_db,
            identity=self.identity,
            tr=self.tr,
        )
        self.talker = TalkerRouter(
            identity=self.identity,
            tr=self.tr,
        )

        # ── 搜索模块标志 ──
        self.enable_search = enable_search
        self._search_cache = {}

    # ═══════════════════════════════════════════════
    # 语言切换
    # ═══════════════════════════════════════════════

    def set_language(self, lang: str):
        """切换语言: 'en' (English) or 'zh' (中文)."""
        self.tr.lang = lang
        # 同步到所有子模块
        for obj in [self.identity, self.thinker, self.talker, self.tier, self.evolution, self.auth]:
            if hasattr(obj, 'tr'):
                obj.tr.lang = lang
        for t in [self.thinker.fast, self.thinker.cot, self.thinker.deep]:
            if hasattr(t, 'tr'):
                t.tr.lang = lang
        if hasattr(self.talker, 'dialog') and hasattr(self.talker.dialog, 'tr'):
            self.talker.dialog.tr.lang = lang

    @property
    def language(self) -> str:
        return self.tr.lang

    # ═══════════════════════════════════════════════
    # 核心对话循环
    # ═══════════════════════════════════════════════

    def chat(self, user_input: str,
             force_mode: str = None,
             style: str = None,
             enable_search: bool = None) -> dict:
        """
        处理用户输入并返回响应。

        Args:
            user_input: 用户输入文本
            force_mode: 强制推理模式 (fast/cot/deep)
            style: 思想风格 (huchenfeng/fengge/zhangxuefeng/weimingzi/综合)
            enable_search: 是否启用联网搜索补充（默认使用实例设置）

        Returns:
            {
                'response': str,          # 最终输出文本
                'thinker_mode': str,      # 使用的推理模式
                'style': str,             # 使用的思想风格
                'knowledge_hit': bool,    # 知识库是否命中
                'processing_time': str,   # 处理耗时
                'emotion': str,           # 检测到的情绪
                'search_used': bool,      # 是否使用了搜索
            }
        """
        start = time.time()

        # 1. 分析意图（快速语义分类）
        intent = self._detect_intent(user_input)

        # 2. 情绪分析（更新自我认知）
        emotion_result = self.emotion_state.analyze_user_text(user_input)
        if emotion_result and emotion_result.get('has_emotion'):
            self.identity.update_mood(
                emotion_result.get('intensity', 0),
                emotion_result.get('dominant', {}).get('emotion') or emotion_result.get('emotion')
            )

        # 3. 知识库检索（简单查询先查一次）
        knowledge = None
        if self.knowledge_db:
            knowledge = self.knowledge_db.search(user_input)

        # 4. 联网搜索补充（当知识库未命中或搜索开启）
        search_used = False
        use_search = enable_search if enable_search is not None else self.enable_search
        if use_search:
            # 快速判断是否需要搜索：简单问候/自我介绍/基础运算不需要
            _search_lower = user_input.strip().lower()
            _greetings = {'hello', 'hi', 'hey', '你好', '嗨', '早上好', '下午好', '晚上好',
                         'good morning', 'good afternoon', 'good evening', 'good night',
                         'who are you', 'what are you', '你是谁', '你叫什么'}
            _skip_search = (
                len(_search_lower.split()) <= 3
                and any(g == _search_lower or _search_lower.startswith(g) for g in _greetings)
            ) or (
                # 简单计算/问时间/表白/闲聊等不需要搜索
                bool(re.search(r'\d+\s*[+\-*/]\s*\d+', _search_lower))
                or _search_lower in ('2+2', '1+1')
                or any(_search_lower.startswith(w) for w in ('what time', 'what day', 'i love', 'i like'))
            )
            if not _skip_search and (not knowledge or intent == 'knowledge_query'):
                search_summary = self._safe_search(user_input)
                if search_summary:
                    search_used = True
                    # 追加到短期记忆作为临时上下文
                    self.short_term.add('system', search_summary)

        # 5. 走 Thinker-Talker 管线
        # 先确定模式（force_mode 优先级最高，否则自动分类）
        # 同时检查 tier 是否允许 deep thinking
        auto_mode = self.thinker._classify(user_input)
        if auto_mode in ('deep', 'cot') and not self.tier.has_deep_thinking:
            auto_mode = 'fast'  # Free tier → no deep thinking
        thinker_mode = force_mode or auto_mode
        if thinker_mode in ('deep', 'cot') and not self.tier.has_deep_thinking:
            thinker_mode = 'fast'  # enforce tier restriction

        # 注入情绪状态到上下文
        context = ""
        if emotion_result and emotion_result.get('has_emotion'):
            mood_str = self.tr.t(self.identity.mood) if self.tr.lang == 'en' else self.identity.mood
            dominant = emotion_result.get('dominant', {}) or {}
            empathy = emotion_result.get('empathy', '') or ''
            context = (
                f"[{self.tr.t('情绪')}] {mood_str} "
                f"[{self.tr.t('能量')}] {self.identity.energy:.1f} "
                f"[{self.tr.t('好奇心')}] {self.identity.curiosity_level:.1f}"
            )
            if empathy:
                context += f"\n{self.tr.t('[共情]')} {empathy}"

        talker_result = self.talker.route(
            user_input,
            thinker=self.thinker,
            emotion_state=self.emotion_state,
            force_mode=thinker_mode,  # 传递 force_mode 确保 deep/cot 不走 talker 的 _detect_mode
            search_context=search_summary if search_used else '',
        )

        # 6. 更新状态
        self.identity.on_interaction(user_input, talker_result.get('response', ''))
        self.identity.update_state()

        # 7. 记录进化经验值
        milestone = self.evolution.record_interaction(
            query=user_input,
            mode=talker_result.get('thinker_mode', thinker_mode),
            knowledge_hit=bool(knowledge),
            search_used=search_used,
        )
        if milestone:
            new_ver = milestone['version_display']
            # 版本自动更新！记录到长期记忆
            self.long_term.facts[f"evolution:version_upgrade:{new_ver}"] = {
                'new_version': new_ver,
                'time': time.time(),
                'total_xp': self.evolution.total_xp,
            }
            self.long_term.save()

            # 进化升级奖励：所有活跃Pro/Plus用户获得1个月免费Plus升级
            self.tier.grant_evolution_plus(days=30)
            self.long_term.facts[f"evolution:upgrade_bonus:{new_ver}"] = {
                'granted_plus_days': 30,
                'time': time.time(),
            }
            self.long_term.save()

        # 8. 记录 tier 使用量
        self.tier.record_usage('chat')
        if thinker_mode == 'deep':
            self.tier.record_usage('deep')

        # 9. 如果搜索有结果，记录到长期记忆（知识库未命中时）
        if search_used and not knowledge:
            self.long_term.facts[f"search:{user_input[:50]}"] = {
                'query': user_input,
                'time': time.time(),
            }
            self.long_term.save()

        elapsed = time.time() - start

        return {
            'response': talker_result.get('response', ''),
            'thinker_mode': talker_result.get('thinker_mode', thinker_mode),
            'style': talker_result.get('style', style or '综合'),
            'knowledge_hit': bool(knowledge),
            'processing_time': f"{elapsed:.3f}s",
            'emotion': self.identity.mood,
            'search_used': search_used,
            'version': self.evolution.version,
            'tier': self.tier.tier_display,
        }

    def _detect_intent(self, text: str) -> str:
        """快速意图分类"""
        t = text.strip().lower()
        if re.search(r'^(你好|hello|hi|hey)', t):
            return 'greeting'
        if re.search(r'(你是谁|你叫什么|what are you|who are you)', t):
            return 'self_identity'
        if re.search(r'(心情|状态|感觉|how are you|how do you feel)', t):
            return 'self_state'
        if re.search(r'(什么|what|how|why|when|where)', t) or re.search(r'[?？]', t):
            return 'knowledge_query'
        if re.search(r'[+\-*/]', t) and re.search(r'\d+', t):
            return 'arithmetic'
        if re.search(r'(难[过受]?|开心|生气|伤心|[不很]?好|sad|happy|angry)', t):
            return 'emotion'
        return 'chat'

    def _safe_search(self, query: str) -> str:
        """安全搜索（带缓存和限流保护）"""
        cache_key = query.strip().lower()[:50]
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]
        try:
            result = search_and_summarize(query)
            self._search_cache[cache_key] = result
            return result
        except Exception:
            return ""

    # ═══════════════════════════════════════════════
    # 风格管理
    # ═══════════════════════════════════════════════

    def set_style(self, style: str):
        """设置思想风格: huchenfeng / fengge / zhangxuefeng / weimingzi / 综合"""
        self.thinker.current_style = style

    def list_style_names(self) -> list:
        """列出所有可用风格名"""
        return self.thinker.list_styles()

    # ═══════════════════════════════════════════════
    # 状态报告
    # ═══════════════════════════════════════════════

    def get_status(self) -> str:
        """生成完整状态报告（多语言支持）"""
        tr = self.tr

        # 身份信息（已翻译）
        name = tr.t("Tian AI")
        emoji = MOOD_EMOJI.get(self.identity.mood, '😊')
        state = self.identity.get_state_summary()

        # 知识库状态
        kb_status = tr.t("💾 已连接") if (self.knowledge_db and self.knowledge_db.conn) else tr.t("⚠️ 未连接")

        # 统计
        route_stats = self.thinker.route_stats
        total_calls = sum(route_stats.values())
        cached_searches = len(self._search_cache)

        # 进化信息
        evo = self.evolution.get_status()
        evo_bar_len = 12
        evo_filled = int(evo['progress'] * evo_bar_len)
        evo_bar = '█' * evo_filled + '░' * (evo_bar_len - evo_filled)

        # Tier info
        tier_info = self.tier.get_status()

        lines = [
            f"═══ {name} {evo['version_display']} ({tr.t('M1 正式版')}) {tr.t('状态报告')} ═══",
            "",
            f"🔹 {tr.t('身份')}: {tr.t(self.identity.mood)} {emoji} | "
            f"{tr.t('能量')}: {self.identity.energy:.1f} | "
            f"{tr.t('好奇心')}: {self.identity.curiosity_level:.1f} | "
            f"{tr.t('动机')}: {tr.t(state.get('current_motive', ''))}",
            f"🔹 {tr.t('语言')}: {'English' if tr.lang == 'en' else '中文'}",
            "",
            f"💳 {tr.t('许可')}: {tier_info['tier_display']} "
            f"{'(' + tr.t('深度思考') + ' ✓)' if tier_info['has_deep_thinking'] else ''}",
            f"📈 {tr.t('进化')}: {evo['version_display']} [{evo_bar}] "
            f"{evo['xp']}/{evo['milestone_xp']} XP",
            f"   {tr.t('交互')}: {evo['total_interactions']}{tr.t('次')} | "
            f"{tr.t('话题')}: {evo['topics_count']} | "
            f"{tr.t('升级次数')}: {evo['version_updates']}",
            "",
            f"📚 {tr.t('知识库')}: {kb_status}",
            f"🌐 {tr.t('搜索')}: {'ON' if self.enable_search else 'OFF'} ({tr.t('缓存')}: {cached_searches})",
            "",
            f"🧠 {tr.t('思考者')}: {total_calls} {tr.t('总调用')} "
            f"(fast:{route_stats.get('fast', 0)}, "
            f"cot:{route_stats.get('cot', 0)}, "
            f"deep:{route_stats.get('deep', 0)})",
            f"💡 {tr.t('风格')}: {tr.t(self.thinker.current_style)}",
            f"🗣️ {tr.t('对话轮次')}: {len(self.talker.dialog.turns)}",
            "",
            f"📝 {tr.t('短期记忆')}: {len(self.short_term.messages)} {tr.t('条')}",
            f"📖 {tr.t('长期记忆事实')}: {len(self.long_term.facts)} | "
            f"{tr.t('学习记录')}: {len(self.long_term.learned)}",
        ]

        return "\n".join(lines)

    # ═══════════════════════════════════════════════
    # 资源管理
    # ═══════════════════════════════════════════════

    def close(self):
        """释放资源"""
        if self.knowledge_db:
            self.knowledge_db.close()
        self.long_term.save()
        self.evolution.save()
        self.tier.save()
        self.auth.save()

    # ═══════════════════════════════════════════════
    # Tier management
    # ═══════════════════════════════════════════════

    def list_subscriptions(self) -> list:
        """列出所有可用订阅方案及价格"""
        return self.tier.list_plans()

    def show_payment(self, plan: str) -> str:
        """显示某个方案的付款信息"""
        return self.tier.format_payment(plan)

    def activate_tier(self, plan: str, duration_days: int):
        """激活订阅（仅供管理员/验证后调用）"""
        if 'plus' in plan:
            self.tier.activate_plus(duration_days)
        elif 'pro' in plan:
            self.tier.activate_pro(duration_days)

    def tier_status(self) -> str:
        """当前许可状态"""
        return self.tier.format_status()

    # ═══════════════════════════════════════════════
    # Evolution management
    # ═══════════════════════════════════════════════

    def evolution_status(self) -> str:
        """进化状态报告"""
        return self.evolution.format_status()

    @property
    def current_version(self) -> str:
        """当前进化版本号"""
        return self.evolution.version

    # ═══════════════════════════════════════════════
    # 用户认证
    # ═══════════════════════════════════════════════

    def register(self, username: str, password: str) -> dict:
        """注册新用户"""
        return self.auth.register(username, password)

    def login(self, username: str, password: str) -> dict:
        """登录"""
        return self.auth.login(username, password)

    def logout(self):
        """退出登录"""
        self.auth.logout()

    def is_logged_in(self) -> bool:
        """是否已登录"""
        return self.auth.is_logged_in()

    def get_current_user(self) -> Optional[str]:
        """当前登录用户"""
        return self.auth.get_current_user()

    def account_status(self) -> str:
        """账号状态"""
        return self.auth.format_status()

    def set_preference(self, key: str, value: Any) -> dict:
        """设置用户偏好"""
        return self.auth.set_preference(key, value)

    def get_preference(self, key: str, default: Any = None) -> Any:
        """获取用户偏好"""
        return self.auth.get_preference(key, default)

    def get_all_preferences(self) -> dict:
        """所有偏好"""
        return self.auth.get_all_preferences()

    def delete_account(self, username: str, password: str) -> dict:
        """删除账号"""
        return self.auth.delete_account(username, password)
