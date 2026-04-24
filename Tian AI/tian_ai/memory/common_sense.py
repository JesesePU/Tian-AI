"""
Tian AI — 本地常识知识库（精简版，吸收自旧版 common_sense v2）

功能：
- IS_A 概念层级图谱（50+概念分类）
- HAS_PROPERTY 属性词典（关键人物/概念的定义）
- CAUSES / CAUSED_BY 因果链（17组本地因果关系）
- CONTRASTS 对比关系（3组预设对比）
- ARITHMETIC 基础运算表
- 查询接口：what_is() / causal_reason() / compare() / solve_arithmetic() / infer_type()

NOTE：纯本地快速查询，不依赖 LLM。新架构中 Thinker 使用 LLM 做主推理，
此模块仅作为 FastThinker 的本地备选查询和概念快速解析用。
"""

import re


# ═══════════════════════════════════════
# 基础常识知识图谱
# ═══════════════════════════════════════

# 概念层级关系 (is_a)
IS_A = {
    # 科学人物
    '爱因斯坦': '科学家', '牛顿': '科学家', '伽利略': '科学家',
    '达尔文': '科学家', '居里夫人': '科学家', '霍金': '科学家',
    '特斯拉': '发明家', '爱迪生': '发明家',
    # 学科
    '微积分': '数学分支', '量子力学': '物理学分支',
    '经典力学': '物理学分支', '相对论': '物理学分支',
    '电磁学': '物理学分支', '热力学': '物理学分支',
    '生物学': '自然科学', '物理学': '自然科学',
    '化学': '自然科学', '数学': '自然科学',
    '天文学': '自然科学', '地理学': '自然科学',
    '哲学': '人文学科', '心理学': '社会科学',
    '经济学': '社会科学', '历史学': '人文学科',
    '医学': '应用科学', '工程': '应用科学',
    # 抽象概念
    '自由': '抽象概念', '幸福': '抽象概念', '正义': '抽象概念',
    '真理': '抽象概念', '美': '抽象概念', '爱': '抽象概念',
    '时间': '抽象概念', '空间': '抽象概念', '意识': '抽象概念',
    '生命': '抽象概念', '知识': '抽象概念', '智慧': '抽象概念',
    '勇气': '抽象概念', '善良': '抽象概念',
    # 情感
    '开心': '正面情绪', '快乐': '正面情绪', '喜悦': '正面情绪',
    '幸福': '正面情绪', '满意': '正面情绪', '兴奋': '正面情绪',
    '伤心': '负面情绪', '难过': '负面情绪', '不开心': '负面情绪',
    '愤怒': '负面情绪', '焦虑': '负面情绪', '恐惧': '负面情绪',
    '孤独': '负面情绪', '沮丧': '负面情绪',
    # 基础运算
    '加法': '算术运算', '减法': '算术运算',
    '乘法': '算术运算', '除法': '算术运算',
    '数字': '数学概念', '计算': '数学概念',
}

# 属性关系 (has_property)
HAS_PROPERTY = {
    '爱因斯坦': ['提出了相对论', 'E=mc²', '物理学家', '20世纪最伟大科学家之一'],
    '牛顿': ['提出了万有引力定律', '经典力学奠基人', '微积分发明者之一', '自然哲学的数学原理'],
    '微积分': ['研究变化率的数学分支', '包括微分和积分', '牛顿和莱布尼茨发明'],
    '量子力学': ['描述微观粒子', '波粒二象性', '不确定性原理', '哥本哈根诠释'],
    '经典力学': ['牛顿力学', '描述宏观物体运动', 'F=ma', '适用于日常尺度'],
    '相对论': ['爱因斯坦提出', 'E=mc²', '光速不变原理', '时空弯曲'],
    '自由': ['自主选择的权利', '免于约束的状态', '哲学核心概念', '有积极和消极之分'],
    '幸福': ['主观感受', '生活满意度', '积极心理学核心', '因人而异'],
    '正义': ['公平与公正', '社会制度的核心价值', '法律的基石'],
    '开心': ['正面情感体验', '通常由满足感引起', '基本情绪之一'],
    '不开心': ['负面情感体验', '可能由挫折引起', '需要关注和理解'],
}

