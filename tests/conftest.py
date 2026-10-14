import pytest


@pytest.fixture
def secrets_dir(tmp_path):
    base = tmp_path / "secrets"
    base.mkdir(mode=0o700)
    base.chmod(0o700)
    return base


@pytest.fixture
def make_secret(secrets_dir):
    def _make(key: str, value: str, mode: int = 0o600):
        path = secrets_dir / key
        for parent in reversed(path.relative_to(secrets_dir).parents[:-1]):
            d = secrets_dir / parent
            d.mkdir(mode=0o700, exist_ok=True)
            d.chmod(0o700)
        path.write_text(value, encoding="utf-8")
        path.chmod(mode)
        return path

    return _make
