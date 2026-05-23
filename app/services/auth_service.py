"""SQLite 用户认证服务。"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict

from flask import current_app

from app.extensions import AUTH_LOCK
from src.config import Config


def _users_db_path() -> Path:
    cfg = Config.load()
    base_dir: Path = current_app.config["BASE_DIR"]
    data_dir = base_dir / cfg.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "users.db"


def _ensure_user_table() -> None:
    db_path = _users_db_path()
    with AUTH_LOCK:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()


def normalize_username(username: str) -> str:
    return re.sub(r"\s+", "", str(username or "").strip().lower())


def hash_password(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", str(password or "").encode("utf-8"), salt, 120_000)
    return digest.hex()


def create_user(username: str, password: str) -> tuple[bool, str]:
    name = normalize_username(username)
    if not re.fullmatch(r"[a-z0-9_]{3,32}", name):
        return False, "用户名仅支持 3-32 位字母、数字、下划线。"
    if len(str(password or "")) < 6:
        return False, "密码长度至少 6 位。"

    _ensure_user_table()
    db_path = _users_db_path()

    with AUTH_LOCK:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute("SELECT id FROM users WHERE username = ?", (name,))
            if cur.fetchone():
                return False, "账号已存在，请更换用户名。"

            salt_hex = secrets.token_hex(16)
            password_hash = hash_password(password, salt_hex)
            conn.execute(
                "INSERT INTO users(username, password_salt, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (name, salt_hex, password_hash, int(time.time())),
            )
            conn.commit()
            return True, "注册成功"
        finally:
            conn.close()


def verify_user(username: str, password: str) -> Dict[str, Any] | None:
    name = normalize_username(username)
    _ensure_user_table()
    db_path = _users_db_path()

    with AUTH_LOCK:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute(
                "SELECT id, username, password_salt, password_hash FROM users WHERE username = ?",
                (name,),
            )
            row = cur.fetchone()
        finally:
            conn.close()

    if not row:
        return None

    user_id, uname, salt_hex, expected_hash = row
    actual_hash = hash_password(password, salt_hex)
    if not hmac.compare_digest(actual_hash, expected_hash):
        return None
    return {"id": int(user_id), "username": str(uname)}


def user_dir_token(user: Dict[str, Any]) -> str:
    seed = f"uid:{int(user.get('id') or 0)}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def get_user_output_dir(user: Dict[str, Any] | None = None) -> Path:
    from app.utils.login_required import current_user

    cfg = Config.load()
    base_dir: Path = current_app.config["BASE_DIR"]
    root = base_dir / cfg.output_dir / "users"
    root.mkdir(parents=True, exist_ok=True)
    u = user or current_user()
    if not u:
        return root / "_guest"
    token = user_dir_token(u)
    user_dir = root / token
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir
