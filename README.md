# secretyaml

Carica file YAML che contengono riferimenti a segreti, così password e token non finiscono mai su Git.

```yaml
# config.yaml: può essere versionato senza problemi
login:
    user: francesco@test.com
    password: !secret "mioservizio/password"
```

```python
import secretyaml

config = secretyaml.load("config.yaml")
config["login"]["password"]   # contenuto del file ~/.secrets/mioservizio/password
```

## Come funziona

Ogni `!secret "a/b"` viene sostituito dal contenuto del file `~/.secrets/a/b`, senza il newline finale.

- **Permessi:** le cartelle devono avere `700` e i file `600`, e devono appartenere all'utente corrente. Altrimenti la libreria solleva `InsecurePermissionsError` invece di leggere.
- **Chiavi rifiutate:** quelle vuote, quelle assolute, quelle con `..` e quelle che puntano fuori dalla cartella dei segreti.
- **Cartella dei segreti:** `FileResolver("/altra/cartella")`, oppure la variabile `SECRETYAML_DIR`; altrimenti `~/.secrets`.
- **Parsing sicuro:** usa `yaml.SafeLoader`.

```python
from secretyaml import FileResolver
config = secretyaml.load("config.yaml", resolver=FileResolver("/srv/secrets"))
```

## Cosa non fa

secretyaml **non è pensato per tenere al sicuro i dati**. I segreti sono salvati in chiaro su disco, senza cifratura.
L'unica protezione sono i permessi del filesystem. Chi ottiene l'accesso al tuo utente, chi ha i privilegi di root
o chi legge un backup del disco può leggere tutte le password.

Lo scopo è un altro, più pragmatico:
- tenere password e token **fuori dai file versionati**, così non finiscono per sbaglio su Git o su GitHub;
- **condividere** le credenziali dello stesso servizio fra più app.

Se ti serve una protezione reale dei dati, usa uno strumento pensato per questo: un password manager, il portachiavi
di sistema, SOPS, Vault o i secret manager dei cloud provider.

## Gestire i segreti

Con `pipx install .` si ottiene il comando `secrets`:

```
$ secrets add servizio/token
Please type the password: **********
Please enter it again   : **********
Secret added as servizio/token

$ secrets remove servizio/token
are you sure (y/N): y
servizio/token has been removed

$ secrets list            # solo i nomi, mai i valori
$ secrets check --fix     # verifica e corregge i permessi
```

Le conferme accettano solo `y` o `Y`; qualsiasi altra risposta annulla. Con `--dir` si usa un'altra cartella.

## Sviluppo

```bash
uv sync
uv run pytest
```
