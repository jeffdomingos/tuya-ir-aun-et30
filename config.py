"""
Carregamento e validação das configurações da Tuya Cloud.

As credenciais são lidas do arquivo .env (veja .env.example). Se alguma
variável obrigatória estiver faltando, o usuário é avisado no terminal
em vez de o script falhar com um traceback confuso.
"""
import os
from dataclasses import dataclass
from getpass import getpass

from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = ("TUYA_ACCESS_KEY", "TUYA_SECRET_KEY", "TUYA_DEVICE_ID")
DEFAULT_ENDPOINT = "https://openapi.tuyaus.com"


@dataclass
class TuyaConfig:
    access_id: str
    access_secret: str
    endpoint: str
    device_id: str


def _prompt_for_missing(name: str) -> str:
    """Se a variável não estiver no .env, pergunta interativamente no terminal."""
    secret_vars = {"TUYA_SECRET_KEY"}
    prompt = f"{name} não encontrado no .env. Digite o valor agora: "
    if name in secret_vars:
        return getpass(prompt)
    return input(prompt).strip()


def load_config(interactive: bool = True) -> TuyaConfig:
    values = {}
    for name in REQUIRED_VARS:
        value = os.getenv(name)
        if not value and interactive:
            value = _prompt_for_missing(name)
        values[name] = value

    missing = [name for name, val in values.items() if not val]
    if missing:
        raise EnvironmentError(
            "Variáveis de ambiente obrigatórias faltando: "
            + ", ".join(missing)
            + ". Configure o arquivo .env (veja .env.example) ou exporte-as no shell."
        )

    endpoint = os.getenv("TUYA_ENDPOINT", DEFAULT_ENDPOINT)

    return TuyaConfig(
        access_id=values["TUYA_ACCESS_KEY"],
        access_secret=values["TUYA_SECRET_KEY"],
        endpoint=endpoint,
        device_id=values["TUYA_DEVICE_ID"],
    )
