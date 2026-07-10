from sinauth.main import is_secret_probe_path


def test_secret_probe_path_detection() -> None:
    assert is_secret_probe_path("/.env")
    assert is_secret_probe_path("/.env.local")
    assert is_secret_probe_path("/.git/config")
    assert is_secret_probe_path("/backup.sql")
    assert is_secret_probe_path("/api/%2eenv")
    assert is_secret_probe_path("/wp-config.php")


def test_normal_api_paths_are_not_secret_probes() -> None:
    assert not is_secret_probe_path("/health")
    assert not is_secret_probe_path("/authorize/api/login")
    assert not is_secret_probe_path("/authorize/web/assets/app.js")
