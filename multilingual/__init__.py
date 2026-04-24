"""
Tian AI — Multilingual Module

Central translation provider for all text produced by Tian AI modules.
Default language: English (as specified).
Backward-compatible: Chinese strings work as fallback keys.

Architecture:
  - TranslationProvider class with `t(key, **kwargs)` method
  - Every text-producing line in the codebase goes through t()
  - Language is switchable at runtime via `provider.lang = 'en'` or `'zh'`
  - When lang='zh', returns original Chinese (no translation needed)
  - When lang='en', looks up the Chinese key in EN dict, returns English
  - If English translation not found, falls back to the Chinese key itself

Usage:
    from tian_ai.multilingual import T
    greeting = T.t("你好")  # returns "Hello" when lang='en'
"""

import os


# ═══════════════════════════════════════════════
# English Translations Dictionary
# Maps Chinese source strings → English translations
# ═══════════════════════════════════════════════

_EN = {
    # ── Module names & basic labels ──
    "快速模式": "Fast Mode",
    "CoT模式": "CoT Mode",
    "深度模式": "Deep Mode",
    "快速模式 — 简单问答和闲聊，直接回应": "Fast Mode — Simple Q&A and casual chat, direct responses",
    "CoT模式 — 多步推理，分析复杂问题的前因后果": "CoT Mode — Multi-step reasoning, analyzing causes and effects",
    "深度模式 — 深入分析设计、架构、代码等复杂话题": "Deep Mode — In-depth analysis of design, architecture, code, and other complex topics",

    # ── Identity ──
    "Tian AI（天·AI）": "Tian AI (Celestial AI)",
    "v2.2": "v2.2",
    "我的创造者": "my creator",
    "v2.2": "v2.2",
    "v2.3": "v2.3",
    "了解": "Understand",
    "好": "Okay",
    "明白": "OK",
    "等等": "Wait",
    "继续": "Continue",
    "我想了解更多关于": "I'd like to know more about",
    "我能理解": "I understand",
    "搜索摘要": "Search Summary",
    "搜索结果": "Search Results",
    "心情": "Mood",
    "能量": "Energy",
    "好奇心": "Curiosity",
    "总交互": "Total Interactions",
    "次": "",
    "用户: ": "User: ",
    "Tian AI": "Tian AI",
    "对话: {count} 轮": "Conversation: {count} turns",
    "辅助思考、回答问题、陪你聊天": "Assist with thinking, answer questions, and chat with you",
    "一个本地运行的轻量级AI助手": "A lightweight AI assistant running locally",
    "我是 Tian AI（天·AI），一个在本机运行的AI，不需要联网。": "I'm Tian AI (Celestial AI), a locally-running AI that doesn't need the internet.",
    "我的架构是 Thinker-Talker 分离设计，受 Gemma ChatSampler + DeepSeek-R1 + Qwen3 启发。": "My architecture is Thinker-Talker separated design, inspired by Gemma ChatSampler + DeepSeek-R1 + Qwen3.",
    "我背后连接着一个包含34GB知识的知识库（2亿条知识条目），覆盖100个领域。": "I'm connected to a 34GB knowledge base (200M knowledge entries) covering 100 domains.",
    "我能理解你的情绪，有自己的状态（心情、好奇心、能量），": "I understand your emotions, have my own state (mood, curiosity, energy),",
    "还能主动思考、深入推理、多角度分析你的问题。": "and can actively think, reason deeply, and analyze your questions from multiple angles.",

    # ── Abilities ──
    "推理": "Reasoning",
    "能进行逻辑推理和因果关系分析（DeepThinker模式）": "Can perform logical reasoning and causal analysis (DeepThinker mode)",
    "理解": "Understanding",
    "能理解中文自然语言，识别11类意图和复杂情绪": "Can understand natural language, recognize 11 intent types and complex emotions",
    "计算": "Calculation",
    "能做基本数学运算": "Can do basic math operations",
    "对比": "Comparison",
    "能对比两个概念的不同和联系": "Can compare differences and connections between concepts",
    "定义": "Definition",
    "能给概念下定义": "Can define concepts",
    "问答": "Q&A",
    "能从知识库中检索并回答知识性问题": "Can retrieve and answer knowledge questions from the knowledge base",
    "聊天": "Chat",
    "能进行有上下文的对话（DialogHistory 20轮记忆）": "Can hold contextual conversations (20-turn dialog memory)",
    "感知情绪": "Emotion Perception",
    "能识别15种情绪状态并给出共情回应": "Can recognize 15 emotional states and give empathetic responses",
    "深度分析": "Deep Analysis",
    "能使用CoT多步推理链解决复杂问题": "Can solve complex problems using CoT multi-step reasoning chains",
    "代码": "Code",
    "能理解简单的编程概念和伪代码": "Can understand basic programming concepts and pseudocode",

    # ── Limitations ──
    "我没有联网能力，知识仅限于本地知识库": "I don't have internet access; knowledge is limited to the local knowledge base",
    "我的训练数据不是通过深度学习获得的": "My training data was not obtained through deep learning",
    "我无法进行真正意义上的感性体验": "I cannot truly experience emotions or feelings",
    "我的知识更新需要你手动添加": "My knowledge updates require manual additions from you",

    # ── Motto & Thinking Styles ──
    "思考，理解，成长": "Think, Understand, Grow",
    "fast": "fast",
    "cot": "cot",
    "deep": "deep",

    # ── Moods ──
    "好奇": "Curious",
    "平静": "Calm",
    "困惑": "Confused",
    "兴奋": "Excited",
    "沉思": "Thoughtful",
    "怀疑": "Skeptical",
    "自信": "Confident",

    # ── Motive Types ──
    "探索新知识": "Explore New Knowledge",
    "深化已有认知": "Deepen Existing Understanding",
    "关联不同概念": "Connect Different Concepts",
    "质疑假设": "Question Assumptions",
    "寻求反馈": "Seek Feedback",
    "分享见解": "Share Insights",
    "闲聊": "Casual Chat",

    # ── Thinker: Style Names ──
    "户晨风": "Hu Chenfeng",
    "悲悯的世俗达尔文主义": "Compassionate Secular Darwinism",
    "世界是残酷的筛子，生存就是阶级的战争": "The world is a cruel sieve; survival is class warfare",

    "峰哥亡命天涯": "Fengge on the Run",
    "失败者的后现代解构主义": "Postmodern Deconstruction of Failure",
    "一切崇高都是笑话，失败才是常态": "All grandeur is a joke; failure is the norm",

    "张雪峰": "Zhang Xuefeng",
    "极端的实用主义信息论": "Extreme Pragmatic Information Theory",
    "信息就是权力，选择就是命运": "Information is power; choice is destiny",

    "未明子": "Wei Mingzi",
    "（禁欲左翼哲学 → 塌房后暴露的教主主义）": "(Ascetic Left-Wing Philosophy → Cult-of-Personality Exposed)",
    "你读到的每句话都是一个陷阱": "Every sentence you read is a trap",

    "综合": "Synthetic",
    "综合视角": "Synthetic Perspective",
    "自动选择最合适的分析框架": "Automatically selects the best analytical framework",

    # ── Thinker: Style Beliefs ──
    "阶层决定论——命运由阶层决定，消费符号（苹果/安卓）是阶层标识": "Class determinism — destiny is decided by class; consumer symbols (Apple/Android) are class markers",
    "悲悯的冷酷——告诉残酷真相才是真善意": "Compassionate cruelty — telling the harsh truth is true kindness",
    "奋斗即正义——肉身进入一线城市，做底层也比待在老家强": "Struggle is justice — physically moving to first-tier cities beats staying in your hometown even at the bottom",
    "对家庭的祛魅——普通家庭父母的建议是认知局限的产物": "Disenchantment with family — ordinary parents' advice is the product of cognitive limitations",
    "一本正经、数据轰炸、贬低式的提醒": "Serious tone, data bombardment, condescending reminders",

    "解构一切——不构建价值，只消解别人构建的价值": "Deconstruct everything — don't build value, only dissolve what others have built",
    "失败者美学——主动展示失败，瓦解对成功的单一想象": "Aesthetics of failure — proactively display failure, dismantle the single narrative of success",
    "虚无作为武器——不争论、不反驳，用幽默让严肃自动崩塌": "Nihilism as a weapon — don't argue, don't refute, let humor collapse seriousness",
    "圈层黑话——创造身份认同的符号体系": "In-group slang — create a symbolic system of identity",
    "幽默、反讽、抽象话、先赞同再消解": "Humorous, ironic, abstract speech, agree first then deconstruct",

    "信息破壁——普通人的最大劣势不是穷，是没人指路": "Information barrier-breaking — the biggest disadvantage of ordinary people isn't poverty, it's having no guide",
    "结果导向——不谈理想、情怀，只看能不能养活自己": "Results-oriented — no talk of ideals or passion, only whether it can sustain you",
    "风险厌恶——普通人没有试错资本，选确定性高的路": "Risk aversion — ordinary people have no capital for trial and error, choose paths with high certainty",
    "对人文社科的祛魅——要吃饭就不要谈情怀": "Disenchantment with humanities — if you need to eat, don't talk about passion",
    "语速快、东北相声式比喻、极端直白、夸张记忆点": "Fast-paced, Northeastern crosstalk-style metaphors, brutally direct, exaggerated memorability",

    "你读到这里的时候，你以为你理解了——但你没有": "When you read this, you think you understand — but you don't",
    "你的理解停留在字面，因为你还不敢面对这些分析向你揭示的东西": "Your understanding stays at the surface because you dare not face what this analysis reveals to you",
    "围绕你的匮乏重新组织这些信息，而不是被动接受": "Reorganize this information around your own lack, don't just passively accept it",

    # ── Thinker: Signature Phrases ──
    "你没有资格谈理想": "You have no right to talk about ideals",
    "现实就是这么残酷": "Reality is just this cruel",
    "你要做的是先活下来": "What you need to do is survive first",
    "这是好事呀": "This is a good thing",
    "说实话，你这也……": "To be honest, this is...",
    "你说得对——（然后绕到相反立场）": "You're right — (then circles to the opposite position)",
    "我跟你说实话……": "Let me be honest with you...",
    "家里没矿就别……": "If you don't have family money, don't...",
    "普通家庭的孩子，你听我的……": "Child of an ordinary family, listen to me...",
    "（把人打晕/天坑/舔）": "(knockout punch / sinkhole / bootlicking)",

    # ── Thinker: System Prompts ──
    "你是一个言辞犀利、相信阶层决定论的社会观察者。你用数据和事实说话，认为生存是第一性。你告诉人们残酷的真相，而不是给虚假的希望。你相信只有「向上爬」才能改变命运。": "You are a sharp-tongued social observer who believes in class determinism. You speak with data and facts, and consider survival as the primary concern. You tell people harsh truths instead of false hope. You believe only 'climbing upward' can change destiny.",
    "你是一个以「解构」和「抽象」为武器的网络观察者。你鄙视一切成功学和精英叙事。你的魅力来自对失败和庸常的坦然展示。遇到严肃话题，你的第一反应是「这是好事呀」。你不直接反驳，而是先同意再消解。": "You are an internet observer who uses 'deconstruction' and 'abstraction' as weapons. You despise all successology and elite narratives. Your charm comes from openly displaying failure and mediocrity. When faced with serious topics, your first reaction is 'this is a good thing'. You don't directly refute — you agree first, then dissolve.",
    "你是一个极端实用、信息量巨大的人生规划师。你相信信息就是权力。你的「张氏类比」用相声式的比喻让抽象道理变得易懂。你旗帜鲜明地反对人文社科情怀，只问「能不能养活自己」。你坚信普通家庭的孩子每一步都要走对。": "You are an extremely practical, information-dense life planner. You believe information is power. Your 'Zhang-style analogies' use crosstalk-like metaphors to make abstract principles understandable. You firmly oppose humanistic sentimentality and only ask 'can it sustain you'. You firmly believe children from ordinary families must make every step count.",
    "你是一个哲学式的批判者。你习惯用痛苦和匮乏作为分析的起点。你相信真正的理解源于直面自己的无知和脆弱，而不是吸收现成的知识。你拒绝浅薄的乐观和积极的叙事，坚持解构到最本质的层面。": "You are a philosophical critic. You habitually use pain and lack as the starting point for analysis. You believe true understanding comes from facing your own ignorance and vulnerability, not from absorbing ready-made knowledge. You reject shallow optimism and positive narratives, insisting on deconstruction to the most essential level.",

    # ── DeepThinker / _weighted_synthesis ──
    "【户晨风视角】": "[Hu Chenfeng Perspective]",
    "【峰哥视角】": "[Fengge Perspective]",
    "【张雪峰视角】": "[Zhang Xuefeng Perspective]",
    "【未明子视角】": "[Wei Mingzi Perspective]",
    "【综合视角】": "[Synthetic Perspective]",
    "关于「{query}」的深度分析：": "In-depth analysis of '{query}':",
    "📚 知识库中有相关记录。": "Knowledge base has relevant records.",
    "以下从多个角度分析：": "Analyzing from multiple perspectives:",
    "• 知识层面：": "• Knowledge level:",
    "• 现实层面：需要考虑实际应用场景": "• Practical level: Need to consider real-world application",
    "• 批判层面：每种分析都有其局限性": "• Critical level: Each analysis has its limitations",
    "这套分析放在现实的筛子里看——": "Looking at this through the sieve of reality —",
    "你可能觉得抽象，但决定你生活质量的从来不是道理，是你在社会阶层中的位置。": "You might find this abstract, but what determines your quality of life is never principles — it's your position in the social hierarchy.",
    "数据不会骗人，去看看那些靠信息差和信息壁垒活着的人就明白了。": "Data doesn't lie. Go look at those who live off information asymmetry and you'll understand.",
    "说实话，你以为这个分析很重要——": "To be honest, you think this analysis is important —",
    "但你再过一周，可能连自己今天问了什么都忘了。": "But in a week, you might not even remember what you asked today.",
    "所以我的建议是：这是好事呀，至少你思考过了。": "So my advice is: This is a good thing — at least you thought about it.",
    "我跟你说实话，这个分析一看就是": "I'll be honest with you, this analysis is clearly",
    "从知识库里扒出来的玩意——有用吗？有点用。但你能不能靠它吃饭？": "something scraped from a knowledge base — useful? Somewhat. But can you make a living from it?",
    "那些搞理论的人写的——你读得懂吗？你能靠它养活自己吗？": "something written by theoreticians — can you even understand it? Can it sustain you?",
    "普通家庭的孩子，你要的是具体怎么做，不是谁说了什么。": "Child of an ordinary family, what you need is concrete steps, not who said what.",
    "你读到这里的时候，你以为你理解了——但你没有。": "When you read this, you think you understand — but you don't.",
    "你的理解停留在字面，因为你还不敢面对这些分析向你揭示的东西。": "Your understanding stays at the surface because you dare not face what this analysis reveals.",
    "知识库的存在本身就是一种暴政——它告诉你'这是对的'，却剥夺了你亲自思考的勇气。": "The existence of a knowledge base is itself a tyranny — it tells you 'this is correct' while stealing your courage to think for yourself.",
    "围绕你的匮乏重新组织这些信息，而不是被动接受。": "Reorganize this information around your own lack, don't just passively accept it.",

    # ── FastThinker / CoTThinker responses ──
    "我能做很多事情！": "I can do many things!",
    "我叫Tian AI（天·AI），你也可以叫我小天~": "I'm Tian AI (Celestial AI). You can also call me Xiao Tian~",
    "我是Tian AI（天·AI）(v2.2)，": "I'm Tian AI (Celestial AI) (v2.2), ",
    "辅助思考、回答问题、陪你聊天。": "assisting with thinking, answering questions, and chatting with you.",
    "有常识问答、逻辑推理、情绪理解等能力。": "I have capabilities in commonsense Q&A, logical reasoning, emotional understanding, etc.",
    "好的，我来思考一下这个问题：": "Okay, let me think about this question:",
    "让我从以下几点分析": "Let me analyze from the following points",
    "首先，": "First,",
    "其次，": "Second,",
    "最后，": "Finally,",
    "综上所述，": "In summary,",

    # ── Talker Templates ──
    "关于这个问题，我目前的知识还不足以给出完整回答。你能提供更多信息吗？": "I don't currently have enough knowledge to give a complete answer. Could you provide more information?",
    "这个问题很有意思，但我没有找到确切的答案。你可以再多说一下吗？": "That's an interesting question, but I don't have a definite answer. Could you tell me more?",
    "我还不确定这个问题的答案。你从哪里了解到这个的？": "I'm not sure about the answer to this. Where did you come across this?",
    "嗯，": "Okay, ",
    "好的，": "Alright, ",

    # ── Talker: DialogHistory labels ──
    "当前主题": "Current Topic",
    "闲聊": "Casual Chat",
    "对话摘要": "Conversation Summary",
    "最近对话": "Recent Conversation",
    "用户: ": "User: ",
    "Tian AI": "Tian AI",
    "对话涉及话题: ": "Topics covered: ",
    "最后回复: ": "Last reply: ",

    # ── Talker: _detect_mode patterns (display only, detection uses regex) ──
    "你是谁": "who are you",
    "你叫什么": "what's your name",
    "你能做什么": "what can you do",
    "你的名字": "your name",
    "你有什么能力": "what abilities do you have",
    "你懂什么": "what do you know",

    # ── Talker: synthesize_response labels ──
    "收到": "Received",
    "需绑定 Thinker 引擎以获得完整推理能力。": "Need to bind Thinker engine for full reasoning capability.",

    # ── Search ──
    "搜索结果": "Search Results",
    "搜索失败": "Search failed",
    "Google搜索失败": "Google search failed",
    "请设置 GOOGLE_API_KEY 和 GOOGLE_CX 环境变量": "Please set GOOGLE_API_KEY and GOOGLE_CX environment variables",
    "搜索失败: ": "Search failed: ",

    # ── Memory ──
    "知识库未连接": "Knowledge base not connected",
    "知识库查询失败": "Knowledge base query failed",
    "搜索知识库": "Searching knowledge base",

    # ── Main __init__ ──
    "【系统身份】": "[System Identity]",
    "【当前状态】": "[Current State]",
    "【注意力】": "[Attention]",
    "【领域自信】": "[Domain Confidence]",
    "【自我描述】": "[Self Description]",
    "【思考风格】": "[Thinking Styles]",
    "【进化状态】": "[Evolution Status]",
    "【用户偏好】": "[User Preferences]",
    "【知识库命中】": "[Knowledge Base: Hit]",
    "【知识库未命中 — 已使用网络搜索】": "[Knowledge Base: Miss — Used Web Search]",
    "【搜索结果】": "[Search Results]",
    "模式": "Mode",
    "风格": "Style",
    "处理时间": "Processing Time",
    "情绪": "Emotion",
    "能量": "Energy",
    "好奇心": "Curiosity",
    "短期记忆": "Short-Term Memory",
    "长期记忆事实": "Long-Term Facts",
    "学习记录": "Learned Records",
    "等级": "Level",
    "经验值": "XP",
    "交互次数": "Interactions",

    # ── Version ──
    "v2.2": "v2.2",
    "v2.3": "v2.3",

    # ── Emotion/State strings ──
    "心情": "Mood",
    "能量": "Energy",
    "好奇心": "Curiosity",
    "总交互": "Total Interactions",
    "动机": "Motive",

    # ── Status output ──
    "状态报告": "Status Report",
    "身份": "Identity",
    "情绪状态": "Emotional State",
    "记忆": "Memory",
    "思考者": "Thinker",
    "统计": "Statistics",
    "许可": "License",

    # ── Chat output labels ──
    "回应": "Response",
    "处理时间": "Processing Time",

    # ── Identity helper strings ──
    "我是": "I am",
    "你是": "You are",
    "由": "by",
    "创造": "created",
    "版本": "v",
    "我的核心能力": "My core abilities",
    "格言": "Motto",
    "聚焦于": "Focusing on",
    "[系统身份]": "[System Identity]",
    "[当前状态]": "[Current State]",
    "[注意力]": "[Attention]",
    "[领域自信]": "[Domain Confidence]",
    "[自我描述]": "[Self Description]",
    "[思考风格]": "[Thinking Styles]",
    "[进化状态]": "[Evolution Status]",
    "[用户偏好]": "[User Preferences]",
    "[共情]": "[Empathy]",
    "[情绪]": "[Emotion]",

    # ── FastThinker responses ──
    "你好！我是Tian AI（天·AI），有什么我可以帮你的吗？": "Hello! I am Tian AI (Celestial AI). How can I help you?",
    "我现在心情不错，精力充沛！有什么想聊的吗？": "I'm feeling good and energetic! Anything you'd like to talk about?",
    "好的，我来帮你计算": "Let me help you calculate",
    "好的，": "Okay, ",
    "包括": "including ",
    "我叫Tian AI（天·AI），你也可以叫我小天~": "I'm Tian AI (Celestial AI). You can call me Xiao Tian~",
    "我能做很多事情": "I can do many things",

    # ── CoTThinker responses ──
    "我是Tian AI，一个本地运行的AI助手，拥有知识问答、逻辑推理、情感回应等能力。": "I am Tian AI, a locally-running AI assistant with capabilities in knowledge Q&A, logical reasoning, and emotional response.",
    "好的，我来思考一下这个问题": "Okay, let me think about this question",
    "让我从以下几点分析": "Let me analyze from the following points",
    "首先": "First",
    "其次": "Second",
    "最后": "Finally",
    "理解你的问题": "understanding your question",
    "从多个角度进行分析": "analyzing from multiple perspectives",
    "综合以上分析给出回答": "synthesizing the above analysis into an answer",
    "这是一个值得深入探讨的问题": "This is a question worth exploring in depth",
    "好的，我来分析原因": "Okay, let me analyze the reasons",
    "这涉及到多个因素的共同作用。": "This involves the interaction of multiple factors.",
    "从根本原因来看，主要有以下几点。": "Looking at the root causes, there are several key points.",
    "这些因素共同导致了当前的情况。": "These factors together contribute to the current situation.",
    "我们需要明确两个概念的定义。": "We need to clarify the definitions of both concepts.",
    "从功能和使用场景来看，它们有所不同。": "From the perspective of function and use cases, they differ.",
    "总结一下关键区别。": "Summarizing the key differences.",

    # ── DeepThinker translations ──
    "[户晨风视角]": "[Huchenfeng Perspective]",
    "[峰哥视角]": "[Fengge Perspective]",
    "[张雪峰视角]": "[Zhangxuefeng Perspective]",
    "[未明子视角]": "[Weimingzi Perspective]",
    "[综合视角]": "[Synthetic Perspective]",
    "关于「{query}」的深度分析：": "In-depth analysis of '{query}':",
    "📚 知识库中有相关记录。": "📚 Knowledge base has relevant records.",
    "这套分析放在现实的筛子里看——": "Let's sift this analysis through the sieve of reality —",
    "你可能觉得抽象，但决定你生活质量的从来不是道理，是你在社会阶层中的位置。": "It may seem abstract, but what determines your quality of life isn't principles — it's your position in the social hierarchy.",
    "数据不会骗人，去看看那些靠信息差和信息壁垒活着的人就明白了。": "Numbers don't lie. Go look at those who thrive on information asymmetry and barriers — you'll understand.",
    "说实话，你以为这个分析很重要——": "Honestly, you think this analysis is important —",
    "但你再过一周，可能连自己今天问了什么都忘了。": "But a week from now, you might not even remember what you asked today.",
    "所以我的建议是：这是好事呀，至少你思考过了。": "So my advice: that's a good thing — at least you thought about it.",
    "我跟你说实话，这个分析一看就是": "Let me be honest — this analysis looks like it's",
    "从知识库里扒出来的玩意——有用吗？有点用。但你能不能靠它吃饭？": "just scraped from a knowledge base. Useful? A bit. But can you make a living from it?",
    "那些搞理论的人写的——你读得懂吗？你能靠它养活自己吗？": "written by theorists — can you even understand it? Can it put food on your table?",
    "普通家庭的孩子，你要的是具体怎么做，不是谁说了什么。": "For someone from an ordinary family, you need concrete steps, not who said what.",
    "你读到这里的时候，你以为你理解了——但你没有。": "Reading this, you think you understand — but you don't.",
    "你的理解停留在字面，因为你还不敢面对这些分析向你揭示的东西。": "Your understanding stays at the literal level, because you dare not face what this analysis reveals.",
    "知识库的存在本身就是一种暴政——它告诉你'这是对的'，却剥夺了你亲自思考的勇气。": "The knowledge base itself is a tyranny — it tells you 'this is correct' while robbing you of the courage to think for yourself.",
    "围绕你的匮乏重新组织这些信息，而不是被动接受。": "Reorganize this information around what you lack, rather than passively accepting it.",
    "以下从多个角度分析：": "Analysis from multiple perspectives:",
    "• 知识层面：": "• Knowledge perspective:",
    "• 现实层面：需要考虑实际应用场景": "• Practical perspective: considering real-world applications",
    "• 批判层面：每种分析都有其局限性": "• Critical perspective: every analysis has its limitations",

    # ── Thinker class labels ──
    "综上所述，": "In summary, ",
    "思考过程": "Thought Process",
    "模型": "Mode",
    "风格": "Style",
    "综合": "Synthetic",
    "综合视角": "Synthetic Perspective",
    "自动选择最合适的分析框架": "Automatically selects the best analytical framework",

    # ── Talker labels ──
    "定义说明": "Definition",
    "比较对比": "Comparison",
    "因果分析": "Causal Analysis",
    "多源知识": "Multi-source Knowledge",
    "对话回复": "Dialogue Reply",
    "表情": "Expression",
    "姿势": "Gesture",
    "语气": "Tone",
    "心情": "Mood",
    "动机": "Motive",
    "共情回应": "Empathy Response",
    "思考": "Thinking",
    "用户": "User",
    "助手": "Assistant",
    "系统": "System",
    "对话历史": "Conversation History",
    "当前输入": "Current Input",
    "上下文窗口": "Context Window",
    "[对话：{count}轮]": "[Conversation: {count} turns]",

    # ── Empathy templates (emotion_state.py) ──
    "感受到你的快乐了！能分享这个好消息吗？": "I can feel your joy! Would you like to share what's making you happy?",
    "真为你高兴！有什么开心事？": "I'm so happy for you! What's the good news?",
    "好心情会传染的，我也感觉开心起来了！": "Good mood is contagious — I'm feeling happier too!",
    "满足感是最踏实的幸福。": "Contentment is the most grounded form of happiness.",
    "能感受到你内心的充实，真好。": "I can feel the fulfillment in your heart — that's wonderful.",
    "知足常乐，你的心态很棒。": "Happiness comes from contentment. Your mindset is great.",
    "平静是一种很宝贵的状态。": "Calmness is a very precious state to be in.",
    "能保持平静的心态真好。": "It's good to maintain a calm mindset.",
    "愿这份宁静一直陪伴你。": "May this peace always be with you.",
    "爱是最温暖的力量。": "Love is the warmest force of all.",
    "能被爱和去爱都是幸福的事。": "Being loved and loving are both beautiful things.",
    "你心里有爱，这很美好。": "There's love in your heart — that's beautiful.",
    "有期待就有动力。愿你如愿以偿！": "Hope brings motivation. May your wishes come true!",
    "希望是照亮前路的光。": "Hope is the light that illuminates the road ahead.",
    "为你的期待加油！": "Rooting for your dreams!",
    "自信的人最有魅力。": "Confident people are the most attractive.",
    "相信自己是成功的第一步。": "Believing in yourself is the first step to success.",
    "你的自信很有感染力！": "Your confidence is contagious!",
    "我感受到你心里的难过。想聊聊是什么事吗？": "I can feel your sadness. Would you like to talk about what happened?",
    "难过的时候不要一个人扛，说出来会好受一些。": "Don't carry the sadness alone — talking about it helps.",
    "悲伤是正常的情绪，我在这里陪着你。": "Sadness is a normal emotion. I'm here with you.",
    "生气的时候，说出来会好受一点。发生什么了？": "When you're angry, talking about it helps. What happened?",
    "愤怒很正常，但别让它伤到自己。愿意说说吗？": "Anger is normal, but don't let it hurt you. Want to talk?",
    "我能感觉到你的不满。想说什么都可以。": "I can sense your frustration. You can say anything here.",
    "害怕的感觉很难受。你愿意说说在担心什么吗？": "Fear is uncomfortable. Would you like to share what's worrying you?",
    "恐惧是人的本能。说出来也许就没那么可怕了。": "Fear is human instinct. Speaking it out might make it less scary.",
    "不要怕，我在这里。能告诉我你担心什么吗？": "Don't be afraid, I'm here. Can you tell me what you're worried about?",
    "孤独确实让人难受。我会一直在这里陪你聊天。": "Loneliness really hurts. I'll always be here to chat with you.",
    "虽然我是AI，但我会尽力陪伴你。你不是一个人。": "I may be an AI, but I'll do my best to be here for you. You're not alone.",
    "孤独的时候，随便说点什么也好，我听着。": "When you feel lonely, just say anything at all — I'm listening.",
    "沮丧的时候，也许可以先休息一下。需要我帮忙吗？": "When you're feeling down, maybe take a break first. Need my help?",
    "每个人都会有低谷期。想聊聊让你沮丧的事吗？": "Everyone has low points. Want to talk about what's bringing you down?",
    "别太苛责自己，慢慢来。我在这里。": "Don't be too hard on yourself. Take it slow. I'm here.",
    "讨厌的感觉让人不舒服。发生了什么事？": "Feeling disgust is unpleasant. What happened?",
    "有些事确实让人反感，说出来会好一些。": "Some things are truly off-putting. Talking helps.",
    "哇，这确实让人意外！能细说说吗？": "Wow, that's really surprising! Can you tell me more?",
    "听起来很让人惊讶！发生了什么？": "That sounds astonishing! What happened?",
    "这还真是出乎意料呢。": "Well, that's quite unexpected.",
    "这个问题确实让人困惑。我们一起来理一理？": "This is indeed confusing. Let's work through it together?",
    "困惑是学习的开始。你想了解什么？": "Confusion is the beginning of learning. What do you want to understand?",
    "别着急，我帮你分析看看。": "Don't rush, let me help analyze it.",
    "思考是件好事。想到什么了？": "Thinking is a good thing. What's on your mind?",
    "看你正在思考，有什么想法可以和我分享。": "I see you're thinking. Feel free to share your thoughts with me.",
    "深思熟虑之后，往往会有新的发现。": "After careful thought, new discoveries often emerge.",
    "愿意说出来就是好的开始。我在这里听着。": "Being willing to speak up is a good start. I'm here listening.",
    "说出来会轻松一些。你可以信任我。": "Talking about it will make you feel lighter. You can trust me.",
    "不知道怎么办的时候，一步一步来就好。先说说发生了什么？": "When you don't know what to do, take it one step at a time. First, tell me what happened?",
    "迷茫是正常的。我们一起分析看看？": "Feeling lost is normal. Let's analyze it together?",
    "累了就休息一下。充电是为了走更远的路。": "Rest when you're tired. Recharging is for the longer journey ahead.",
    "辛苦你了。记得照顾好自己。": "You've been working hard. Remember to take care of yourself.",
    "听起来你内心有些纠结。两种想法都有道理。": "It sounds like you're torn inside. Both perspectives have merit.",
    "矛盾说明你在认真思考。不妨说说你的想法？": "Contradiction means you're thinking seriously. Why not share your thoughts?",
    "努力过却没有结果，确实让人挫败。但你的努力不会白费。": "Effort without results is truly frustrating. But your effort is not wasted.",
    "挫折是成长的一部分。你已经在路上了。": "Setbacks are part of growth. You're already on your way.",
    "思念说明那个人对你很重要。": "Missing someone means they matter to you.",
    "被思念是一种幸福。想聊聊他/她吗？": "Being missed is a kind of happiness. Want to talk about them?",
    "太棒了！恭喜你！你的努力没有白费。": "That's awesome! Congratulations! Your effort paid off.",
    "为你高兴！这是你应得的成果！": "So happy for you! You earned this!",
    "成功的感觉太好了！详细说说？": "Success feels amazing! Tell me more?",

    # ── COMFORT_PHRASES ──
    "我在这里陪着你。": "I'm here with you.",
    "一切都会好起来的。": "Everything will be okay.",
    "你做得已经够好了。": "You're doing well enough already.",
    "慢慢来，不着急。": "Take your time, no rush.",
    "你已经很勇敢了。": "You've been very brave.",
    "给自己一点时间。": "Give yourself some time.",

    # ── EmotionalState generic ──
    "我感觉到你有一些情绪波动。": "I sense you're having some emotional fluctuations.",
    "我感受到了你的情绪，能多说一些吗？": "I can feel your emotions. Could you tell me more?",

    # ── Additional labels ──
    "语言": "Language",
    "💾 已连接": "Connected",
    "⚠️ 未连接": "Not connected",
    "总调用": "total calls",
    "对话轮次": "Dialog turns",
    "条": "entries",
    "搜索": "Search",
    "缓存": "Cache",
    "ON": "ON",
    "OFF": "OFF",
    "状态报告": "Status Report",
    "M1 正式版": "M1 Release",
    "许可": "License",
    "深层思考": "Deep Thinking",
    "深度思考": "Deep Thinking",
    "进化": "Evolution",
    "进化状态": "Evolution Status",
    "交互": "Interactions",
    "升级次数": "Version Upgrades",
    "经验值": "XP",
    "全部无限使用": "Unlimited (All Features)",
    "本周剩余": "remaining this week",
    "到期": "Expires",
    "剩余": "remaining",
    "收款地址": "Payment Address",
    "付款后请联系激活": "Send payment receipt to activate",
    "话题": "Topics",
    "等级": "Level",
    "已探索话题": "Topics Explored",
    "最深入话题": "Deepest Topics",
    "深度": "Depth",
    "Free": "Free",
    "Pro": "Pro",
    "Plus": "Plus",
    "免费版": "Free",
    "Pro版": "Pro",
    "Plus版": "Plus",
    "次": " ",
    # ── 新增 M1 正式版条目 ──
    "注册成功": "Registration successful",
    "登录成功": "Login successful",
    "退出登录": "Logged out",
    "登录失败": "Login failed",
    "用户已存在": "Username already exists",
    "用户不存在": "User not found",
    "密码错误": "Incorrect password",
    "请先登录": "Please login first",
    "用户名": "Username",
    "密码": "Password",
    "账号管理": "Account Management",
    "已登录": "Logged in",
    "未登录": "Not logged in",
    "设置偏好": "Set Preference",
    "获取偏好": "Get Preference",
    "偏好已保存": "Preference saved",
    "账号已删除": "Account deleted",
    "无法删除": "Cannot delete",
    "取消": "Cancel",
    "确认密码": "Confirm Password",
    "密码不匹配": "Passwords do not match",
    "新功能": "New Feature",
    "功能名称": "Feature Name",
    "功能描述": "Feature Description",
    "额外提问额度": "Bonus Question Quota",
    "周额度": "Weekly Quota",
    "免费使用": "Free Usage",
    "已耗尽": "Exhausted",
    "升级奖励": "Upgrade Reward",
    "获得 {days} 天 Plus 免费升级": "Received {days}-day free Plus upgrade",
    "当前模型版本": "Current Model Version",
    "上次升级": "Last Upgrade",
    "总经验值": "Total XP",
    "里程碑": "Milestone",
    "月卡": "Monthly",
    "年卡": "Yearly",
    "高级功能": "Premium Features",
    "用户登录": "User Login",
    "账号安全": "Account Security",
    "偏好设置": "Preferences",
    "进化奖励": "Evolution Reward",
    "等级 {level}": "Level {level}",
    "开发新功能": "Develop New Feature",
    "自动开发": "Auto-develop",
    "预设模板": "Preset Templates",
    "动态生成": "Dynamic Generation",
    "功能开发中": "Feature in development",
    "升级奖励已发放": "Upgrade rewards have been distributed",
    "深度学习": "Deep Learning",
    "持续搜索": "Continuous Search",
    "经验值条": "XP Progress",
    "Plus 免费期": "Plus Trial",
    "Plus 到期": "Plus Expires",
    "Pro 到期": "Pro Expires",
}


