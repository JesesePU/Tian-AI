"""
Tian AI M1 — Tier / Subscription System
═══════════════════════════════════════════════

Three-tier subscription model:
  - Free  : Unlimited Q&A + daily 10 image/audio generation
  - Pro   : Deep thinking + weekly 50 quota for ALL features (incl. new features)
            $15/mo or $185/yr
  - Plus  : Unlimited everything (monthly/annual card)
            $25/mo or $275/yr
            New features developed by Evolution are free for Plus users
            until their subscription expires.

Evolution Upgrade Bonus:
  When Evolution Engine achieves a version bump (M1.0 → M1.1),
  all Pro and Plus users whose subscription hasn't expired get a
  FREE 1-month Plus upgrade to the new model version.

Cryptocurrency payment:
  USDT(TRC-20): TNeUMpbwWFcv6v7tYHmkFkE7gC5eWzqbrs
  BTC         : bc1ph7qnaqkx4pkg4fmucvudlu3ydzgwnfmxy7dkv3nyl48wwa03kmnsvpc2xv

Data persisted to tier_store.json
"""

import time
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from .multilingual import TranslationProvider


# ═══════════════════════════════════════════════
# Pricing (User's final prices)
# ═══════════════════════════════════════════════

PRICES = {
    'pro_monthly':  {'usdt': 15,  'btc': 0.00022, 'label': 'Pro 月卡', 'days': 30},
    'pro_yearly':   {'usdt': 185, 'btc': 0.00275, 'label': 'Pro 年卡', 'days': 365},
    'plus_monthly': {'usdt': 25,  'btc': 0.00037, 'label': 'Plus 月卡', 'days': 30},
    'plus_yearly':  {'usdt': 275, 'btc': 0.00410, 'label': 'Plus 年卡', 'days': 365},
}

CRYPTO_WALLETS = {
    'usdt_trc20': 'TNeUMpbwWFcv6v7tYHmkFkE7gC5eWzqbrs',
    'btc':        'bc1ph7qnaqkx4pkg4fmucvudlu3ydzgwnfmxy7dkv3nyl48wwa03kmnsvpc2xv',
}

DAILY_USAGE_TYPES = ['image', 'audio']           # Free tier: daily cap
WEEKLY_USAGE_TYPES = ['image', 'audio', 'video', 'other']  # Pro tier: weekly cap

# Evolution upgrade bonus: days of free Plus
EVOLUTION_UPGRADE_PLUS_DAYS = 30


def _today() -> str:
    return datetime.now().strftime('%Y-%m-%d')

def _this_week() -> str:
    # ISO week string (e.g., "2026-W17")
    now = datetime.now()
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


