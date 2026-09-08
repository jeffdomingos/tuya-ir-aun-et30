"""
Codebook: armazena localmente, por nome de botão, os códigos IR já
descobertos para o controle do projetor AUN ET30.

Cada entrada guarda:
  - code_b64: o payload no formato da Tuya, pronto para reenviar
              (via /remotes/{id}/learning-codes) sem precisar
              recodificar nada. É a forma mais confiável de reenviar
              um código aprendido do controle físico.
  - nec_hex:  os 4 bytes NEC decodificados (se o sinal seguiu o
              protocolo NEC padrão), só para leitura/análise humana.
  - source:   "learned"   -> capturado do controle físico real
              "synthetic" -> gerado pelos presets originais (nec_encoder)
              "inferred"  -> chute educado para um botão quebrado,
                              ainda não confirmado no aparelho
  - checksum_ok: se os bytes de complemento do NEC batem (indica
                 leitura confiável quando source == "learned")
"""
import json
from pathlib import Path
from typing import Optional

CODEBOOK_FILE = Path(__file__).parent / "codebook.json"


def load() -> dict:
    if CODEBOOK_FILE.exists():
        try:
            return json.loads(CODEBOOK_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save(data: dict):
    CODEBOOK_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def get(button_name: str) -> Optional[dict]:
    return load().get(button_name)


def set_entry(
    button_name: str,
    code_b64: str,
    nec_hex: Optional[str] = None,
    source: str = "learned",
    checksum_ok: Optional[bool] = None,
):
    data = load()
    data[button_name] = {
        "code_b64": code_b64,
        "nec_hex": nec_hex,
        "source": source,
        "checksum_ok": checksum_ok,
    }
    save(data)


def all_entries() -> dict:
    return load()


def delete_entry(button_name: str):
    data = load()
    data.pop(button_name, None)
    save(data)
