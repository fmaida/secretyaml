import pytest

from secretyaml import FileResolver, InsecurePermissionsError, InvalidSecretKeyError, SecretNotFoundError


def test_resolve_simple(secrets_dir, make_secret):
    make_secret("token", "abc")
    assert FileResolver(secrets_dir).resolve("token") == "abc"


def test_resolve_nested(secrets_dir, make_secret):
    make_secret("servizio/sotto/password", "pw")
    assert FileResolver(secrets_dir).resolve("servizio/sotto/password") == "pw"


@pytest.mark.parametrize("content", ["pw\n", "pw\r\n", "pw"])
def test_trailing_newline_stripped(secrets_dir, make_secret, content):
    make_secret("p", content)
    assert FileResolver(secrets_dir).resolve("p") == "pw"


def test_missing_secret(secrets_dir):
    with pytest.raises(SecretNotFoundError, match="nope"):
        FileResolver(secrets_dir).resolve("nope")


@pytest.mark.parametrize("key", [
    "", "   ", "/etc/passwd", "//etc/passwd", "../fuori", "./../fuori", "a/../../b", "..",
    "~/../.config/altro-servizio/token", "../.config/altro-servizio/token", "C:\\x", "a\\..\\b",
    "/chiave", "~/chiave", "~", "~root/chiave", "~/.ssh/id_rsa",
])
def test_invalid_keys(secrets_dir, key):
    with pytest.raises(InvalidSecretKeyError):
        FileResolver(secrets_dir).resolve(key)


def test_symlink_escaping_base(secrets_dir, tmp_path):
    outside = tmp_path / "fuori.txt"
    outside.write_text("rubato")
    outside.chmod(0o600)
    (secrets_dir / "link").symlink_to(outside)
    with pytest.raises(InvalidSecretKeyError):
        FileResolver(secrets_dir).resolve("link")


def test_symlinked_dir_escaping_base(secrets_dir, tmp_path):
    outside = tmp_path / "fuori"
    outside.mkdir(mode=0o700)
    (outside / "token").write_text("rubato")
    (outside / "token").chmod(0o600)
    (secrets_dir / "link-dir").symlink_to(outside)
    with pytest.raises(InvalidSecretKeyError):
        FileResolver(secrets_dir).resolve("link-dir/token")


def test_file_too_open(secrets_dir, make_secret):
    make_secret("p", "pw", mode=0o644)
    with pytest.raises(InsecurePermissionsError, match="chmod 600"):
        FileResolver(secrets_dir).resolve("p")


def test_dir_too_open(secrets_dir, make_secret):
    make_secret("servizio/p", "pw")
    (secrets_dir / "servizio").chmod(0o755)
    with pytest.raises(InsecurePermissionsError, match="chmod 700"):
        FileResolver(secrets_dir).resolve("servizio/p")


def test_base_too_open(secrets_dir, make_secret):
    make_secret("p", "pw")
    secrets_dir.chmod(0o755)
    with pytest.raises(InsecurePermissionsError):
        FileResolver(secrets_dir).resolve("p")


def test_permission_check_disabled(secrets_dir, make_secret):
    make_secret("p", "pw", mode=0o644)
    assert FileResolver(secrets_dir, check_permissions=False).resolve("p") == "pw"


def test_error_message_never_contains_value(secrets_dir, make_secret):
    make_secret("p", "valore-segreto", mode=0o644)
    with pytest.raises(InsecurePermissionsError) as exc:
        FileResolver(secrets_dir).resolve("p")
    assert "valore-segreto" not in str(exc.value)


def test_env_var_base_dir(secrets_dir, make_secret, monkeypatch):
    make_secret("p", "da-env")
    monkeypatch.setenv("SECRETYAML_DIR", str(secrets_dir))
    assert FileResolver().resolve("p") == "da-env"


def test_explicit_dir_wins_over_env(secrets_dir, make_secret, monkeypatch, tmp_path):
    make_secret("p", "esplicito")
    monkeypatch.setenv("SECRETYAML_DIR", str(tmp_path / "altrove"))
    assert FileResolver(secrets_dir).resolve("p") == "esplicito"


def test_default_is_home_secrets(monkeypatch, tmp_path):
    monkeypatch.delenv("SECRETYAML_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert FileResolver().base_dir == tmp_path / ".secrets"
