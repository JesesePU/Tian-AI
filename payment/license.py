#!/usr/bin/env python3
"""
Tian AI — 卡密（License Key）管理系统

功能：
- 生成卡密（免费/Pro/Plus 三种等级）
- 验证卡密并激活
- 配额管理（Pro每周刷新、Plus不限）
- SQLite存储

接入方式：
    python license.py generate pro     # 生成1个Pro卡密
    python license.py generate plus 5  # 生成5个Plus卡密
    python license.py list             # 列出所有卡密
    python license.py activate xxx     # 激活卡密
"""

import os
import sys
import time
import json
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

# ═══════════════════════════════════════════════
# 路径配置
# ═══════════════════════════════════════════════

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, 'licenses.db')


# ═══════════════════════════════════════════════
# 三级定义
# ═══════════════════════════════════════════════

TIERS = {
    'free': {
        'name': 'Free',
        'price_usdt': 0,
        'price_btc': 0,
        'features': {
            'chat_daily': 100,
            'knowledge_range': 'basic_30',
            'styles': ['zonghe'],
            'image_gen': False,
            'video_gen': False,
            'agent_level': 'none',
            'evolution': 0,
        },
        'durations': {'monthly': None},
        'description': 'Basic chat, 100 messages/day. Good for trying out.',
    },
    'pro_monthly': {
        'name': 'Pro Monthly',
        'price_usdt': 9.99,
        'price_btc': 0.00015,
        'features': {
            'chat_daily': -1,
            'knowledge_range': 'full',
            'styles': ['huchenfeng', 'fengge', 'zhangxuefeng', 'weimingzi', 'zonghe'],
            'image_gen': True,
            'image_weekly': 100,
            'video_gen': True,
            'video_weekly': 20,
            'agent_level': 'basic',
            'evolution': 5,
        },
        'duration_days': 30,
        'weekly_reset': True,
        'description': 'All features. 100 images + 20 videos + 5 evolutions/week.',
    },
    'pro_yearly': {
        'name': 'Pro Yearly',
        'price_usdt': 99.99,
        'price_btc': 0.0015,
        'features': {
            'chat_daily': -1,
            'knowledge_range': 'full',
            'styles': ['huchenfeng', 'fengge', 'zhangxuefeng', 'weimingzi', 'zonghe'],
            'image_gen': True,
            'image_weekly': 100,
            'video_gen': True,
            'video_weekly': 20,
            'agent_level': 'basic',
            'evolution': 5,
        },
        'duration_days': 365,
        'weekly_reset': True,
        'description': 'Pro features at 2 months free. Best value.',
    },
    'plus_monthly': {
        'name': 'Plus Monthly',
        'price_usdt': 29.99,
        'price_btc': 0.00045,
        'features': {
            'chat_daily': -1,
            'knowledge_range': 'full_deep',
            'styles': ['huchenfeng', 'fengge', 'zhangxuefeng', 'weimingzi', 'zonghe', 'mix'],
            'image_gen': True,
            'image_weekly': -1,
            'video_gen': True,
            'video_weekly': -1,
            'agent_level': 'advanced',
            'evolution': -1,
            'priority': True,
        },
        'duration_days': 30,
        'weekly_reset': False,
        'description': 'Unlimited everything. Priority queue. Priority support.',
    },
    'plus_yearly': {
        'name': 'Plus Yearly',
        'price_usdt': 299.99,
        'price_btc': 0.0045,
        'features': {
            'chat_daily': -1,
            'knowledge_range': 'full_deep',
            'styles': ['huchenfeng', 'fengge', 'zhangxuefeng', 'weimingzi', 'zonghe', 'mix'],
            'image_gen': True,
            'image_weekly': -1,
            'video_gen': True,
            'video_weekly': -1,
            'agent_level': 'advanced',
            'evolution': -1,
            'priority': True,
        },
        'duration_days': 365,
        'weekly_reset': False,
        'description': 'Plus features at 2 months free. Best value for power users.',
    },
}

# Display groupings
PLAN_GROUPS = {
    'free': ['free'],
    'pro': ['pro_monthly', 'pro_yearly'],
    'plus': ['plus_monthly', 'plus_yearly'],
}