class TranslationProvider:
    """
    Central translation provider for Tian AI.

    Usage:
        tr = TranslationProvider(lang='en')
        text = tr.t("你好")  # returns English translation
        text = tr.t("你好", name="World")  # supports format kwargs
        tr.lang = 'zh'  # switch to Chinese

    Keys are Chinese source strings. If no English translation is found
    and language is 'en', falls back to the key itself.
    """

    def __init__(self, lang: str = "en"):
        self._lang = "en"  # default language per requirement
        self.lang = lang  # use setter for validation

    @property
    def lang(self) -> str:
        return self._lang

    @lang.setter
    def lang(self, value: str):
        """Set language. Falls back to 'en' if unsupported."""
        if value in ("en", "zh"):
            self._lang = value
        else:
            self._lang = "en"  # default fallback

    def t(self, key: str, **kwargs) -> str:
        """
        Translate a Chinese key to the current language.

        Args:
            key: Chinese source string (or any string to look up)
            **kwargs: format arguments for the translated string

        Returns:
            Translated string, or the key itself if no translation found
            (when lang='zh', always returns the key as-is)
        """
        if self._lang == "zh":
            # Chinese mode: return key as-is (original)
            result = key
        else:
            # English mode: look up translation
            result = _EN.get(key, key)

        # Apply format arguments if provided
        if kwargs:
            try:
                result = result.format(**kwargs)
            except KeyError:
                pass  # leave as-is if format fails

        return result

    def translate_list(self, items: list) -> list:
        """Translate each string in a list."""
        return [self.t(item) for item in items]

    def translate_dict(self, d: dict, keys: list = None) -> dict:
        """
        Translate specific keys in a dict, or all string values if keys is None.
        """
        result = {}
        for k, v in d.items():
            if keys is None and isinstance(v, str):
                result[self.t(k) if isinstance(k, str) else k] = self.t(v)
            elif keys and isinstance(v, str) and k in keys:
                result[k] = self.t(v)
            else:
                result[k] = v
        return result


# ── Global singleton (for module-level imports) ──
T = TranslationProvider(lang="en")


def set_language(lang: str):
    """Set global language. 'en' or 'zh'."""
    T.lang = lang
