from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sinauth.models import DEFAULT_SCOPE, UserRecord


def has_permission(user: UserRecord, action: str, scope: str = DEFAULT_SCOPE) -> bool:
    permissions = set(user.permissions)
    return any(
        candidate in permissions
        for candidate in (
            "*",
            f"{action}:*",
            f"{action}:{scope}",
            action,
        )
    )


def _allowed_services(token_service: str | Iterable[str]) -> set[str] | None:
    services = {token_service} if isinstance(token_service, str) else set(token_service)
    # A default-scoped token has the historical unrestricted behaviour.
    if DEFAULT_SCOPE in services:
        return None
    return {DEFAULT_SCOPE, *services}


def require_service_visible(token_service: str | Iterable[str], target_service: str) -> None:
    allowed = _allowed_services(token_service)
    if allowed is not None and target_service not in allowed:
        raise PermissionError("token can access only default and its requested service collections")


def require_collections_visible(
    token_service: str | Iterable[str], collection_names: set[str]
) -> None:
    allowed = _allowed_services(token_service)
    if allowed is None:
        return
    forbidden = sorted(collection_names - allowed)
    if forbidden:
        raise PermissionError(
            "token can access only default and its requested service collections: "
            + ", ".join(forbidden)
        )


def visible_collections(
    collections: dict[str, dict[str, Any]],
    *,
    token_service: str | Iterable[str],
) -> dict[str, dict[str, Any]]:
    allowed = _allowed_services(token_service)
    if allowed is None:
        return dict(collections)
    return {key: value for key, value in collections.items() if key in allowed}
