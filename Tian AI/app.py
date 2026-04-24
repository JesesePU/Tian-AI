"""
Tian AI — Hugging Face Space 入口
部署到 HF Spaces: 选择 Gradio SDK，上传此文件 + tian_ai/ 目录

用法：
  - 直接提交到 Hugging Face Spaces
  - 或者本地测试：pip install gradio && python app.py
"""
import os, sys, json

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import gradio as gr
from tian_ai import TianAI

# ── 全局实例 ──
ai = TianAI(
    enable_search=True,
    memory_store_path=os.path.join(
        os.environ.get("TMPDIR", os.environ.get("HOME", "/tmp")),
        "tian_ai_memory.json",
    ),
)

print(f"Tian AI {ai.current_version} loaded | {ai.tier.tier_display}")


def respond(message: str, history: list) -> str:
    """ChatInterface callback"""
    if not message or not message.strip():
        return ""
    try:
        result = ai.chat(message)
        response = result.get("response", "")
        version = result.get("version", ai.current_version)
        mode = result.get("thinker_mode", "fast")
        search = " 🌐" if result.get("search_used") else ""
        return f"{response}  [{mode.upper()}]{search} v{version}"
    except Exception as e:
        return f"Error: {e}"


# ── 界面 ──
with gr.Blocks(
    title="Tian AI",
    theme=gr.themes.Soft(primary_hue="blue", neutral_hue="stone"),
) as demo:
    gr.Markdown(
        "# 🤖 Tian AI\n"
        "Local AI — thinking modes, web search, evolving intelligence.\n\n"
        "Ask anything or try the examples below."
    )

    gr.ChatInterface(
        fn=respond,
        title=None,
        examples=[
            "What is quantum computing?",
            "Explain neural networks",
            "Who are you?",
            "Latest AI news 2025",
            "What is 2+2?",
        ],
    )

    # 底部状态
    def status_line():
        evo = ai.evolution.get_status()
        return (
            f"**Tian AI** v{evo['version_display']} | "
            f"{ai.tier.tier_display} | "
            f"{evo['xp']}/{evo['milestone_xp']} XP | "
            f"{evo['total_interactions']} interactions | "
            f"HF Spaces CPU"
        )

    status = gr.Markdown(status_line)
    demo.load(status_line, outputs=status, every=60)

if __name__ == "__main__":
    demo.launch()
