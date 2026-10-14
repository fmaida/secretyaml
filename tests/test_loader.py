import io

import pytest
import yaml

import secretyaml
from secretyaml import FileResolver, SecretNotFoundError, SecretYamlError


class DictResolver:
    def __init__(self, data):
        self.data = data

    def resolve(self, key):
        try:
            return self.data[key]
        except KeyError:
            raise SecretNotFoundError(key) from None


def test_example_from_readme(secrets_dir, make_secret):
    make_secret("mioservizio/password", "s3greta\n")
    doc = """
login:
    user: francesco@test.com
    password: !secret "mioservizio/password"
"""
    assert secretyaml.loads(doc, resolver=FileResolver(secrets_dir)) == {
        "login": {"user": "francesco@test.com", "password": "s3greta"}
    }


def test_multiple_secrets_in_lists_and_maps():
    doc = """
a: !secret uno
b:
  - !secret due
  - normale
  - {c: !secret uno}
"""
    r = DictResolver({"uno": "1", "due": "2"})
    assert secretyaml.loads(doc, resolver=r) == {"a": "1", "b": ["2", "normale", {"c": "1"}]}


def test_load_from_path_and_stream(tmp_path):
    f = tmp_path / "config.yaml"
    f.write_text("k: !secret x\n", encoding="utf-8")
    r = DictResolver({"x": "v"})
    assert secretyaml.load(f, resolver=r) == {"k": "v"}
    assert secretyaml.load(str(f), resolver=r) == {"k": "v"}
    assert secretyaml.load(io.StringIO("k: !secret x"), resolver=r) == {"k": "v"}


def test_missing_secret_propagates():
    with pytest.raises(SecretNotFoundError):
        secretyaml.loads("k: !secret manca", resolver=DictResolver({}))


@pytest.mark.parametrize("doc", ["k: !secret {a: 1}", "k: !secret [a, b]"])
def test_secret_must_be_scalar(doc):
    with pytest.raises(SecretYamlError, match="riga 1"):
        secretyaml.loads(doc, resolver=DictResolver({}))


def test_unsafe_tags_still_rejected():
    with pytest.raises(yaml.constructor.ConstructorError):
        secretyaml.loads("k: !!python/object/apply:os.system ['echo x']", resolver=DictResolver({}))


def test_global_safe_loader_untouched():
    secretyaml.loads("k: !secret x", resolver=DictResolver({"x": "v"}))
    with pytest.raises(yaml.constructor.ConstructorError):
        yaml.safe_load("k: !secret x")


def test_resolver_protocol():
    assert isinstance(DictResolver({}), secretyaml.SecretResolver)
    assert isinstance(FileResolver("/tmp"), secretyaml.SecretResolver)
