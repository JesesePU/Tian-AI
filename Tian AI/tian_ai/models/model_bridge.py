#!/usr/bin/env python3
"""
Tian AI — Model Bridge Layer

负责在 Kaggle 云端调用图像/视频生成模型，本地仅做请求转发。
完整模型源代码存放在 ../models_source/ 目录：

  models_source/
    deepseek/   — DeepSeek-V3 推理代码
    qwen/       — Qwen3 推理/评估代码
    gemma/      — Gemma 3 JAX/Flax 训练推理代码
    sd3/        — Stable Diffusion 3.5 pipeline
    flux/       — FLUX.1 rectified flow 模型代码
    cogvideo/   — CogVideoX 视频生成代码
    opensora/   — Open-Sora ST-DiT 视频生成代码
    whisper/    — OpenAI Whisper 语音识别/翻译
    bark/       — Suno Bark 文字转语音 (TTS)
    audiocraft/ — Meta AudioCraft 音乐/音频生成
    triposr/    — TripoSR 单图转3D模型
    pointe/     — OpenAI Point-E 文本/图像转3D点云

使用方式（在 Kaggle 上）:
  bridge = ModelBridge(license_key='xxx')
  result = bridge.generate('image', prompt='a cat')
  result = bridge.generate('audio', prompt='jazz piano')
  result = bridge.generate('3d', prompt='a chair')

本地环境运行时返回 stub 信息（因缺少 PyTorch/GPU）。
"""

import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SUPPORTED = ['image', 'video', 'audio', '3d']

MODEL_INFO = {
    # ── LLM (reasoning / language) ──
    'deepseek': {
        'type': 'llm', 'name': 'DeepSeek-V3',
        'params': '671B (MoE)', 'vram_min': '— (Kaggle only)',
        'task': 'reasoning_cot',
        'kaggle': True, 'pipe': None,
        'source': 'deepseek/',
    },
    'qwen': {
        'type': 'llm', 'name': 'Qwen3',
        'params': '235M-235B', 'vram_min': '— (Kaggle only)',
        'task': 'thinker_talker_llm',
        'kaggle': True, 'pipe': None,
        'source': 'qwen/',
    },
    'gemma': {
        'type': 'llm', 'name': 'Gemma 3',
        'params': '2B-27B', 'vram_min': '— (Kaggle only)',
        'task': 'jax_flax_llm',
        'kaggle': True, 'pipe': None,
        'source': 'gemma/',
    },
    # ── Image Generation ──
    'sd3': {
        'type': 'image', 'name': 'Stable Diffusion 3.5 Medium',
        'params': '2B', 'vram_min': '8GB', 'vram_rec': '12GB',
        'steps': 28, 'cfg': 7.0, 'res': '1024x1024',
        'kaggle': True, 'pipe': 'StableDiffusion3Pipeline',
        'source': 'sd3/',
    },
    'flux': {
        'type': 'image', 'name': 'FLUX.1-schnell',
        'params': '12B', 'vram_min': '6GB(4bit)', 'vram_rec': '24GB',
        'steps': 4, 'cfg': 3.5, 'res': '1024x1024',
        'kaggle': False, 'pipe': 'FluxPipeline',
        'source': 'flux/',
    },
    # ── Video Generation ──
    'cogvideo': {
        'type': 'video', 'name': 'CogVideoX-2B',
        'params': '2B', 'vram_min': '12GB', 'vram_rec': '16GB',
        'steps': 50, 'cfg': 6.0, 'res': '480x720', 'frames': 49,
        'kaggle': True, 'pipe': 'CogVideoXPipeline',
        'source': 'cogvideo/',
    },
    'opensora': {
        'type': 'video', 'name': 'Open-Sora STDiT-3',
        'params': '1.1B', 'vram_min': '8GB', 'vram_rec': '16GB',
        'steps': 30, 'cfg': 7.0, 'res': '360p', 'frames': 32,
        'kaggle': True, 'pipe': None,
        'source': 'opensora/',
    },
    # ── Audio / Speech ──
    'whisper': {
        'type': 'audio', 'name': 'OpenAI Whisper large-v3',
        'params': '1.5B', 'vram_min': '4GB', 'vram_rec': '8GB',
        'task': 'speech_recognition', 'lang': 'multilingual',
        'kaggle': True, 'pipe': None,
        'source': 'whisper/',
    },
    'bark': {
        'type': 'audio', 'name': 'Suno Bark',
        'params': '~1.2B', 'vram_min': '4GB', 'vram_rec': '8GB',
        'task': 'text_to_speech', 'lang': 'multilingual',
        'kaggle': True, 'pipe': None,
        'source': 'bark/',
    },
    'audiocraft': {
        'type': 'audio', 'name': 'Meta AudioCraft (MusicGen)',
        'params': '1.5B (large)', 'vram_min': '6GB', 'vram_rec': '12GB',
        'task': 'music_generation', 'lang': 'multilingual',
        'kaggle': True, 'pipe': 'MusicGen',
        'source': 'audiocraft/',
    },
    # ── 3D Generation ──
    'triposr': {
        'type': '3d', 'name': 'TripoSR (Stability AI + Tripo)',
        'params': '~300M', 'vram_min': '4GB', 'vram_rec': '8GB',
        'task': 'image_to_3d', 'res': '512x512',
        'kaggle': True, 'pipe': None,
        'source': 'triposr/',
    },
    'pointe': {
        'type': '3d', 'name': 'OpenAI Point-E',
        'params': '~1B', 'vram_min': '4GB', 'vram_rec': '8GB',
        'task': 'text_to_3d', 'res': 'point_cloud',
        'kaggle': True, 'pipe': None,
        'source': 'pointe/',
    },
}


