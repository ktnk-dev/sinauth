from sinauth.main import record_to_out
from sinauth.models import DEFAULT_SCOPE, UserRecord


def test_user_output_includes_default_profile_fields() -> None:
    user = UserRecord(
        username="alice",
        password_hash="x",
        collections={
            DEFAULT_SCOPE: {
                "display_name": "Alice",
                "profile_picture_url": "https://example.com/alice.png",
            }
        },
    )

    output = record_to_out(user)

    assert output.display_name == "Alice"
    assert output.profile_picture_url == "https://example.com/alice.png"
