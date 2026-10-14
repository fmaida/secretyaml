import copy
import json
import pickle
import stat

import pytest

import secretyaml
from secretyaml import Secret, SecretYamlError
from tests.conftest import DictResolver

DOC = """\
login:
  user: francesco@test.com
  password: !secret "mioservizio/password"
servers:
- host: a.example.com
  token: !secret "a/token"
- host: b.example.com
"""
SECRETS = {"mioservizio/password": "s3greta", "a/token": "tok-123"}


@pytest.fixture
def config(write_yaml):
    path = write_yaml(DOC)
    return secretyaml.load(path, resolver=DictResolver(SECRETS))


def reload(path):
    return secretyaml.load(path, resolver=DictResolver(SECRETS))


def test_round_trip_restores_tags(config):
    secretyaml.save(config)
    text = config.source_path.read_text()
    assert 'password: !secret "mioservizio/password"' in text
    assert 'token: !secret "a/token"' in text
    assert "s3greta" not in text and "tok-123" not in text
    assert text == DOC
    assert reload(config.source_path) == config


def test_save_writes_normal_changes(config):
    config["login"]["user"] = "altro@test.com"
    config["nuovo"] = {"porta": 8080}
    secretyaml.save(config)
    text = config.source_path.read_text()
    assert "user: altro@test.com" in text
    assert "porta: 8080" in text
    assert "s3greta" not in text
    assert reload(config.source_path)["nuovo"] == {"porta": 8080}


def test_secret_replaced_by_plain_value_is_refused(config):
    before = config.source_path.read_text()
    config["login"]["password"] = "nuova-password"
    with pytest.raises(SecretYamlError, match=r"login\.password") as exc:
        secretyaml.save(config)
    assert "nuova-password" not in str(exc.value)
    assert config.source_path.read_text() == before


def test_secret_in_list_replaced_is_refused(config):
    config["servers"][0]["token"] = 12345
    with pytest.raises(SecretYamlError, match=r"servers\[0\]\.token"):
        secretyaml.save(config)


def test_removed_secret_field_is_fine(config):
    del config["login"]["password"]
    del config["servers"][0]
    secretyaml.save(config)
    text = config.source_path.read_text()
    assert "password" not in text and "a/token" not in text


def test_moved_secret_is_written_as_tag(config):
    config["backup"] = {"pw": config["login"].pop("password")}
    secretyaml.save(config)
    text = config.source_path.read_text()
    assert 'pw: !secret "mioservizio/password"' in text
    assert "s3greta" not in text


def test_same_secret_twice_has_no_yaml_aliases(config):
    config["copia"] = config["login"]["password"]
    config["login2"] = config["login"]
    secretyaml.save(config)
    text = config.source_path.read_text()
    assert "&id" not in text and "*id" not in text
    assert 'copia: !secret "mioservizio/password"' in text


def test_plain_dict_needs_path(tmp_path):
    with pytest.raises(SecretYamlError, match="percorso"):
        secretyaml.save({"a": 1})
    target = tmp_path / "nuovo.yaml"
    secretyaml.save({"a": 1, "pw": Secret("x", "svc/pw")}, target)
    assert target.read_text() == 'a: 1\npw: !secret "svc/pw"\n'


def test_save_to_explicit_path(config, tmp_path):
    other = tmp_path / "copia.yaml"
    secretyaml.save(config, other)
    assert other.read_text() == DOC


def test_file_mode_preserved_and_no_temp_files(config):
    config.source_path.chmod(0o640)
    secretyaml.save(config)
    assert stat.S_IMODE(config.source_path.stat().st_mode) == 0o640
    assert not list(config.source_path.parent.glob(".secretyaml-*"))


def test_secret_behaves_like_str():
    s = Secret("s3greta", "svc/pw")
    assert s == "s3greta" and f"{s}" == "s3greta" and s.upper() == "S3GRETA"
    assert json.dumps({"p": s}) == '{"p": "s3greta"}'
    assert repr(s) == "Secret('***', key='svc/pw')"
    for clone in (copy.deepcopy(s), pickle.loads(pickle.dumps(s))):
        assert clone == "s3greta" and clone.key == "svc/pw" and isinstance(clone, Secret)


def test_repr_of_loaded_config_hides_values(config):
    assert "s3greta" not in repr(config) and "tok-123" not in repr(config)