# 因果关系
CAUSES = {
    '摩擦': '生热', '加热': '温度升高', '温度升高': '分子运动加剧',
    '不开心': '需要倾诉或安慰', '开心': '通常源于好事发生',
    '努力学习': '获得知识', '练习': '技能提升',
    '提出问题': '获得答案', '生热': '能量转化',
    '力': '加速度改变', '电流': '产生磁场',
    '光合作用': '产生氧气和能量', '学习': '增长知识',
    '思考': '加深理解', '锻炼': '增强体质',
    '睡眠': '恢复精力', '吃饭': '补充能量',
}

CAUSED_BY = {}
for k, v in CAUSES.items():
    CAUSED_BY.setdefault(v, []).append(k)

# 对比关系
CONTRASTS = {
    ('量子力学', '经典力学'): [
        '量子力学描述微观世界，经典力学描述宏观世界',
        '量子力学中有不确定性原理，经典力学中一切确定',
        '量子力学中粒子可同时处于多个状态（叠加态），经典力学中物体有确定位置',
        '量子力学在原子尺度适用，经典力学在日常尺度适用',
    ],
    ('爱因斯坦', '牛顿'): [
        '牛顿是经典物理学奠基人，爱因斯坦发展了现代物理学',
        '牛顿研究万有引力，爱因斯坦发展为广义相对论',
        '牛顿的时空观是绝对的，爱因斯坦的时空观是相对的',
        '两人都是划时代的科学巨人，贡献在不同层面',
    ],
    ('微积分', '量子力学'): [
        '微积分是数学工具，量子力学是物理理论',
        '微积分为量子力学提供了数学基础',
        '量子力学中使用微分方程描述波函数',
    ],
}

# 基础运算表
ARITHMETIC = {
    '1+1': '2', '1+2': '3', '2+2': '4', '3+3': '6',
    '1-1': '0', '2-1': '1', '3-2': '1',
    '1×1': '1', '2×2': '4', '3×3': '9', '1*1': '1',
    '1÷1': '1', '2÷2': '1',
    '0+1': '1', '1+0': '1',
}


