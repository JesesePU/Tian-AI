"""
Tian AI M1 — Advanced Evolution Module
═══════════════════════════════════════════════

The AI continuously searches, learns, and grows.

Version system:
  - M1        → Base version
  - M1E       → M1 with enhancement(s) (feature upgrades)
  - M2        → Major upgrade (new features, knowledge expansion)
  - M2E       → M2 enhanced
  - M2Reason  → Major upgrade themed "reason" (reasoning focus)
  - M2E sciencer  → Enhanced M2 themed "sciencer"

Version structure:  f"M{major}{theme_suffix}{'E' if enhanced else ''}"

Feature naming themes:
  - sciencer       → Science & technology focused
  - reason         → Reasoning & logic focused
  - understanding  → Deep understanding & knowledge
  - creator        → Creative & generative
  - analyzer       → Analysis & data processing
  - communicator   → Language & communication

Key mechanics:
  1. Each interaction earns XP (experience points).
  2. Small enhancement (set_enhanced): marks version with E suffix.
     Improves existing features, no major version bump.
  3. Major milestone (check_milestone): M number +1, clears E flag,
     develops a new feature, assigns a theme alias.
  4. Theme is auto-assigned based on the new feature's domain.

Data persisted to evolution_store.json
"""

import time
import json
import math
import os
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set, Tuple
from collections import defaultdict
from .multilingual import TranslationProvider


# ═══════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════

# XP rewards for different actions
XP_REWARDS = {
    'search_query':      3,
    'search_result':     1,
    'new_topic':        15,
    'knowledge_hit':     2,
    'follow_up':         5,
    'user_positive':     8,
    'reflection':       10,
    'deep_analysis':    12,
    'daily_bonus':      20,
    'interaction':       1,
}

# Milestone: XP needed per major version level
MILESTONE_XP = 100
MILESTONE_MULTIPLIER = 1.5

# Initial version
BASE_VERSION = "M1"

# Feature self-development pool
FEATURE_TEMPLATES = [
    {"name": "multilingual_translation", "label": "多语言翻译",
     "desc": "实时翻译功能，支持中英文互译", "theme": "communicator"},
    {"name": "code_analysis", "label": "代码分析",
     "desc": "代码审查、错误检测与优化建议", "theme": "analyzer"},
    {"name": "text_summarization", "label": "文本摘要",
     "desc": "长文本自动摘要，提取核心观点", "theme": "analyzer"},
    {"name": "sentiment_timeline", "label": "情绪时间线",
     "desc": "追踪对话中的情绪变化趋势", "theme": "understanding"},
    {"name": "knowledge_graph", "label": "知识图谱",
     "desc": "实体关系抽取，可视化知识关联", "theme": "understanding"},
    {"name": "language_style_transfer", "label": "语风转换",
     "desc": "改写文本风格，正式/口语/诗意等", "theme": "communicator"},
    {"name": "concept_explainer", "label": "概念解释器",
     "desc": "用多个视角解释复杂概念", "theme": "reason"},
    {"name": "debate_generator", "label": "辩论生成",
     "desc": "对同一话题生成正反方观点", "theme": "reason"},
    {"name": "hypothesis_tester", "label": "假设检验",
     "desc": "对用户提出的假设进行逻辑验证", "theme": "reason"},
    {"name": "creative_writing_framework", "label": "创作框架",
     "desc": "故事/诗歌/剧本的结构化创作辅助", "theme": "creator"},
    {"name": "memory_compression", "label": "记忆压缩",
     "desc": "将长期记忆压缩为知识摘要", "theme": "understanding"},
    {"name": "argument_mapper", "label": "论点图谱",
     "desc": "提取争论中的逻辑链条和漏洞", "theme": "reason"},
    {"name": "cross_domain_bridge", "label": "跨域桥梁",
     "desc": "在不同领域之间建立概念连接", "theme": "understanding"},
    {"name": "behavioral_pattern_recognition", "label": "行为模式识别",
     "desc": "识别用户的思维模式和习惯", "theme": "analyzer"},
    {"name": "personalized_teaching", "label": "个性化教学",
     "desc": "根据用户知识水平自适应调整解释深度", "theme": "communicator"},
    {"name": "idea_incubator", "label": "创意孵化器",
     "desc": "基于用户输入展开发散性创意联想", "theme": "creator"},
    {"name": "cognitive_bias_detector", "label": "认知偏差检测",
     "desc": "识别对话中的逻辑谬误和认知偏见", "theme": "reason"},
    {"name": "scenario_simulator", "label": "情景模拟器",
     "desc": "对假设情景进行推演和可能结果预测", "theme": "creator"},
    {"name": "metaphor_factory", "label": "隐喻工坊",
     "desc": "生成类比和比喻帮助理解抽象概念", "theme": "creator"},
    {"name": "decision_matrix", "label": "决策矩阵",
     "desc": "多维度分析和比较不同选择", "theme": "reason"},
]

