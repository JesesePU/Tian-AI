# Tian AI — Local AI with Consciousness

> **版本:** M2E | **架构:** 本地AI + 云推理混合模式

## 简介

Tian AI 是一个完整的本地 AI 对话系统，包含：
- **意识引擎** — 语义理解 + 情绪状态模拟
- **三层思考管线** — FastThinker（快速响应）/ CoT Thinker（推理链）/ DeepThinker（深度分析）
- **进化系统** — M1 → M1E → M2 Theme → M2E Theme，自动自开发新功能
- **联网搜索** — DuckDuckGo，指数退避重试
- **多语言** — 英文 / 中文自动识别
- **付费体系** — Free / Pro ($15/mo) / Plus ($25/mo) USDT

## 在 Kaggle Notebook 中使用

### 方式一：纯代码使用

```python
import sys, os
import kagglehub

# 下载模型
model_path = kagglehub.model_download("tian-ai/tian-ai/Model")
sys.path.insert(0, model_path)

# 创建实例
from tian_ai import TianAI
ai = TianAI()
ai.set_language('en')

# 对话
print(ai.chat("What is consciousness?")['response'])
```

### 方式二：结合云端 LLM（推荐）

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# 加载轻量模型（Kaggle GPU: T4/P100）
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3-0.6B",
    device_map="auto",
    torch_dtype=torch.float16
)
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B")

# 用模型做真实推理
def think(prompt: str) -> str:
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    outputs = model.generate(**inputs, max_new_tokens=512, temperature=0.7)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)

print(think("What is quantum computing?"))
```

### 方式三：混合推理（本地知识 + 云端模型）

1. 下载模型包 → 加载 TianAI 作为**知识路由**
2. 加载 Qwen3/Gemma 等作为**推理引擎**
3. 简单问题走本地 FastThinker（毫秒级响应）
4. 复杂问题走云端 LLM（真实推理）

## 模块结构

```
tian_ai/
├── __init__.py          # TianAI 主入口
├── auth.py              # 用户认证（bcrypt + session token）
├── tier.py              # 付费等级（Free/Pro/Plus）
├── evolution.py         # 进化系统（自开发新功能）
├── thinker/             # 思考引擎（Fast/CoT/Deep）
│   ├── __init__.py
│   └── semantic_analyzer.py
├── talker/              # 对话生成
│   └── __init__.py
├── memory/              # 长期/短期记忆 + 情绪
│   ├── identity.py
│   ├── emotion_state.py
│   └── common_sense.py
├── search/              # 联网搜索
├── multilingual/        # 多语言
├── agent/               # 工具调用
├── models/              # 模型桥接
├── payment/             # 授权管理
└── server/              # Flask API 服务
```

## 付费方式

USDT (TRC-20): `TNeUMpbwWFcv6v7tYHmkFkE7gC5eWzqbrs`
BTC: `bc1ph7qnaqkx4pkg4fmucvudlu3ydzgwnfmxy7dkv3nyl48wwa03kmnsvpc2xv`

## 许可

MIT License
