from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import pickle
from threading import RLock
from typing import Any
from uuid import uuid4

from sinauth.models import DEFAULT_SCOPE, UserRecord, utcnow
from sinauth.security import hash_password


class PickleStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()
        self._users: dict[str, UserRecord] = {}
        self._banned_ips: set[str] = set()
        self._load()

    def ensure_admin(self, username: str, password: str) -> None:
        with self._lock:
            if username in self._users:
                return
            self._users[username] = UserRecord(
                username=username,
                password_hash=hash_password(password),
                permissions=["*"],
                collections={DEFAULT_SCOPE: {"role": "admin"}},
            )
            self._save_locked()

    def list_users(self) -> list[UserRecord]:
        with self._lock:
            return deepcopy(list(self._users.values()))

    def get_user(self, username: str) -> UserRecord | None:
        with self._lock:
            user = self._users.get(username)
            return deepcopy(user) if user else None

    def user_exists(self, identifier: str) -> bool:
        with self._lock:
            if identifier in self._users:
                return True
            return any(user.id == identifier for user in self._users.values())

    def is_ip_banned(self, ip_address: str) -> bool:
        with self._lock:
            return ip_address in self._banned_ips

    def ban_ip(self, ip_address: str) -> None:
        with self._lock:
            if ip_address in self._banned_ips:
                return
            self._banned_ips.add(ip_address)
            self._save_locked()

    def create_user(
        self,
        *,
        username: str,
        password: str,
        permissions: list[str],
        collections: dict[str, dict[str, Any]],
        disabled: bool,
    ) -> UserRecord:
        with self._lock:
            if username in self._users:
                raise ValueError("user already exists")
            user = UserRecord(
                username=username,
                password_hash=hash_password(password),
                permissions=permissions,
                collections=collections,
                disabled=disabled,
            )
            self._users[username] = user
            self._save_locked()
            return deepcopy(user)

    def update_user(
        self,
        username: str,
        *,
        password: str | None = None,
        permissions: list[str] | None = None,
        collections: dict[str, dict[str, Any]] | None = None,
        disabled: bool | None = None,
    ) -> UserRecord:
        with self._lock:
            user = self._users.get(username)
            if user is None:
                raise KeyError("user not found")
            if password is not None:
                user.password_hash = hash_password(password)
            if permissions is not None:
                user.permissions = permissions
            if collections is not None:
                user.collections = collections
            if disabled is not None:
                user.disabled = disabled
            user.updated_at = utcnow()
            self._save_locked()
            return deepcopy(user)

    def delete_user(self, username: str) -> None:
        with self._lock:
            if username not in self._users:
                raise KeyError("user not found")
            del self._users[username]
            self._save_locked()

    def put_collection(self, username: str, service: str, data: dict[str, Any]) -> UserRecord:
        with self._lock:
            user = self._users.get(username)
            if user is None:
                raise KeyError("user not found")
            user.collections[service] = data
            user.updated_at = utcnow()
            self._save_locked()
            return deepcopy(user)

    def _load(self) -> None:
        with self._lock:
            if not self.path.exists():
                self._users = {}
                return
            with self.path.open("rb") as file:
                data = pickle.load(file)
            if isinstance(data, dict) and "users" in data:
                users = data["users"]
                banned_ips = data.get("banned_ips", [])
            else:
                users = data
                banned_ips = []
            if not isinstance(users, dict):
                raise RuntimeError(f"invalid store format in {self.path}")
            self._users = users
            self._banned_ips = set(banned_ips) if isinstance(banned_ips, (list, set, tuple)) else set()
            if self._ensure_user_ids_locked():
                self._save_locked()

    def _ensure_user_ids_locked(self) -> bool:
        changed = False
        for user in self._users.values():
            if not getattr(user, "id", None):
                user.id = str(uuid4())
                changed = True
        return changed

    def _save_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp_path.open("wb") as file:
            pickle.dump({"users": self._users, "banned_ips": sorted(self._banned_ips)}, file)
        os.replace(tmp_path, self.path)
