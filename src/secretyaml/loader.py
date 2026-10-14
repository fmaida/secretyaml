import stat
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from secretyaml._fs import atomic_write, current_umask
from secretyaml.errors import SecretYamlError
from secretyaml.resolvers import FileResolver, SecretResolver
from secretyaml.types import Secret, SecretYamlDict

TAG = "!secret"
_MISSING = object()


def _make_loader(resolver: SecretResolver) -> type[yaml.SafeLoader]:
    class Loader(yaml.SafeLoader):
        pass

    def construct_secret(loader: yaml.SafeLoader, node: yaml.Node) -> Secret:
        if not isinstance(node, yaml.ScalarNode):
            mark = node.start_mark
            raise SecretYamlError(
                f"{TAG} accetta solo una stringa (riga {mark.line + 1}, colonna {mark.column + 1})"
            )
        key = loader.construct_scalar(node)
        return Secret(resolver.resolve(key), key)

    # Registrato sulla sottoclasse: il SafeLoader globale resta intatto.
    Loader.add_constructor(TAG, construct_secret)
    return Loader


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True  # niente &id001 / *id001 se lo stesso oggetto compare più volte


_Dumper.add_representer(Secret, lambda dumper, s: dumper.represent_scalar(TAG, s.key, style='"'))
_Dumper.add_representer(SecretYamlDict, yaml.representer.SafeRepresenter.represent_dict)


def load(path: str | Path, resolver: SecretResolver | None = None) -> SecretYamlDict:
    """Legge il file YAML in `path` e restituisce il dizionario con i segreti già risolti.

    Il dizionario ricorda il file di origine e i campi segreti, così `save` può riscriverlo
    rimettendo i tag `!secret`. Un documento vuoto restituisce un dizionario vuoto.
    """
    path = Path(path).absolute()
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=_make_loader(resolver or FileResolver()))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise SecretYamlError(
            f"il documento YAML deve essere un dizionario, trovato {type(data).__name__}"
        )
    return SecretYamlDict(data, source_path=path, secret_fields=dict(_find_secrets(data, ())))


def save(data: dict, path: str | Path | None = None) -> None:
    """Riscrive `data` su disco, nel file da cui è stato caricato (o in `path`).

    I valori `Secret` tornano a essere `!secret "chiave"`. Se un campo che era segreto ora
    contiene un valore normale, solleva `SecretYamlError` senza scrivere nulla.
    """
    if path is None:
        path = getattr(data, "source_path", None)
        if path is None:
            raise SecretYamlError("il dizionario non proviene da load: indica il percorso in cui salvarlo")
    path = Path(path)

    for field, key in getattr(data, "secret_fields", {}).items():
        value = _lookup(data, field)
        if value is not _MISSING and not isinstance(value, Secret):
            raise SecretYamlError(
                f"il campo {_format_field(field)} era {TAG} {key!r} ma ora contiene un valore in chiaro; "
                "le app non possono modificare i segreti, lo fa l'amministratore con `secrets add`. "
                "Nessun file scritto."
            )

    text = yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, default_flow_style=False)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o666 & ~current_umask()
    atomic_write(path, text, mode)


def _find_secrets(obj: Any, prefix: tuple) -> Iterator[tuple[tuple, str]]:
    if isinstance(obj, Secret):
        yield prefix, obj.key
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _find_secrets(v, (*prefix, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _find_secrets(v, (*prefix, i))


def _lookup(obj: Any, field: tuple) -> Any:
    for part in field:
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        elif isinstance(obj, list) and isinstance(part, int) and 0 <= part < len(obj):
            obj = obj[part]
        else:
            return _MISSING
    return obj


def _format_field(field: tuple) -> str:
    out = ""
    for part in field:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out
