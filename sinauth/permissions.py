from __future__ import annotations

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


def require_service_visible(token_service: str, target_service: str) -> None:
    if token_service != DEFAULT_SCOPE and target_service not in {DEFAULT_SCOPE, token_service}:
        raise PermissionError("token service can access only default and its own collection")


def require_collections_visible(token_service: str, collection_names: set[str]) -> None:
    if token_service == DEFAULT_SCOPE:
        return
    allowed = {DEFAULT_SCOPE, token_service}
    forbidden = sorted(collection_names - allowed)
    if forbidden:
        raise PermissionError(
            "token service can access only default and its own collection: "
            + ", ".join(forbidden)
        )


def visible_collections(
    collections: dict[str, dict[str, Any]],
    *,
    token_service: str,
) -> dict[str, dict[str, Any]]:
    if token_service == DEFAULT_SCOPE:
        return dict(collections)
    allowed = {DEFAULT_SCOPE, token_service}
    return {key: value for key, value in collections.items() if key in allowed}