class CommonSense:
    """
    本地常识知识库 — 快速概念查询/推理，不依赖 LLM
    
    为 FastThinker 提供本地概念查询、算术、因果、对比等能力。
    新架构的 CoT/DeepThinker 使用 LLM 做主要推理，不依赖此模块。
    """
    
    def what_is(self, concept: str) -> str | None:
        """返回概念的基本定义"""
        concept = concept.strip()
        if concept in HAS_PROPERTY:
            props = HAS_PROPERTY[concept]
            return f'{concept}：' + '；'.join(props[:3])
        if concept in IS_A:
            return f'{concept}是一种{IS_A[concept]}。'
        return None
    
    def classify(self, concept: str) -> str | None:
        """返回概念类别"""
        return IS_A.get(concept.strip())
    
    def get_properties(self, concept: str) -> list:
        """返回概念属性列表"""
        return HAS_PROPERTY.get(concept.strip(), [])
    
    def compare(self, a: str, b: str) -> list | None:
        """对比两个概念"""
        key = (a, b) if (a, b) in CONTRASTS else \
              (b, a) if (b, a) in CONTRASTS else \
              tuple(sorted([a, b])) if tuple(sorted([a, b])) in CONTRASTS else None
        if not key:
            return None
        diffs = CONTRASTS.get(key)
        if diffs and key != (a, b):
            # 交换概念名称
            swapped = []
            for d in diffs:
                tmp = d.replace(key[1], '__TMP__').replace(key[0], key[1])
                tmp = tmp.replace('__TMP__', key[0])
                swapped.append(tmp)
            return swapped
        return diffs
    
    def causal_reason(self, thing: str) -> dict | None:
        """因果推理"""
        results = {}
        if thing in CAUSES:
            results['causes'] = CAUSES[thing]
        if thing in CAUSED_BY:
            results['caused_by'] = CAUSED_BY[thing]
        return results if results else None
    
    def infer_type_chain(self, thing: str) -> list:
        """推断事物类型链"""
        chain = []
        current = thing
        seen = set()
        while current in IS_A and current not in seen:
            seen.add(current)
            parent = IS_A[current]
            chain.append(parent)
            current = parent
        return chain
    
    def solve_arithmetic(self, query: str) -> str | None:
        """解析并计算简单算术"""
        clean = query.replace(' ', '').replace('等于', '=').replace('多少', '')
        if clean.endswith('几'):
            clean = clean[:-1]
        # 已知结果表匹配
        for pattern, result in ARITHMETIC.items():
            if pattern in clean:
                return result
        
        # 提取数字和运算符
        nums = re.findall(r'\d+', query)
        if len(nums) < 2:
            return None
        
        ops = {
            '+': lambda a, b: a + b, '-': lambda a, b: a - b,
            '×': lambda a, b: a * b, '*': lambda a, b: a * b,
            '/': lambda a, b: a / b if b != 0 else None,
            '÷': lambda a, b: a / b if b != 0 else None,
        }
        for op_char, op_func in ops.items():
            if op_char in query:
                a, b = int(nums[0]), int(nums[1])
                result = op_func(a, b)
                if result is not None:
                    n = int(result) if result == int(result) else result
                    return str(n)
        return None
    
    def extract_topics(self, text: str) -> list:
        """从文本中提取已知概念——长词优先"""
        topics = []
        all_keys = (set(IS_A.keys()) | set(HAS_PROPERTY.keys()) |
                    set(CAUSES.keys()) | set(CAUSED_BY.keys()))
        sorted_keys = sorted(all_keys, key=len, reverse=True)
        
        for kw in sorted_keys:
            if kw in text:
                has_parent = any(kw in t and kw != t for t in topics)
                if kw not in topics and not has_parent:
                    topics.append(kw)
        
        # 补充对比关系中的概念
        for (a, b) in CONTRASTS:
            for name in (a, b):
                if name in text and name not in topics:
                    topics.append(name)
        
        return topics[:5]
    
    def quick_query(self, query: str) -> dict | None:
        """
        快速本地查询，不涉及 LLM。
        
        适用于：算术、纯概念定义、小规模因果/对比。
        返回与 Thinker router 兼容的格式。
        """
        # 算术
        arith = self.solve_arithmetic(query)
        if arith:
            return {'answer': arith, 'source': 'common_sense',
                    'confidence': 0.95, 'type': 'arithmetic'}
        
        # 对比（当有明确对比词时）
        topics = self.extract_topics(query)
        has_compare = any(kw in query for kw in ['和', '与', '区别', '对比', '比', '谁', '哪个'])
        if len(topics) >= 2 and has_compare:
            a, b = topics[0], topics[1]
            diffs = self.compare(a, b)
            if diffs:
                lines = [f'关于「{a}」和「{b}」的区别：']
                lines.extend(f'• {d}' for d in diffs[:4])
                return {'answer': '\n'.join(lines), 'source': 'common_sense',
                        'confidence': 0.85, 'type': 'comparison'}
        
        # 概念定义
        if topics:
            defns = [self.what_is(t) for t in topics if self.what_is(t)]
            if defns:
                return {'answer': '\n'.join(defns[:3]), 'source': 'common_sense',
                        'confidence': 0.6, 'type': 'definition'}
        
        # 因果
        for t in topics:
            causal = self.causal_reason(t)
            if causal:
                lines = []
                if 'causes' in causal:
                    lines.append(f'{t} 会导致 {causal["causes"]}。')
                if 'caused_by' in causal:
                    lines.append(f'{t} 可以由 {"、".join(causal["caused_by"])} 引起。')
                if lines:
                    return {'answer': '\n'.join(lines), 'source': 'common_sense',
                            'confidence': 0.85, 'type': 'causal'}
        
        return None
