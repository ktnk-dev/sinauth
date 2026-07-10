import pytest

from sinauth.models import UserRecord
from sinauth.permissions import (
    has_permission,
    require_collections_visible,
    require_service_visible,
    visible_collections,
)


def test_permission_wildcards() -> None:
    user = UserRecord(username="admin", password_hash="x", permissions=["*"])

    assert has_permission(user, "users.delete")
    assert has_permission(user, "collections.write", "billing")


def test_permission_scopes() -> None:
    user = UserRecord(
        username="manager",
        password_hash="x",
        permissions=["users.read:default", "collections.write:billing"],
    )

    assert has_permission(user, "users.read")
    assert has_permission(user, "collections.write", "billing")
    assert not has_permission(user, "collections.write", "crm")


def test_service_visibility_filter() -> None:
    collections = {
        "default": {"display_name": "Alice"},
        "billing": {"plan": "pro"},
        "crm": {"lead": True},
    }

    assert visible_collections(collections, token_service="billing") == {
        "default": {"display_name": "Alice"},
        "billing": {"plan": "pro"},
    }
    assert visible_collections(collections, token_service=["billing", "crm"]) == collections


def test_service_visibility_guard() -> None:
    require_service_visible("billing", "default")
    require_service_visible("billing", "billing")

    with pytest.raises(PermissionError):
        require_service_visible("billing", "crm")

    require_service_visible(["billing", "crm"], "crm")


def test_bulk_collection_visibility_guard() -> None:
    require_collections_visible("billing", {"default", "billing"})
    require_collections_visible("default", {"default", "billing", "crm"})

    with pytest.raises(PermissionError):
        require_collections_visible("billing", {"default", "crm"})

    require_collections_visible(["billing", "crm"], {"default", "billing", "crm"})
