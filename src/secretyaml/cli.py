import argparse
import getpass
import os
import stat
import sys
import tempfile
from pathlib import Path

from secretyaml.errors import InvalidSecretKeyError, SecretYamlError
from secretyaml.resolvers import DIR_MODE, FILE_MODE, default_base_dir, permission_problem, validate_key


def cmd_add(base: Path, key: str, force: bool) -> int:
    path = _secret_path(base, key)
    if path.exists() and not force:
        if not _interactive():
            print(f"{key} already exists, use --force to overwrite it", file=sys.stderr)
            return 1
        if not _confirm(f"{key} already exists. Overwrite (y/N): "):
            print("Aborted")
            return 1

    if _interactive():
        value = _getpass("Please type the password: ")
        if _getpass("Please enter it again   : ") != value:
            print("Passwords do not match, nothing changed", file=sys.stderr)
            return 1
    else:
        value = sys.stdin.read().rstrip("\r\n")
    if not value:
        print("Empty password, nothing changed", file=sys.stderr)
        return 1

    current = base
    for part in (None, *path.relative_to(base).parts[:-1]):
        if part is not None:
            current = current / part
        if not current.exists():
            current.mkdir(mode=DIR_MODE)
            current.chmod(DIR_MODE)  # mkdir è soggetto a umask

    # mkstemp crea il file già con permessi 600; os.replace rende la scrittura atomica.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".secretyaml-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(value + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, FILE_MODE)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise

    print(f"Secret added as {key}")
    return _report(_iter_paths(base))


def cmd_remove(base: Path, key: str, yes: bool) -> int:
    path = _secret_path(base, key)
    if not path.is_file():
        print(f"{key} not found", file=sys.stderr)
        return 1
    if not yes:
        if not _interactive():
            print("Not a terminal: use --yes to confirm the removal", file=sys.stderr)
            return 1
        if not _confirm("are you sure (y/N): "):
            print("Aborted")
            return 1

    path.unlink()
    # Rimuove le cartelle rimaste vuote, senza mai toccare la cartella base.
    parent = path.parent
    while parent != base and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent

    print(f"{key} has been removed")
    return 0


def cmd_list(base: Path) -> int:
    if not base.is_dir():
        print(f"{base} does not exist", file=sys.stderr)
        return 1
    for p in sorted(base.rglob("*")):
        if p.is_file() and not p.name.startswith(".secretyaml-"):
            print(p.relative_to(base).as_posix())
    return 0


def cmd_check(base: Path, fix: bool) -> int:
    if not base.is_dir():
        print(f"{base} does not exist", file=sys.stderr)
        return 1
    if fix:
        for p in _iter_paths(base):
            if permission_problem(p):
                mode = DIR_MODE if p.is_dir() else FILE_MODE
                try:
                    p.chmod(stat.S_IMODE(p.stat().st_mode) & mode)
                except PermissionError:
                    pass  # proprietario diverso: verrà segnalato sotto
    problems = _report(_iter_paths(base))
    if not problems:
        print(f"{base}: permissions are correct")
    return problems


def _secret_path(base: Path, key: str) -> Path:
    path = base / validate_key(key)
    if path.exists() and not path.resolve().is_relative_to(base.resolve()):
        raise InvalidSecretKeyError(f"il segreto {key!r} punta fuori da {base}")
    return path


def _interactive() -> bool:
    return sys.stdin.isatty()


def _getpass(prompt: str) -> str:
    # Gli asterischi durante la digitazione sono disponibili solo da Python 3.14.
    if sys.version_info >= (3, 14):
        return getpass.getpass(prompt, echo_char="*")
    return getpass.getpass(prompt)


def _confirm(prompt: str) -> bool:
    # Default N: conferma solo con esattamente "y" o "Y".
    try:
        return input(prompt) in ("y", "Y")
    except EOFError:
        return False


def _iter_paths(base: Path):
    yield base
    yield from sorted(base.rglob("*"))


def _report(paths) -> int:
    found = 0
    for p in paths:
        if problem := permission_problem(p):
            print(problem, file=sys.stderr)
            found = 1
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="secrets", description="Manage the secrets used by secretyaml")
    parser.add_argument("--dir", help="secrets folder (default: $SECRETYAML_DIR or ~/.secrets)")
    sub = parser.add_subparsers(dest="command", required=True)
    p_add = sub.add_parser("add", help="add or replace a secret (prompt, or stdin when piped)")
    p_add.add_argument("key", help='secret name, e.g. "servizio/token"')
    p_add.add_argument("-f", "--force", action="store_true", help="overwrite an existing secret without asking")
    p_remove = sub.add_parser("remove", help="remove a secret")
    p_remove.add_argument("key", help='secret name, e.g. "servizio/token"')
    p_remove.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")
    sub.add_parser("list", help="list secret names (never the values)")
    p_check = sub.add_parser("check", help="verify permissions (700 folders, 600 files)")
    p_check.add_argument("--fix", action="store_true", help="fix permissions that are too open")
    args = parser.parse_args(argv)

    base = default_base_dir(args.dir)
    try:
        match args.command:
            case "add":
                return cmd_add(base, args.key, args.force)
            case "remove":
                return cmd_remove(base, args.key, args.yes)
            case "list":
                return cmd_list(base)
            case "check":
                return cmd_check(base, args.fix)
    except SecretYamlError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAborted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
