import io
import stat

import pytest

from secretyaml import FileResolver
from secretyaml.cli import main


def mode(p):
    return stat.S_IMODE(p.stat().st_mode)


def run(monkeypatch, argv, stdin=""):
    """Esegue la CLI con stdin non interattivo (pipe)."""
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    monkeypatch.setattr("secretyaml.cli._interactive", lambda: False)
    return main(argv)


@pytest.fixture
def tty(monkeypatch):
    """Simula un terminale: risposte di getpass e input prese da liste."""
    passwords, answers = [], []
    monkeypatch.setattr("secretyaml.cli._interactive", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda prompt="", **kw: passwords.pop(0))
    monkeypatch.setattr("builtins.input", lambda prompt="": answers.pop(0))
    return passwords, answers


# --- add ---------------------------------------------------------------------

def test_add_interactive(tmp_path, tty, capsys):
    passwords, _ = tty
    passwords += ["pw", "pw"]
    base = tmp_path / "s"
    assert main(["--dir", str(base), "add", "servizio/token"]) == 0
    assert "Secret added as servizio/token" in capsys.readouterr().out
    assert FileResolver(base).resolve("servizio/token") == "pw"


def test_add_passwords_do_not_match(tmp_path, tty, capsys):
    passwords, _ = tty
    passwords += ["pw", "altro"]
    base = tmp_path / "s"
    assert main(["--dir", str(base), "add", "servizio/token"]) == 1
    assert "do not match" in capsys.readouterr().err
    assert not (base / "servizio/token").exists()


def test_add_existing_asks_before_overwrite(tmp_path, monkeypatch, tty):
    passwords, answers = tty
    base = tmp_path / "s"
    run(monkeypatch, ["--dir", str(base), "add", "k"], "vecchio")
    monkeypatch.setattr("secretyaml.cli._interactive", lambda: True)

    answers.append("n")
    assert main(["--dir", str(base), "add", "k"]) == 1
    assert FileResolver(base).resolve("k") == "vecchio"

    answers.append("y")
    passwords += ["nuovo", "nuovo"]
    assert main(["--dir", str(base), "add", "k"]) == 0
    assert FileResolver(base).resolve("k") == "nuovo"


def test_add_existing_prompt_text(tmp_path, monkeypatch, tty):
    passwords, answers = tty
    base = tmp_path / "s"
    run(monkeypatch, ["--dir", str(base), "add", "servizio/token"], "vecchio")
    monkeypatch.setattr("secretyaml.cli._interactive", lambda: True)
    prompts = []
    monkeypatch.setattr("builtins.input", lambda prompt="": prompts.append(prompt) or "n")
    main(["--dir", str(base), "add", "servizio/token"])
    assert prompts == ["servizio/token already exists. Overwrite (y/N): "]


@pytest.mark.parametrize("answer", ["", "n", "N", "yes", "Yes", " y", "y ", "si"])
def test_add_overwrite_requires_exactly_y(tmp_path, monkeypatch, tty, answer):
    passwords, answers = tty
    base = tmp_path / "s"
    run(monkeypatch, ["--dir", str(base), "add", "k"], "vecchio")
    monkeypatch.setattr("secretyaml.cli._interactive", lambda: True)
    answers.append(answer)
    assert main(["--dir", str(base), "add", "k"]) == 1
    assert FileResolver(base).resolve("k") == "vecchio"


@pytest.mark.parametrize("answer", ["y", "Y"])
def test_add_overwrite_accepts_y(tmp_path, monkeypatch, tty, answer):
    passwords, answers = tty
    base = tmp_path / "s"
    run(monkeypatch, ["--dir", str(base), "add", "k"], "vecchio")
    monkeypatch.setattr("secretyaml.cli._interactive", lambda: True)
    answers.append(answer)
    passwords += ["nuovo", "nuovo"]
    assert main(["--dir", str(base), "add", "k"]) == 0
    assert FileResolver(base).resolve("k") == "nuovo"


def test_add_into_existing_folder(tmp_path, monkeypatch):
    base = tmp_path / "s"
    run(monkeypatch, ["--dir", str(base), "add", "servizio/password"], "pw1")
    assert run(monkeypatch, ["--dir", str(base), "add", "servizio/token"], "tok") == 0
    assert FileResolver(base).resolve("servizio/password") == "pw1"
    assert FileResolver(base).resolve("servizio/token") == "tok"


def test_add_from_stdin_creates_strict_permissions(tmp_path, monkeypatch):
    base = tmp_path / "s"
    assert run(monkeypatch, ["--dir", str(base), "add", "svc/sub/password"], "pw\n") == 0
    assert mode(base) == 0o700
    assert mode(base / "svc") == 0o700
    assert mode(base / "svc/sub") == 0o700
    assert mode(base / "svc/sub/password") == 0o600
    assert FileResolver(base).resolve("svc/sub/password") == "pw"
    assert not list((base / "svc/sub").glob(".secretyaml-*"))


def test_add_from_stdin_existing_needs_force(tmp_path, monkeypatch):
    base = tmp_path / "s"
    run(monkeypatch, ["--dir", str(base), "add", "k"], "vecchio")
    assert run(monkeypatch, ["--dir", str(base), "add", "k"], "nuovo") == 1
    assert FileResolver(base).resolve("k") == "vecchio"
    assert run(monkeypatch, ["--dir", str(base), "add", "--force", "k"], "nuovo") == 0
    assert FileResolver(base).resolve("k") == "nuovo"


def test_add_rejects_invalid_key_and_empty_value(tmp_path, monkeypatch):
    base = tmp_path / "s"
    for key in ("../x", "/chiave", "~/chiave"):
        assert run(monkeypatch, ["--dir", str(base), "add", key], "pw") == 1
    assert run(monkeypatch, ["--dir", str(base), "add", "k"], "") == 1


