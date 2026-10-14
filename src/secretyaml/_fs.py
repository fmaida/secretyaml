import os
import tempfile
from pathlib import Path


def atomic_write(path: Path, text: str, mode: int) -> None:
    """Scrive `text` in `path` passando da un file temporaneo nella stessa cartella e `os.replace`."""
    # mkstemp crea il file con permessi 600: il contenuto non è mai leggibile da altri durante la scrittura.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".secretyaml-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def current_umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask
