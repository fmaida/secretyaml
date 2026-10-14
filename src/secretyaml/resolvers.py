import os
import stat
from pathlib import Path, PurePosixPath
from typing import Protocol, runtime_checkable

from secretyaml.errors import InsecurePermissionsError, InvalidSecretKeyError, SecretNotFoundError

ENV_DIR = "SECRETYAML_DIR"
DIR_MODE = 0o700
FILE_MODE = 0o600


@runtime_checkable
class SecretResolver(Protocol):
    """Sorgente di segreti: data una chiave come "servizio/password" restituisce il valore."""

    def resolve(self, key: str) -> str: ...


def default_base_dir(base_dir: str | Path | None = None) -> Path:
    """Cartella dei segreti: argomento esplicito, poi $SECRETYAML_DIR, poi ~/.secrets."""
    if base_dir is not None:
        return Path(base_dir).expanduser()
    if env := os.environ.get(ENV_DIR):
        return Path(env).expanduser()
    return Path.home() / ".secrets"


def permission_problem(path: Path) -> str | None:
    """Descrive cosa non va nei permessi di `path`, o None se sono corretti (solo POSIX)."""
    if os.name != "posix":
        return None
    st = path.stat()
    if st.st_uid != os.getuid():
        return f"{path}: il proprietario non è l'utente corrente (uid {st.st_uid})"
    if st.st_mode & 0o077:
        expected = DIR_MODE if stat.S_ISDIR(st.st_mode) else FILE_MODE
        return (
            f"{path}: permessi {stat.S_IMODE(st.st_mode):o} troppo aperti, "
            f"usa: chmod {expected:o} {path}"
        )
    return None


def validate_key(key: str) -> PurePosixPath:
    rel = PurePosixPath(key)
    if not key.strip() or not rel.parts:
        raise InvalidSecretKeyError("chiave del segreto vuota")
    if rel.is_absolute() or "\\" in key or ":" in rel.parts[0]:
        raise InvalidSecretKeyError(f"la chiave {key!r} non può essere un percorso assoluto")
    if rel.parts[0].startswith("~"):
        raise InvalidSecretKeyError(f"la chiave {key!r} non può iniziare con '~'")
    if ".." in rel.parts:
        raise InvalidSecretKeyError(f"la chiave {key!r} non può contenere '..'")
    return rel


class FileResolver:
    """Legge ogni segreto da un file in chiaro: la chiave "a/b" corrisponde a <base_dir>/a/b."""

    def __init__(self, base_dir: str | Path | None = None, *, check_permissions: bool = True):
        self.base_dir = default_base_dir(base_dir)
        self.check_permissions = check_permissions

    def resolve(self, key: str) -> str:
        rel = validate_key(key)
        path = self.base_dir / rel
        if not path.is_file():
            raise SecretNotFoundError(f"segreto {key!r} non trovato in {path}")
        if not path.resolve().is_relative_to(self.base_dir.resolve()):
            raise InvalidSecretKeyError(f"il segreto {key!r} punta fuori da {self.base_dir}")
        if self.check_permissions:
            self._check(rel)
        return path.read_text(encoding="utf-8").rstrip("\r\n")

    def _check(self, rel: PurePosixPath) -> None:
        current = self.base_dir
        to_check = [current]
        for part in rel.parts:
            current = current / part
            to_check.append(current)
        for p in to_check:
            if problem := permission_problem(p):
                raise InsecurePermissionsError(problem)
