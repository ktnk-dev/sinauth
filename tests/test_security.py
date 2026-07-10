from sinauth.security import (
    create_signed_payload,
    create_token,
    decode_signed_payload,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    encoded = hash_password("secret")

    assert verify_password("secret", encoded)
    assert not verify_password("wrong", encoded)


def test_token_roundtrip() -> None:
    token, expires_at = create_token(
        username="alice",
        service="billing",
        secret="test-secret",
        ttl_seconds=60,
    )

    payload = decode_token(token, "test-secret")

    assert payload["sub"] == "alice"
    assert payload["service"] == "billing"
    assert payload["exp"] == expires_at


def test_signed_payload_roundtrip() -> None:
    token, expires_at = create_signed_payload(
        payload={
            "typ": "web_authorize",
            "service": "billing",
            "on_success_redirect": "https://service.example/success",
        },
        secret="test-secret",
        ttl_seconds=60,
    )

    payload = decode_signed_payload(token, "test-secret")

    assert payload["typ"] == "web_authorize"
    assert payload["service"] == "billing"
    assert payload["on_success_redirect"] == "https://service.example/success"
    assert payload["exp"] == expires_at
