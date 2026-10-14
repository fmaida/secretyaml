class SecretYamlError(Exception):
    """Errore base della libreria. I messaggi non contengono mai il valore del segreto."""


class SecretNotFoundError(SecretYamlError):
    """Il segreto richiesto non esiste nella sorgente."""


class InvalidSecretKeyError(SecretYamlError):
    """La chiave del segreto non è valida (vuota, assoluta, con '..' o fuori dalla cartella base)."""


class InsecurePermissionsError(SecretYamlError):
    """Un file o una cartella dei segreti ha permessi troppo aperti o un proprietario diverso."""
