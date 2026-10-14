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
config["login"]["password"]          # "s3greta": il contenuto di ~/.secrets/mioservizio/password

config["login"]["user"] = "altro@test.com"
secretyaml.save(config)              # riscrive config.yaml con password: !secret "mioservizio/password"
```

- **`load(path)`** legge il file e restituisce un `dict` con le password già in chiaro. L'app lo usa come un
  dizionario qualsiasi. Il documento deve essere un dizionario: un file vuoto restituisce `{}`, una lista o
  un valore singolo sollevano `SecretYamlError`.
- **`save(config)`** riscrive il dizionario nello stesso file da cui è stato caricato. La libreria ricorda quali
  campi venivano da un `!secret` e li riscrive come `!secret "chiave"`, così la password non finisce mai nel YAML.
  - Nessuna app può cambiare una password: lo fa solo l'amministratore, a mano, con `secrets add`.
    Se un'app sostituisce un campo segreto con un valore nuovo, `save` solleva `SecretYamlError` e non scrive nulla.
  - I commenti del file originale si perdono (l'ordine delle chiavi resta).
  - Con `save(dati, path)` si può scrivere in un altro file, anche un dizionario non caricato con `load`.
- **Valori segreti nei log:** sono stringhe normali, ma il loro `repr` è mascherato. `print(config)` mostra
  `Secret('***', key='mioservizio/password')` invece della password.

## Come funziona

Ogni `!secret "a/b"` viene sostituito dal contenuto del file `~/.secrets/a/b`, senza il newline finale.

- **Permessi:** le cartelle devono avere `700` e i file `600`, e devono appartenere all'utente corrente. Altrimenti la libreria solleva `InsecurePermissionsError` invece di leggere.
- **Chiavi rifiutate:** quelle vuote, quelle assolute (`/chiave`), quelle che iniziano con `~` (`~/chiave`), quelle con `..` e quelle che puntano fuori dalla cartella dei segreti.
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
