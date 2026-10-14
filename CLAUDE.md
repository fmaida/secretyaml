# SecretYAML

Questa libreria serve a poter aprire un documento YAML formattato "fuori standard", perchè contiene una stringa da interpretare per poi ottenere di ritorno una password.

## Esempio

```yaml
login:
    user: francesco@test.com
    password: !secret "mioservizio/password"
```

In questo caso dopo il parsing del file YAML, l'app si accorge che c'è qualcosa da verificare: quella `password: !secret "mioservizio/password"` viene riconosciuto, e in base al plugin selezionato va a recuperare la password da `mioservizio/password`.

Inizialmente prevediamo un solo tipo di plugin possibile, che memorizza le password in file in chiaro sul disco dell'utente nella cartella `~/.secrets/`

Nell'esempio precedente, `mioservizio/password`, la libreria andrà a verificare l'esistenza di un file in `~/.secrets/mioservizio/password`, aprirlo e sostituire il suo valore alla stringa `!secret "mioservizio/password"`

Chiaramente la cartella `~/.secrets` e tutte le sue sottocartelle e i files dovranno avere permessi di lettura e scrittura limitati per evitare le fughe di dati (cartelle `700`, file `600`: accesso solo al proprietario, come per `~/.ssh`). La libreria rifiuta di leggere segreti con permessi più aperti o con un proprietario diverso (`InsecurePermissionsError`, disattivabile con `check_permissions=False`); `secrets check --fix` li corregge.

La cartella base è configurabile: argomento `base_dir` di `FileResolver`, poi variabile `SECRETYAML_DIR`, poi `~/.secrets`.

Non è un sistema pensato per tenere le password al sicuro dai furti di dati, ma piuttosto è un sistema pragmatico per permettere di condividere le password dello stesso servizio fra app diverse senza avere l'incubo che una password reale o un token reale finiscano per sbaglio versionate su Git e su GitHub.

Considera che in produzione le app che useranno questa libreria staranno su una VPS in cui solo io ho l'accesso via SSH.

## Struttura del codice

- `src/secretyaml/loader.py`: `load` / `loads`. Il tag `!secret` è registrato su una sottoclasse di `yaml.SafeLoader`, mai sul SafeLoader globale.
- `src/secretyaml/resolvers.py`: protocollo `SecretResolver` (`resolve(key) -> str`), cioè il "plugin", e l'unica implementazione attuale `FileResolver`. Qui stanno anche la validazione delle chiavi (niente chiavi vuote, assolute, con `..` o con symlink che escono dalla base) e il controllo dei permessi.
- `src/secretyaml/errors.py`: `SecretYamlError` e sottoclassi. I messaggi non devono **mai** contenere il valore di un segreto.
- `src/secretyaml/cli.py`: il comando `secrets` (`add`, `remove`, `list`, `check`).

## Convenzioni

- Python >= 3.13, unica dipendenza PyYAML. Build con poetry-core, ambiente gestito con uv.
- Versionamento CalVer `AA.MM.patch` (es. `26.10.0`).
- Il protocollo `SecretResolver` resta minimale: tutto ciò che riguarda i file (permessi, percorsi) sta in `FileResolver`, non nel loader.
- Niente funzione `dump`: riscriverebbe i segreti in chiaro.
- CLI:
  - messaggi in inglese;
  - ogni conferma ha default N e accetta solo `y` o `Y` esatti;
  - `add` chiede la password due volte e, se il segreto esiste, chiede di sovrascriverlo prima di chiedere la password;
  - quando lo stdin non è un terminale, `add` legge da stdin e serve `--force` per sovrascrivere, mentre `remove` richiede `--yes`.
- Il nome `secrets` va in conflitto con il pacchetto Debian/Ubuntu `secrets` (password manager GNOME, `/usr/bin/secrets`). È irrilevante su macOS e su una VPS senza desktop, ma va tenuto presente.

## Comandi di sviluppo

```bash
uv sync               # installa dipendenze e pacchetto in modalità editabile
uv run pytest         # test
uv run secrets --dir /tmp/prova list
```

## Estensioni future

- `KeyringResolver` basato sulla libreria `keyring` (Keychain macOS, Secret Service Linux). La chiave `"servizio/utente"` diventa `keyring.get_password("servizio", "utente")`. La dipendenza va resa opzionale (extra `secretyaml[keyring]`, con import pigro).
