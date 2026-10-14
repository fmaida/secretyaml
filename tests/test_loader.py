import pytest
import yaml

import secretyaml
from secretyaml import FileResolver, Secret, SecretNotFoundError, SecretYamlDict, SecretYamlError
from tests.conftest import DictResolver


def test_example_from_readme(secrets_dir, make_secret, write_yaml):
    make_secret("mioservizio/password", "s3greta\n")
    path = write_yaml("""
login:
    user: francesco@test.com
    password: !secret "mioservizio/password"
""")
    assert secretyaml.load(path, resolver=FileResolver(secrets_dir)) == {
        "login": {"user": "francesco@test.com", "password": "s3greta"}
    }


def test_multiple_secrets_in_lists_and_maps(write_yaml):
    path = write_yaml("""
a: !secret uno
b:
  - !secret due
  - normale
  - {c: !secret uno}
""")
    data = secretyaml.load(path, resolver=DictResolver({"uno": "1", "due": "2"}))
    assert data == {"a": "1", "b": ["2", "normale", {"c": "1"}]}
    assert data.secret_fields == {("a",): "uno", ("b", 0): "due", ("b", 2, "c"): "uno"}


def test_load_returns_secretyamldict(write_yaml):
    path = write_yaml("k: !secret x\nn: 1\n")
    for p in (path, str(path)):
        data = secretyaml.load(p, resolver=DictResolver({"x": "v"}))
        assert isinstance(data, dict) and isinstance(data, SecretYamlDict)
        assert data == {"k": "v", "n": 1}
        assert data.source_path == path
        assert isinstance(data["k"], Secret) and data["k"].key == "x"
        assert type(data["n"]) is int


def test_load_relative_path_is_stored_absolute(write_yaml, monkeypatch):
    path = write_yaml("k: 1\n")
    monkeypatch.chdir(path.parent)
    assert secretyaml.load("config.yaml", resolver=DictResolver({})).source_path == path


def test_load_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        secretyaml.load(tmp_path / "manca.yaml", resolver=DictResolver({}))


@pytest.mark.parametrize("doc", ["", "# solo un commento\n"])
def test_empty_document_is_empty_dict(write_yaml, doc):
    data = secretyaml.load(write_yaml(doc), resolver=DictResolver({}))
    assert data == {} and isinstance(data, SecretYamlDict)


@pytest.mark.parametrize("doc", ["- a\n- b\n", "solo una stringa", "!secret x"])
def test_document_must_be_a_dict(write_yaml, doc):
    with pytest.raises(SecretYamlError, match="dizionario"):
        secretyaml.load(write_yaml(doc), resolver=DictResolver({"x": "v"}))


def test_missing_secret_propagates(write_yaml):
    with pytest.raises(SecretNotFoundError):
        secretyaml.load(write_yaml("k: !secret manca"), resolver=DictResolver({}))


@pytest.mark.parametrize("doc", ["k: !secret {a: 1}", "k: !secret [a, b]"])
def test_secret_must_be_scalar(write_yaml, doc):
    with pytest.raises(SecretYamlError, match="riga 1"):
        secretyaml.load(write_yaml(doc), resolver=DictResolver({}))


def test_unsafe_tags_still_rejected(write_yaml):
    with pytest.raises(yaml.constructor.ConstructorError):
        secretyaml.load(write_yaml("k: !!python/object/apply:os.system ['echo x']"), resolver=DictResolver({}))


def test_global_safe_loader_untouched(write_yaml):
    secretyaml.load(write_yaml("k: !secret x"), resolver=DictResolver({"x": "v"}))
    with pytest.raises(yaml.constructor.ConstructorError):
        yaml.safe_load("k: !secret x")


def test_resolver_protocol():
    assert isinstance(DictResolver({}), secretyaml.SecretResolver)
    assert isinstance(FileResolver("/tmp"), secretyaml.SecretResolver)