# --- remove ------------------------------------------------------------------

@pytest.mark.parametrize("answer", ["y", "Y"])
def test_remove_confirmed(tmp_path, monkeypatch, tty, capsys, answer):
    _, answers = tty
    base = tmp_path / "s"
    run(monkeypatch, ["--dir", str(base), "add", "servizio/token"], "pw")
    run(monkeypatch, ["--dir", str(base), "add", "altro"], "pw")
    monkeypatch.setattr("secretyaml.cli._interactive", lambda: True)
    answers.append(answer)
    assert main(["--dir", str(base), "remove", "servizio/token"]) == 0
    assert "servizio/token has been removed" in capsys.readouterr().out
    assert not (base / "servizio").exists()  # cartella rimasta vuota eliminata
    assert base.is_dir() and (base / "altro").is_file()


@pytest.mark.parametrize("answer", ["", "n", "no", "yes", " y"])
def test_remove_default_is_no(tmp_path, monkeypatch, tty, answer):
    _, answers = tty
    base = tmp_path / "s"
    run(monkeypatch, ["--dir", str(base), "add", "k"], "pw")
    monkeypatch.setattr("secretyaml.cli._interactive", lambda: True)
    answers.append(answer)
    assert main(["--dir", str(base), "remove", "k"]) == 1
    assert (base / "k").is_file()


def test_remove_last_secret_keeps_base(tmp_path, monkeypatch):
    base = tmp_path / "s"
    run(monkeypatch, ["--dir", str(base), "add", "k"], "pw")
    assert run(monkeypatch, ["--dir", str(base), "remove", "--yes", "k"]) == 0
    assert base.is_dir()


def test_remove_non_interactive_needs_yes(tmp_path, monkeypatch):
    base = tmp_path / "s"
    run(monkeypatch, ["--dir", str(base), "add", "k"], "pw")
    assert run(monkeypatch, ["--dir", str(base), "remove", "k"]) == 1
    assert (base / "k").is_file()


def test_remove_missing_and_invalid(tmp_path, monkeypatch, capsys):
    base = tmp_path / "s"
    assert run(monkeypatch, ["--dir", str(base), "remove", "-y", "manca"]) == 1
    assert "manca not found" in capsys.readouterr().err
    assert run(monkeypatch, ["--dir", str(base), "remove", "-y", "../x"]) == 1


# --- list / check ------------------------------------------------------------

def test_list_never_prints_values(tmp_path, monkeypatch, capsys):
    base = tmp_path / "s"
    run(monkeypatch, ["--dir", str(base), "add", "a/b"], "valore-segreto")
    run(monkeypatch, ["--dir", str(base), "add", "c"], "altro-valore")
    capsys.readouterr()
    assert main(["--dir", str(base), "list"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines() == ["a/b", "c"]
    assert "valore-segreto" not in out


def test_check_and_fix(tmp_path, monkeypatch, capsys):
    base = tmp_path / "s"
    run(monkeypatch, ["--dir", str(base), "add", "a/b"], "pw")
    (base / "a").chmod(0o755)
    (base / "a/b").chmod(0o644)
    assert main(["--dir", str(base), "check"]) == 1
    assert "chmod 600" in capsys.readouterr().err
    assert main(["--dir", str(base), "check", "--fix"]) == 0
    assert mode(base / "a") == 0o700
    assert mode(base / "a/b") == 0o600


def test_env_dir(tmp_path, monkeypatch):
    base = tmp_path / "s"
    monkeypatch.setenv("SECRETYAML_DIR", str(base))
    assert run(monkeypatch, ["add", "k"], "pw") == 0
    assert (base / "k").is_file()


# --- nessuna modifica fuori dalla cartella dei segreti --------------------------

@pytest.fixture
def external(tmp_path):
    """Cartella esterna con un file, raggiungibile via symlink da dentro la base."""
    base = tmp_path / "s"
    base.mkdir(mode=0o700)
    base.chmod(0o700)
    ext = tmp_path / "esterna"
    ext.mkdir()
    ext.chmod(0o755)
    (ext / "importante.txt").write_text("non toccare")
    (ext / "importante.txt").chmod(0o644)
    (base / "link-dir").symlink_to(ext)
    (base / "link-file").symlink_to(ext / "importante.txt")
    return base, ext


def test_add_refuses_symlinked_dir_outside(monkeypatch, external):
    base, ext = external
    assert run(monkeypatch, ["--dir", str(base), "add", "link-dir/nuovo"], "pw") == 1
    assert sorted(p.name for p in ext.iterdir()) == ["importante.txt"]


def test_add_refuses_symlinked_file_outside(monkeypatch, external):
    base, ext = external
    assert run(monkeypatch, ["--dir", str(base), "add", "--force", "link-file"], "pw") == 1
    assert (ext / "importante.txt").read_text() == "non toccare"


def test_remove_refuses_outside(monkeypatch, external):
    base, ext = external
    assert run(monkeypatch, ["--dir", str(base), "remove", "-y", "link-dir/importante.txt"]) == 1
    assert run(monkeypatch, ["--dir", str(base), "remove", "-y", "link-file"]) == 1
    assert (ext / "importante.txt").exists()
    assert (base / "link-file").is_symlink()


def test_check_fix_never_touches_outside(external, capsys):
    base, ext = external
    assert main(["--dir", str(base), "check", "--fix"]) == 1
    assert "symlink pointing outside" in capsys.readouterr().err
    assert mode(ext) == 0o755
    assert mode(ext / "importante.txt") == 0o644