# ═══════════════════════════════════════════════
# 数据库操作
# ═══════════════════════════════════════════════

def _init_db():
    """初始化卡密数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            key_id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            tier TEXT NOT NULL,
            status TEXT DEFAULT 'unused',
            created_at TEXT NOT NULL,
            activated_at TEXT,
            activated_by TEXT,
            expires_at TEXT,
            quota_image INTEGER DEFAULT 0,
            quota_video INTEGER DEFAULT 0,
            quota_evolution INTEGER DEFAULT 0,
            last_quota_reset TEXT
        )
    ''')
    conn.commit()
    conn.close()


def _generate_key(prefix: str = 'TA') -> str:
    """生成唯一卡密，格式: TA-XXXX-XXXX-XXXX"""
    rand = secrets.token_hex(6).upper()
    return f"{prefix}-{rand[:4]}-{rand[4:8]}-{rand[8:12]}"


def generate_license(tier: str, count: int = 1, prefix: str = 'TA') -> list:
    """批量生成卡密"""
    _init_db()
    _validate_tier(tier)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    keys = []
    tier_def = TIERS[tier]
    today = datetime.now().isoformat()
    
    for _ in range(count):
        while True:
            key = _generate_key(prefix)
            # 检查不重复
            c.execute('SELECT 1 FROM licenses WHERE license_key = ?', (key,))
            if not c.fetchone():
                break
        
        c.execute('''
            INSERT INTO licenses 
            (license_key, tier, status, created_at, 
             quota_image, quota_video, quota_evolution, last_quota_reset)
            VALUES (?, ?, 'unused', ?, ?, ?, ?, ?)
        ''', (
            key, tier, today,
            tier_def['features'].get('image_weekly', 0),
            tier_def['features'].get('video_weekly', 0),
            tier_def['features'].get('evolution', 0) if isinstance(tier_def['features'].get('evolution'), int) else -1,
            today,
        ))
        keys.append({'key': key, 'tier': tier})
    
    conn.commit()
    conn.close()
    return keys


def validate_license(license_key: str) -> Optional[dict]:
    """
    验证卡密并激活
    返回卡密信息，如果无效返回None
    """
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return None
    
    data = dict(row)
    
    if data['status'] == 'used':
        conn.close()
        return {'error': '该卡密已被使用', **data}
    if data['status'] == 'expired':
        conn.close()
        return {'error': '该卡密已过期', **data}
    
    # Activate
    now = datetime.now().isoformat()
    
    # Calculate expiry based on tier's duration_days
    tier = data['tier']
    tier_def = TIERS.get(tier, {})
    duration = tier_def.get('duration_days')
    if duration:
        expires = (datetime.now() + timedelta(days=duration)).isoformat()
    else:
        expires = None
    
    c.execute('''
        UPDATE licenses SET 
            status = 'used', 
            activated_at = ?,
            expires_at = ?
        WHERE license_key = ? AND status = 'unused'
    ''', (now, expires, license_key))
    
    conn.commit()
    conn.close()
    
    return {
        'status': 'activated',
        'tier': data['tier'],
        'expires_at': expires,
        'features': TIERS[data['tier']]['features'],
        'message': f"{TIERS[tier]['name']}已激活！有效期至{expires[:10] if expires else '永久'}",
    }


def get_license_info(license_key: str) -> Optional[dict]:
    """查询卡密信息（不激活）"""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def list_licenses(status: str = None) -> list:
    """列出所有卡密"""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if status:
        c.execute('SELECT * FROM licenses WHERE status = ? ORDER BY created_at DESC', (status,))
    else:
        c.execute('SELECT * FROM licenses ORDER BY created_at DESC')
    
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def check_quota(license_key: str, resource: str) -> dict:
    """
    检查配额
    
    Args:
        license_key: 卡密
        resource: 'image', 'video', 'evolution'
    
    Returns:
        {'allowed': bool, 'remaining': int, 'total': int, 'reset': str}
    """
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return {'allowed': False, 'error': '无效卡密'}
    
    data = dict(row)
    tier = data['tier']
    tier_feat = TIERS[tier]['features']
    
    # Plus版（plus_monthly / plus_yearly）不限
    if tier.startswith('plus'):
        conn.close()
        return {'allowed': True, 'remaining': -1, 'total': -1, 'reset': 'never'}
    
    # 免费版没有配额
    if tier == 'free':
        conn.close()
        return {'allowed': False, 'remaining': 0, 'total': 0, 'reset': 'never'}
    
    # Pro版检查每周配额
    quota_col = {
        'image': 'quota_image',
        'video': 'quota_video',
        'evolution': 'quota_evolution',
    }.get(resource)
    
    weekly_max = {
        'image': tier_feat.get('image_weekly', 0),
        'video': tier_feat.get('video_weekly', 0),
        'evolution': tier_feat.get('evolution', 0) if isinstance(tier_feat.get('evolution'), int) else 0,
    }.get(resource, 0)
    
    remaining = data[quota_col]
    
    # 检查是否需要重置（每周一）
    if TIERS[tier].get('weekly_reset'):
        last_reset = data.get('last_quota_reset', '')
        if _needs_weekly_reset(last_reset):
            remaining = weekly_max
            c.execute(f'UPDATE licenses SET {quota_col} = ?, last_quota_reset = ? WHERE license_key = ?',
                      (weekly_max, datetime.now().isoformat(), license_key))
            conn.commit()
    
    conn.close()
    return {
        'allowed': remaining > 0 or remaining == -1,
        'remaining': remaining,
        'total': weekly_max,
        'reset': 'weekly',
    }


def use_quota(license_key: str, resource: str) -> dict:
    """
    消耗一次配额
    """
    result = check_quota(license_key, resource)
    if not result.get('allowed'):
        return result
    
    if result['remaining'] == -1:  # 不限
        return {'allowed': True, 'remaining': -1}
    
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    quota_col = {
        'image': 'quota_image',
        'video': 'quota_video',
        'evolution': 'quota_evolution',
    }.get(resource)
    
    c.execute(f'UPDATE licenses SET {quota_col} = {quota_col} - 1 WHERE license_key = ?',
              (license_key,))
    conn.commit()
    conn.close()
    
    return {'allowed': True, 'remaining': result['remaining'] - 1}


def _validate_tier(tier: str):
    if tier not in TIERS:
        print(f"错误: 无效等级 '{tier}'，可选: {', '.join(TIERS.keys())}")
        sys.exit(1)


def _needs_weekly_reset(last_reset: str) -> bool:
    """检查是否需要每周重置"""
    if not last_reset:
        return True
    try:
        last = datetime.fromisoformat(last_reset)
        now = datetime.now()
        # 如果上次重置超过7天
        return (now - last).days >= 7
    except:
        return True


# ═══════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python license.py generate <tier> [count]    Generate license key(s)")
        print("  python license.py list [status]               List license keys")
        print("  python license.py activate <key>              Activate a license")
        print("  python license.py info <key>                  Query license info")
        print("  python license.py quota <key> <resource>      Check quota")
        print()
        print("Tiers: free, pro_monthly, pro_yearly, plus_monthly, plus_yearly")
        print("Resources: image, video, evolution")
        sys.exit(0)
    
    action = sys.argv[1]
    
    if action == 'generate':
        tier = sys.argv[2] if len(sys.argv) > 2 else 'pro_monthly'
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        _validate_tier(tier)
        keys = generate_license(tier, count)
        print(f"Generated {count} {TIERS[tier]['name']} key(s):")
        for k in keys:
            print(f"   {k['key']}")
    
    elif action == 'list':
        status = sys.argv[2] if len(sys.argv) > 2 else None
        rows = list_licenses(status)
        print(f"📋 共 {len(rows)} 个卡密:")
        for r in rows:
            print(f"   [{r['status']:>6}] {r['license_key']} — {r['tier']} — 创建: {r['created_at'][:10]}")
    
    elif action == 'activate':
        key = sys.argv[2]
        result = validate_license(key)
        if result:
            print(f"✅ {result.get('message', '激活成功')}")
        else:
            print("❌ 无效卡密")
    
    elif action == 'info':
        key = sys.argv[2]
        info = get_license_info(key)
        if info:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print("❌ 卡密不存在")
    
    elif action == 'quota':
        key = sys.argv[2]
        resource = sys.argv[3]
        result = check_quota(key, resource)
        print(json.dumps(result, ensure_ascii=False, indent=2))
