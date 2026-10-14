from pathlib import Path
from typing import Any


class Secret(str):
    """Valore letto da un tag `!secret`: si comporta come una stringa e ricorda la propria chiave.

    `save` lo riscrive come `!secret "chiave"`; `repr` non mostra mai il valore.
    """

    key: str

    def __new__(cls, value: str, key: str):
        obj = super().__new__(cls, value)
        obj.key = key
        return obj

    def __repr__(self) -> str:
        return f"Secret('***', key={self.key!r})"

    def __reduce__(self):
        return (Secret, (str(self), self.key))


class SecretYamlDict(dict):
    """Dizionario restituito da `load`: ricorda il file di origine e quali campi erano segreti."""

    def __init__(
        self,
        data: Any = (),
        *,
        source_path: Path | None = None,
        secret_fields: dict[tuple, str] | None = None,
    ):
        super().__init__(data)
        self.source_path = source_path
        self.secret_fields = dict(secret_fields or {})