# Theme display names
THEME_NAMES = {
    "sciencer":      "Sciencer",
    "reason":        "Reason",
    "understanding": "Understanding",
    "creator":       "Creator",
    "analyzer":      "Analyzer",
    "communicator":  "Communicator",
}


class TopicRecord:
    """Tracks exploration depth for a single topic."""
    def __init__(self, name: str, depth: int = 1,
                 last_accessed: float = 0, xp_earned: int = 0):
        self.name = name
        self.depth = depth
        self.last_accessed = last_accessed or time.time()
        self.xp_earned = xp_earned


class EvolutionEngine:
    """
    Tracks learning progress and manages version evolution.

    Version mechanics:
      - M{number}{theme}{E}
        major: increments on milestone (new feature developed)
        theme: named alias based on features developed (e.g. reason, sciencer)
        E:     present when existing features have been enhanced

    Enhancement: marks the current version as enhanced (E suffix).
    Does NOT develop a new feature — only improves existing ones.

    Major milestone: increments M number, clears E flag,
    develops a new feature, assigns a thematic alias.

    Each major milestone triggers tier.grant_evolution_plus()
    to reward active Pro/Plus users.
    """

    def __init__(self, store_path: str = 'evolution_store.json',
                 tr: Optional[TranslationProvider] = None):
        self.tr = tr or TranslationProvider(lang="en")

        # Version components
        self.major = 1                  # M-number
        self.enhanced = False           # True = has E suffix
        self.theme: str = ""            # Named alias (e.g. "reason", "sciencer")

        # XP system
        self.xp = 0
        self.total_xp = 0
        self.total_interactions = 0
        self.version_updates = 0

        # Self-developed features
        self.developed_features: List[dict] = []

        # Learning indicators
        self.topics_explored: Dict[str, TopicRecord] = {}
        self._recent_queries: List[str] = []
        self._daily_first = False
        self._used_templates: Set[str] = set()

        # Persistence
        self.store_path = store_path
        self._last_save = time.time()
        self._load()

    # ── Version ──

    @property
    def version(self) -> str:
        """Full version string: M1, M1E, M2Reason, M2EReason, etc."""
        parts = [f"M{self.major}"]
        if self.enhanced:
            parts.append("E")
        if self.theme:
            parts.append(THEME_NAMES.get(self.theme, self.theme.capitalize()))
        return "".join(parts)

    @property
    def version_display(self) -> str:
        """Human-friendly display version."""
        base = f"M{self.major}"
        if self.enhanced:
            base += "E"
        if self.theme:
            base += f" {THEME_NAMES.get(self.theme, self.theme.capitalize())}"
        return base

    @property
    def milestone_xp(self) -> int:
        return int(MILESTONE_XP * (MILESTONE_MULTIPLIER ** self.version_updates))

    @property
    def progress(self) -> float:
        return min(1.0, self.xp / self.milestone_xp)

    def enhance(self) -> str:
        """
        Mark current version as enhanced (add E suffix).
        Does NOT develop a new feature — only improves existing ones.
        Returns the new version string.
        """
        if not self.enhanced:
            self.enhanced = True
            self.save()
        return self.version

    # ── Persistence ──

    def _get_path(self) -> str:
        if self.store_path.startswith('/'):
            return self.store_path
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, self.store_path)

    def _load(self):
        path = self._get_path()
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            self.major = data.get('major', 1)
            self.enhanced = data.get('enhanced', False)
            self.theme = data.get('theme', '')
            self.xp = data.get('xp', 0)
            self.total_xp = data.get('total_xp', 0)
            self.total_interactions = data.get('total_interactions', 0)
            self.version_updates = data.get('version_updates', 0)
            self.developed_features = data.get('developed_features', [])
            self._used_templates = set(data.get('used_templates', []))

            topics_raw = data.get('topics_explored', {})
            self.topics_explored = {}
            for k, v in topics_raw.items():
                self.topics_explored[k] = TopicRecord(
                    name=k,
                    depth=v.get('depth', 1),
                    last_accessed=v.get('last_accessed', time.time()),
                    xp_earned=v.get('xp_earned', 0),
                )
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save(self):
        path = self._get_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        topics_serial = {}
        for k, rec in self.topics_explored.items():
            topics_serial[k] = {
                'depth': rec.depth,
                'last_accessed': rec.last_accessed,
                'xp_earned': rec.xp_earned,
            }
        with open(path, 'w') as f:
            json.dump({
                'major': self.major,
                'enhanced': self.enhanced,
                'theme': self.theme,
                'xp': self.xp,
                'total_xp': self.total_xp,
                'total_interactions': self.total_interactions,
                'version_updates': self.version_updates,
                'developed_features': self.developed_features,
                'used_templates': list(self._used_templates),
                'topics_explored': topics_serial,
                'last_save': time.time(),
            }, f, indent=2)

    # ── Feature self-development ──

    def _self_develop_feature(self) -> dict:
        """
        Generate a new feature on major milestone.
        Picks from unused FEATURE_TEMPLATES first, then generates dynamically.
        Returns the feature dict with theme info.
        """
        available = [t for t in FEATURE_TEMPLATES if t['name'] not in self._used_templates]
        if available:
            picked = random.choice(available)
        else:
            feature_num = len(self.developed_features) + 1
            theme = random.choice(list(THEME_NAMES.keys()))
            picked = {
                "name": f"dynamic_feature_{feature_num}",
                "label": f"动态功能 #{feature_num}",
                "desc": f"自动进化生成的新功能 ({feature_num})",
                "theme": theme,
            }

        self._used_templates.add(picked['name'])
        feature_theme = picked.get('theme', 'understanding')
        feature = {
            'name': picked['name'],
            'label': picked['label'],
            'desc': picked['desc'],
            'theme': feature_theme,
            'version_bumped': f"M{self.major}",
            'developed_at': time.time(),
        }
        self.developed_features.append(feature)
        return feature, feature_theme

    def _determine_theme(self, features_since_last_major: List[dict]) -> str:
        """
        Determine the theme alias for the new major version
        based on the features developed in this cycle.
        """
        if not features_since_last_major:
            return "understanding"
        # Count theme occurrences
        theme_counts: Dict[str, int] = defaultdict(int)
        for feat in features_since_last_major:
            t = feat.get('theme', 'understanding')
            theme_counts[t] += 1
        # Return most common theme
        return max(theme_counts, key=theme_counts.get)

    def _check_milestone(self) -> Optional[dict]:
        """
        Check if milestone is reached (major upgrade).
        If so: bump M number, clear enhanced flag, develop a new feature,
        and assign a theme alias based on developed features.

        Returns dict with version info if milestone reached, None otherwise.
        """
        target = self.milestone_xp
        if self.xp < target:
            return None

        # Major milestone reached!
        overflow = self.xp - target
        old_major = self.major
        self.major += 1
        self.enhanced = False  # Clear E flag for fresh major
        self.xp = overflow
        self.version_updates += 1

        # Develop a new feature
        new_feature, feature_theme = self._self_develop_feature()

        # Determine theme for this version
        # Collect all features developed under the old major version
        features_this_cycle = [
            f for f in self.developed_features
            if f.get('version_bumped', '').startswith(f"M{old_major}")
        ]
        if features_this_cycle:
            self.theme = self._determine_theme(features_this_cycle)
        else:
            self.theme = feature_theme

        self.save()

        return {
            'version': self.version,
            'version_display': self.version_display,
            'new_feature': new_feature,
            'theme': self.theme,
        }

    # ── XP earning ──

    def record_interaction(self, query: str, mode: str = 'fast',
                           knowledge_hit: bool = False,
                           search_used: bool = False) -> Optional[dict]:
        """
        Record one user interaction. Returns milestone dict if major
        milestone was reached, None otherwise.
        """
        self.total_interactions += 1

        # Daily bonus
        today = datetime.now().strftime('%Y-%m-%d')
        if not self._daily_first:
            self._add_xp('daily_bonus')
            self._daily_first = True

        # Base interaction
        self._add_xp('interaction')

        # Search XP
        if search_used:
            self._add_xp('search_query')
            self._add_xp('search_result')

        # Knowledge hit XP
        if knowledge_hit:
            self._add_xp('knowledge_hit')

        # Deep mode XP
        if mode in ('deep', 'cot'):
            self._add_xp('deep_analysis')

        # Topic tracking
        topic = self._extract_topic(query)
        if topic:
            if topic in self.topics_explored:
                self.topics_explored[topic].depth += 1
                self.topics_explored[topic].last_accessed = time.time()
                self._add_xp('follow_up')
            else:
                self.topics_explored[topic] = TopicRecord(
                    name=topic, depth=1, last_accessed=time.time()
                )
                self._add_xp('new_topic')

        # Keep recent queries
        self._recent_queries.append(query)
        if len(self._recent_queries) > 20:
            self._recent_queries = self._recent_queries[-20:]

        # Check milestone
        result = self._check_milestone()
        self.save()
        return result

    def _add_xp(self, action: str):
        reward = XP_REWARDS.get(action, 0)
        if reward > 0:
            self.xp += reward
            self.total_xp += reward

    def _extract_topic(self, query: str) -> Optional[str]:
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'to',
                      'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                      'what', 'why', 'how', 'when', 'where', 'who', 'does',
                      'do', 'did', 'can', 'will', 'would', 'could', 'should',
                      'this', 'that', 'these', 'those'}
        words = query.strip().lower().split()
        content = [w for w in words if w not in stop_words and len(w) > 2]
        if not content:
            return None
        for i in range(len(content)):
            pair = ' '.join(content[i:i+2])
            if len(pair) > 4:
                return pair
        return content[0]

    # ── Status ──

    def get_status(self) -> dict:
        return {
            'version': self.version,
            'version_display': self.version_display,
            'enhanced': self.enhanced,
            'theme': self.theme,
            'xp': self.xp,
            'total_xp': self.total_xp,
            'milestone_xp': self.milestone_xp,
            'progress': self.progress,
            'progress_pct': f"{self.progress * 100:.1f}%",
            'total_interactions': self.total_interactions,
            'version_updates': self.version_updates,
            'topics_count': len(self.topics_explored),
            'features_count': len(self.developed_features),
            'latest_features': self.developed_features[-3:] if self.developed_features else [],
            'next_feature_at': self.milestone_xp - self.xp,
        }

    def format_status(self) -> str:
        s = self.get_status()
        bar_len = 20
        filled = int(self.progress * bar_len)
        bar = '█' * filled + '░' * (bar_len - filled)

        lines = [
            f"━━ {self.tr.t('进化状态')}: {s['version_display']} ━━",
            f"  {self.tr.t('等级')}: {s['version_updates']} | "
            f"{self.tr.t('经验值')}: {s['total_xp']} XP",
            f"  [{bar}] {s['progress_pct']} ({s['xp']}/{s['milestone_xp']} XP)",
            f"  {self.tr.t('交互次数')}: {s['total_interactions']}",
            f"  {self.tr.t('已探索话题')}: {s['topics_count']}",
            f"  {self.tr.t('已开发功能')}: {s['features_count']}",
        ]

        if s['latest_features']:
            lines.append(f"  {self.tr.t('最新功能')}:")
            for feat in s['latest_features']:
                label = self.tr.t(feat.get('label', '')) if self.tr.lang == 'en' else feat.get('label', '')
                desc = self.tr.t(feat.get('desc', '')) if self.tr.lang == 'en' else feat.get('desc', '')
                lines.append(f"    ✦ {label} ({self.tr.t('版本')} {feat['version_bumped']})")
                lines.append(f"      {desc}")

        top_deepest = sorted(
            self.topics_explored.items(),
            key=lambda x: x[1].depth,
            reverse=True
        )[:5]
        if top_deepest:
            lines.append(f"  {self.tr.t('最深入话题')}:")
            for topic, rec in top_deepest:
                lines.append(f"    · {topic} ({self.tr.t('深度')}: {rec.depth})")

        return "\n".join(lines)
