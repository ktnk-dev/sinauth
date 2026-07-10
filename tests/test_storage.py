import pickle
from uuid import UUID

from sinauth.models import UserRecord
from sinauth.storage import PickleStore


def test_created_user_gets_uuid4_id(tmp_path) -> None:
    store = PickleStore(tmp_path / "store.pkl")

    user = store.create_user(
        username="alice",
        password="secret",
        permissions=[],
        collections={},
        disabled=False,
    )

    assert UUID(user.id).version == 4


def test_user_exists_checks_username_and_id(tmp_path) -> None:
    store = PickleStore(tmp_path / "store.pkl")
    user = store.create_user(
        username="alice",
        password="secret",
        permissions=[],
        collections={},
        disabled=False,
    )

    assert store.user_exists("alice")
    assert store.user_exists(user.id)
    assert not store.user_exists("missing")


def test_banned_ips_are_persisted(tmp_path) -> None:
    path = tmp_path / "store.pkl"
    store = PickleStore(path)

    store.ban_ip("203.0.113.10")

    reloaded = PickleStore(path)
    assert reloaded.is_ip_banned("203.0.113.10")
    assert not reloaded.is_ip_banned("203.0.113.11")


def test_load_migrates_user_without_id(tmp_path) -> None:
    path = tmp_path / "store.pkl"
    old_user = UserRecord(username="old", password_hash="x")
    del old_user.id
    with path.open("wb") as file:
        pickle.dump({"users": {"old": old_user}}, file)

    store = PickleStore(path)
    user = store.get_user("old")

    assert user is not None
    assert UUID(user.id).version == 4