class ModelBridge:
    """模型桥接器：本地 stub → Kaggle 真实推理"""

    def __init__(self, license_key=None):
        self.license_key = license_key
        self.is_kaggle = self._detect_kaggle()
        self.stats = {'calls': 0, 'total_time': 0.0}

    def _detect_kaggle(self):
        return os.environ.get('KAGGLE_KERNEL_RUN_TYPE') is not None or os.path.exists('/kaggle')

    def generate(self, media_type, prompt, negative_prompt='', steps=None, cfg_scale=None, **kw):
        start = time.time()
        from tian_ai.payment.license import use_quota
        if self.license_key:
            q = use_quota(self.license_key, media_type)
            if not q.get('allowed'):
                return {'success': False, 'error': f'Quota exhausted: {q.get("error", "upgrade required")}'}
        model_id = self._pick_model(media_type)
        if not model_id:
            return {'success': False, 'error': f'Unsupported type: {media_type} (supported: {SUPPORTED})'}
        info = MODEL_INFO[model_id]
        steps = steps or info.get('steps', 50)
        cfg_scale = cfg_scale or info.get('cfg', 7.0)
        result = self._generate_real(model_id, prompt, negative_prompt, steps, cfg_scale, **kw) if self.is_kaggle \
                 else self._generate_stub(model_id, prompt, steps, cfg_scale)
        result['time'] = round(time.time() - start, 2)
        self.stats['calls'] += 1
        self.stats['total_time'] += result['time']
        return result

    def _pick_model(self, media_type):
        candidates = [(m, i) for m, i in MODEL_INFO.items() if i['type'] == media_type]
        if not candidates:
            return None
        candidates.sort(key=lambda x: (x[1].get('kaggle', False), x[1].get('vram_min', '99GB')), reverse=True)
        return candidates[0][0]

    def _generate_stub(self, model_id, prompt, steps, cfg):
        info = MODEL_INFO[model_id]
        return {
            'success': True, 'stub': True, 'model_used': model_id,
            'message': (
                f"[Stub] {info['name']} will run on Kaggle\n"
                f"  Prompt: {prompt[:60]}\n"
                f"  Steps: {steps}, CFG: {cfg}\n"
                f"  VRAM: {info.get('vram_min', 'N/A')}\n"
                f"  Task: {info.get('task', 'N/A')}\n"
                f"  Source code: {info['source']}"
            ),
        }

    def _generate_real(self, model_id, prompt, negative_prompt, steps, cfg, **kw):
        """Kaggle 真实推理入口。模型源码在 models_source/ 目录中。"""
        raise NotImplementedError(
            f"Kaggle inference for {model_id} is delegated to the Kaggle notebook. "
            f"See models_source/{model_id}/ for source code."
        )

    def status(self):
        return {
            'platform': 'kaggle' if self.is_kaggle else 'local',
            'license': self.license_key or 'none',
            'models': {m: {'type': i['type'], 'name': i['name'], 'ready': i.get('kaggle', False), 'source': i['source']}
                       for m, i in MODEL_INFO.items()},
            'stats': self.stats,
        }

    def list_sources(self):
        """返回所有模型源码目录的信息"""
        import subprocess
        sources_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'models_source')
        result = {}
        for name, info in MODEL_INFO.items():
            rel = info['source'].lstrip('/')
            src = os.path.join(sources_dir, rel)
            py_count = 0
            if os.path.isdir(src):
                out = subprocess.run(
                    ['find', src, '-name', '*.py', '-type', 'f'],
                    capture_output=True, text=True
                ).stdout.strip()
                py_count = len(out.split('\n')) if out else 0
            result[name] = {
                'path': info['source'],
                'py_files': py_count,
                'exists': os.path.isdir(src),
            }
        return result
