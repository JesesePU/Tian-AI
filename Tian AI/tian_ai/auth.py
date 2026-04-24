"""
Tian AI M1 — User Authentication / Account System
═══════════════════════════════════════════════

Simple local user account system:
  - Register with username + password
  - Login with username + password
  - Password hashing via hashlib.sha256 + salt
  - Session token generation
  - Account info: username, tier, preferences, login history

Data persisted to auth_store.json
"""

import time
import json
import os
import hmac
import hashlib
import base64
import secrets
from datetime import datetime
from typing import Optional, Dict, Any, List
from .multilingual import TranslationProvider

TOKEN_EXPIRY_HOURS = 24


def _hash_password(password: str, salt: Optional[str] = None) -> tuple:
    """
    Hash a password with a salt.
    Returns (hash, salt) where both are base64-encoded strings.
    """
    if salt is None:
        salt = base64.b64encode(secrets.token_bytes(16)).decode('utf-8')
    pwd_salt = password + salt
    h = hashlib.sha256(pwd_salt.encode('utf-8')).hexdigest()
    return h, salt


def _generate_token() -> str:
    """Generate a random session token."""
    return secrets.token_hex(32)


class AuthSystem:
    """
    Simple local authentication system.

    Each user has:
      - username (unique)
      - password_hash + salt
      - account tier: 'free' (always) — tier gates handled by TierManager
      - created_at / last_login
      - login_history: list of timestamps
      - session_token (active session, if logged in)
      - session_expires: timestamp

    Data stored in auth_store.json:
      {users: {username: {...}}, last_token_cleanup: timestamp}
    """

    def __init__(self, store_path: str = 'auth_store.json',
                 tr: Optional[TranslationProvider] = None):
        self.tr = tr or TranslationProvider(lang="en")
        self.store_path = store_path
        self._users: Dict[str, dict] = {}
        self._active_token: Optional[str] = None
        self._active_username: Optional[str] = None
        self._active_expires: float = 0
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
            self._users = data.get('users', {})
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save(self):
        path = self._get_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump({
                'users': self._users,
                'last_save': time.time(),
            }, f, indent=2)

    # ── Account management ──

    def register(self, username: str, password: str) -> dict:
        """
        Register a new user account.
        Returns {'success': True/False, 'message': str}
        """
        username = username.strip().lower()

        if not username or len(username) < 3:
            return {'success': False, 'message': self.tr.t('用户名至少3个字符')}
        if len(password) < 6:
            return {'success': False, 'message': self.tr.t('密码至少6个字符')}
        if username in self._users:
            return {'success': False, 'message': self.tr.t('用户名已存在')}

        pw_hash, salt = _hash_password(password)
        self._users[username] = {
            'password_hash': pw_hash,
            'salt': salt,
            'created_at': time.time(),
            'last_login': 0,
            'login_count': 0,
            'login_history': [],
            'preferences': {},
        }
        self.save()
        return {'success': True, 'message': self.tr.t('注册成功')}

    def login(self, username: str, password: str) -> dict:
        """
        Login with username and password.
        Returns {'success': True/False, 'message': str, 'token': str/None}
        """
        username = username.strip().lower()
        user = self._users.get(username)
        if not user:
            return {'success': False, 'message': self.tr.t('用户名或密码错误')}

        pw_hash, _ = _hash_password(password, user['salt'])
        if pw_hash != user['password_hash']:
            return {'success': False, 'message': self.tr.t('用户名或密码错误')}

        # Generate session
        token = _generate_token()
        self._active_token = token
        self._active_username = username
        self._active_expires = time.time() + TOKEN_EXPIRY_HOURS * 3600

        # Update user stats
        now = time.time()
        user['last_login'] = now
        user['login_count'] = user.get('login_count', 0) + 1
        history = user.get('login_history', [])
        history.append(now)
        if len(history) > 50:
            history = history[-50:]
        user['login_history'] = history
        self.save()

        return {
            'success': True,
            'message': self.tr.t('登录成功'),
            'token': token,
            'username': username,
        }

    def logout(self):
        """Clear active session."""
        self._active_token = None
        self._active_username = None
        self._active_expires = 0

    def is_logged_in(self) -> bool:
        """Check if there's a valid active session."""
        if not self._active_token or not self._active_username:
            return False
        if time.time() > self._active_expires:
            self.logout()
            return False
        return True

    def get_current_user(self) -> Optional[str]:
        """Get current logged-in username, or None."""
        if self.is_logged_in():
            return self._active_username
        return None

    def get_user_info(self, username: str) -> Optional[dict]:
        """Get public user info (no password hash)."""
        user = self._users.get(username.strip().lower())
        if not user:
            return None
        return {
            'username': username,
            'created_at': user.get('created_at', 0),
            'last_login': user.get('last_login', 0),
            'login_count': user.get('login_count', 0),
            'preferences': user.get('preferences', {}),
        }

    def list_users(self) -> list:
        """List all registered usernames (admin use only)."""
        return list(self._users.keys())

    def delete_account(self, username: str, password: str) -> dict:
        """Delete account (requires password confirmation)."""
        username = username.strip().lower()
        user = self._users.get(username)
        if not user:
            return {'success': False, 'message': self.tr.t('用户不存在')}

        pw_hash, _ = _hash_password(password, user['salt'])
        if pw_hash != user['password_hash']:
            return {'success': False, 'message': self.tr.t('密码错误')}

        del self._users[username]
        if self._active_username == username:
            self.logout()
        self.save()
        return {'success': True, 'message': self.tr.t('账号已删除')}

    # ── Preferences ──

    def set_preference(self, key: str, value: Any) -> dict:
        """Set a user preference for the active user."""
        user = self._get_active_user()
        if not user:
            return {'success': False, 'message': self.tr.t('请先登录')}
        prefs = user.get('preferences', {})
        prefs[key] = value
        user['preferences'] = prefs
        self.save()
        return {'success': True, 'message': f"{key} = {value}"}

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference for the active user."""
        user = self._get_active_user()
        if not user:
            return default
        return user.get('preferences', {}).get(key, default)

    def get_all_preferences(self) -> dict:
        """Get all preferences for the active user."""
        user = self._get_active_user()
        if not user:
            return {}
        return user.get('preferences', {})

    def _get_active_user(self) -> Optional[dict]:
        if not self.is_logged_in():
            return None
        return self._users.get(self._active_username)

    # ── Status ──

    def get_status(self) -> dict:
        return {
            'logged_in': self.is_logged_in(),
            'username': self.get_current_user(),
            'users_count': len(self._users),
        }

    def format_status(self) -> str:
        status = self.get_status()
        lines = [
            f"━━ {self.tr.t('账号')} ━━",
            f"  {self.tr.t('登录状态')}: {'✓ ' + status['username'] if status['logged_in'] else '✗ ' + self.tr.t('未登录')}",
            f"  {self.tr.t('注册用户')}: {status['users_count']}",
        ]
        if status['logged_in']:
            info = self.get_user_info(status['username'])
            if info:
                lines.append(f"  {self.tr.t('登录次数')}: {info['login_count']}")
        return '\n'.join(lines)