class TierManager:
    """
    Manages subscription tiers, quota tracking, and payment info.

    Data stored in tier_store.json:
      - tier: 'free'|'pro'|'plus'
      - pro_expires: timestamp or 0
      - plus_expires: timestamp or 0
      - daily_usage: {date: {type: count}}
      - weekly_usage: {week: {type: count}}
      - evolution_free_plus_from: timestamp (0 if none active)
      - evolution_free_plus_to: timestamp (0 if none active)
    """

    def __init__(self, store_path: str = 'tier_store.json',
                 tr: Optional[TranslationProvider] = None):
        self.tr = tr or TranslationProvider(lang="en")

        # Tier state
        self._tier = 'free'
        self._pro_expires: float = 0
        self._plus_expires: float = 0

        # Evolution free Plus (granted when version bumps)
        self._evo_plus_from: float = 0
        self._evo_plus_to: float = 0

        # Usage tracking
        self._daily_usage: Dict[str, Dict[str, int]] = {}
        self._weekly_usage: Dict[str, Dict[str, int]] = {}

        # Persistence
        self.store_path = store_path
        self._load()

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
            self._tier = data.get('tier', 'free')
            self._pro_expires = data.get('pro_expires', 0)
            self._plus_expires = data.get('plus_expires', 0)
            self._evo_plus_from = data.get('evo_plus_from', 0)
            self._evo_plus_to = data.get('evo_plus_to', 0)
            self._daily_usage = data.get('daily_usage', {})
            self._weekly_usage = data.get('weekly_usage', {})
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save(self):
        path = self._get_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump({
                'tier': self._tier,
                'pro_expires': self._pro_expires,
                'plus_expires': self._plus_expires,
                'evo_plus_from': self._evo_plus_from,
                'evo_plus_to': self._evo_plus_to,
                'daily_usage': self._daily_usage,
                'weekly_usage': self._weekly_usage,
                'last_save': time.time(),
            }, f, indent=2)

    # ── Tier detection ──

    def _check_expiry(self):
        """Check all expirations and auto-downgrade if needed."""
        now = time.time()
        changed = False

        # Check evolution free Plus
        if self._evo_plus_to > 0 and now > self._evo_plus_to:
            self._evo_plus_from = 0
            self._evo_plus_to = 0
            changed = True

        # Check paid Plus
        if self._plus_expires > 0 and now > self._plus_expires:
            self._plus_expires = 0
            changed = True

        # Check Pro
        if self._pro_expires > 0 and now > self._pro_expires:
            self._pro_expires = 0
            changed = True

        # Determine effective tier (evolution Plus has highest priority during its period)
        evo_plus_active = self._evo_plus_to > 0 and now <= self._evo_plus_to
        plus_active = self._plus_expires > 0 and now <= self._plus_expires
        pro_active = self._pro_expires > 0 and now <= self._pro_expires

        old_tier = self._tier
        if evo_plus_active or plus_active:
            self._tier = 'plus'
        elif pro_active:
            self._tier = 'pro'
        else:
            self._tier = 'free'

        if self._tier != old_tier:
            changed = True

        if changed:
            self.save()

    @property
    def tier(self) -> str:
        self._check_expiry()
        return self._tier

    @property
    def is_premium(self) -> bool:
        return self.tier in ('pro', 'plus')

    @property
    def has_deep_thinking(self) -> bool:
        return self.tier in ('pro', 'plus')

    @property
    def tier_display(self) -> str:
        t = self.tier
        if t == 'plus':
            evo_active = self._evo_plus_to > 0 and time.time() <= self._evo_plus_to
            if evo_active:
                return "Plus (进化升级)"
        return t.capitalize()

    # ── Activation ──

    def activate_pro(self, days: int):
        """Activate Pro for N days."""
        now = time.time()
        if self._pro_expires > now:
            self._pro_expires += days * 86400  # extend
        else:
            self._pro_expires = now + days * 86400
        self.save()

    def activate_plus(self, days: int):
        """Activate Plus for N days."""
        now = time.time()
        if self._plus_expires > now:
            self._plus_expires += days * 86400  # extend
        else:
            self._plus_expires = now + days * 86400
        self.save()

    def grant_evolution_plus(self, days: int = EVOLUTION_UPGRADE_PLUS_DAYS):
        """
        Grant free Plus upgrade from Evolution version bump.
        If user already has an active evolution Plus, extends it.
        Resets ANY existing evolution Plus to start from now.
        """
        now = time.time()
        self._evo_plus_from = now
        self._evo_plus_to = now + days * 86400
        self.save()

    def has_active_evolution_plus(self) -> bool:
        now = time.time()
        return self._evo_plus_to > 0 and now <= self._evo_plus_to

    # ── Quota checking ──

    def can_use(self, usage_type: str) -> bool:
        """Check if user can use a feature of given type."""
        t = self.tier

        if t == 'plus':
            return True

        today = _today()
        week = _this_week()

        if t == 'free':
            if usage_type not in DAILY_USAGE_TYPES:
                return False  # Free can only do image/audio generation
            cap = 10  # daily
            used = self._daily_usage.get(today, {}).get(usage_type, 0)
            return used < cap

        if t == 'pro':
            cap = 50  # weekly total across all types
            used = sum(self._weekly_usage.get(week, {}).values())
            return used < cap

        return False

    def record_usage(self, usage_type: str):
        """Record one usage event."""
        t = self.tier
        if t == 'plus':
            return  # no tracking

        today = _today()
        week = _this_week()

        if t == 'free':
            daily = self._daily_usage.setdefault(today, {})
            daily[usage_type] = daily.get(usage_type, 0) + 1

        if t == 'pro':
            weekly = self._weekly_usage.setdefault(week, {})
            weekly[usage_type] = weekly.get(usage_type, 0) + 1

        self.save()

    def get_quota_remaining(self, usage_type: str) -> dict:
        """Get remaining quota info for a usage type."""
        t = self.tier
        if t == 'plus':
            return {'total': -1, 'used': 0, 'remaining': -1}

        today = _today()
        week = _this_week()

        if t == 'free':
            cap = 10
            used = self._daily_usage.get(today, {}).get(usage_type, 0)
            return {'total': cap, 'used': used, 'remaining': max(0, cap - used)}

        if t == 'pro':
            cap = 50
            used = sum(self._weekly_usage.get(week, {}).values())
            return {'total': cap, 'used': used, 'remaining': max(0, cap - used)}

        return {'total': 0, 'used': 0, 'remaining': 0}

    def get_all_quotas(self) -> dict:
        result = {}
        for utype in ['image', 'audio', 'video', 'other']:
            result[utype] = self.get_quota_remaining(utype)
        return result

    # ── Payment info ──

    def get_payment_info(self, plan: str) -> dict:
        info = PRICES.get(plan, {})
        return {
            'price_usdt': info.get('usdt', 0),
            'price_btc': info.get('btc', 0),
            'usdt_wallet': CRYPTO_WALLETS['usdt_trc20'],
            'btc_wallet': CRYPTO_WALLETS['btc'],
            'plan_label': info.get('label', plan),
            'plan_key': plan,
        }

    def list_plans(self) -> list:
        plans = []
        for key, info in PRICES.items():
            plans.append({
                'key': key,
                'label': info['label'],
                'usdt': info['usdt'],
                'btc': info['btc'],
                'days': info['days'],
            })
        return plans

    # ── Status ──

    def get_status(self) -> dict:
        self._check_expiry()
        pro_exp = self._pro_expires
        plus_exp = self._plus_expires
        evo_plus = self._evo_plus_to if self.has_active_evolution_plus() else 0

        return {
            'tier': self.tier,
            'tier_display': self.tier_display,
            'is_premium': self.is_premium,
            'has_deep_thinking': self.has_deep_thinking,
            'pro_expires': datetime.fromtimestamp(pro_exp).isoformat() if pro_exp else None,
            'plus_expires': datetime.fromtimestamp(plus_exp).isoformat() if plus_exp else None,
            'evo_plus_expires': datetime.fromtimestamp(evo_plus).isoformat() if evo_plus else None,
            'quotas': self.get_all_quotas(),
        }

    def format_status(self) -> str:
        s = self.get_status()
        lines = [
            f"━━ {self.tr.t('许可')}: {s['tier_display']} ━━",
            f"  {self.tr.t('深层思考')}: {'✓' if s['has_deep_thinking'] else '✗'}",
        ]

        if s['tier'] == 'free':
            for utype in DAILY_USAGE_TYPES:
                q = s['quotas'].get(utype, {})
                cap = q.get('total', 0)
                rem = q.get('remaining', 0)
                lines.append(f"  {utype}: {rem}/{cap} {self.tr.t('剩余')}")

        elif s['tier'] == 'pro':
            lines.append(f"  {self.tr.t('本周新功能额度')}: {self._weekly_remaining()}/50")
            if s['pro_expires']:
                lines.append(f"  {self.tr.t('到期')}: {s['pro_expires']}")

        elif s['tier'] == 'plus':
            lines.append(f"  {self.tr.t('全部无限使用')}")
            if s['evo_plus_expires']:
                lines.append(f"  {self.tr.t('进化升级')}: {s['evo_plus_expires']}")
            if s['plus_expires']:
                lines.append(f"  {self.tr.t('到期')}: {s['plus_expires']}")

        return '\n'.join(lines)

    def _weekly_remaining(self) -> int:
        week = _this_week()
        used = sum(self._weekly_usage.get(week, {}).values())
        return max(0, 50 - used)

    def format_payment(self, plan: str) -> str:
        info = self.get_payment_info(plan)
        lines = [
            f"━━ {info['plan_label']} ━━",
            f"USDT: {info['price_usdt']} USDT (TRC-20)",
            f"BTC:  {info['price_btc']} BTC",
            "",
            f"{self.tr.t('收款地址')}:",
            f"USDT(TRC-20): {info['usdt_wallet']}",
            f"BTC:          {info['btc_wallet']}",
            "",
            self.tr.t("付款后请联系激活"),
        ]
        return '\n'.join(lines)
