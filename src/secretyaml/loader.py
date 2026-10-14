from pathlib import Path
from typing import IO, Any

import yaml

from secretyaml.errors import SecretYamlError
from secretyaml.resolvers import FileResolver, SecretResolver

TAG = "!secret"


def _make_loader(resolver: SecretResolver) -> type[yaml.SafeLoader]:
    class Loader(yaml.SafeLoader):
        pass

    def construct_secret(loader: yaml.SafeLoader, node: yaml.Node) -> str:
        if not isinstance(node, yaml.ScalarNode):
            mark = node.start_mark
            raise SecretYamlError(
                f"{TAG} accetta solo una stringa (riga {mark.line + 1}, colonna {mark.column + 1})"
            )
        return resolver.resolve(loader.construct_scalar(node))

    # Registrato sulla sottoclasse: il SafeLoader globale resta intatto.
    Loader.add_constructor(TAG, construct_secret)
    return Loader


def loads(text: str | bytes, resolver: SecretResolver | None = None) -> Any:
    """Interpreta un documento YAML sostituendo ogni `!secret "chiave"` con il valore del segreto."""
    return yaml.load(text, Loader=_make_loader(resolver or FileResolver()))


def load(source: str | Path | IO, resolver: SecretResolver | None = None) -> Any:
    """Come `loads`, ma legge da un percorso o da uno stream già aperto."""
    if isinstance(source, (str, Path)):
        with open(source, encoding="utf-8") as f:
            return loads(f.read(), resolver)
    return yaml.load(source, Loader=_make_loader(resolver or FileResolver()))
