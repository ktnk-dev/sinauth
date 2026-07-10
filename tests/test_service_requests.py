import pytest
from pydantic import ValidationError

from sinauth.models import ApiRegisterRequest, LoginRequest, WebAuthorizeSessionCreate


def test_login_accepts_a_service_list() -> None:
    request = LoginRequest(
        username="alice",
        password="secret",
        service=["billing", "crm"],
    )

    assert request.service == ["billing", "crm"]


def test_service_string_is_normalized_to_a_list() -> None:
    request = LoginRequest(username="alice", password="secret", service="billing")

    assert request.service == ["billing"]


def test_service_list_rejects_duplicates() -> None:
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        LoginRequest(username="alice", password="secret", service=["billing", "billing"])


def test_register_and_web_session_accept_a_service_list() -> None:
    registration = ApiRegisterRequest(
        login="alice",
        password="secret",
        display_name="Alice",
        service=["billing", "crm"],
    )
    session = WebAuthorizeSessionCreate(
        service=["billing", "crm"],
        on_success_redirect="https://example.com/success",
    )

    assert registration.service == ["billing", "crm"]
    assert session.service == ["billing", "crm"]
