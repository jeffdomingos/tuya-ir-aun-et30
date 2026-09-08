#!/usr/bin/env python3
"""
Controle remoto "de verdade" no terminal -- roda LOCALMENTE (Windows).

Aperta UMA tecla e o comando dispara na hora (sem precisar de ENTER),
que nem um controle fisico. Usa os codigos confirmados do
codebook.json, mais duas variantes extras de ESQUERDA e VOLUME- que
ainda estao em teste.

Uso:
    python remote.py

Teclas:
    1 = POWER          2 = MUTE           3 = INPUT
    4 = MENU           5 = VOLTAR         6 = OK
    w = CIMA           a = ESQUERDA (verbatim, do app)
    s = BAIXO          d = DIREITA
    e = ESQUERDA (sintetizado -- variante de teste)
    + = VOLUME+        - = VOLUME- (confirmado 0x8B74)
    _ = VOLUME- (variante alternativa 0x8D72, caso a de cima pare de bater)
    < = REWIND         > = FORWARD        p = PLAY_PAUSE
    z = ESQUERDA verbatim de novo (repete o teste que ja falhou, caso queira reconferir)
    q = sair
"""
import sys

from config import load_config
from tuya_client import TuyaIRClient, TuyaAPIError
import codebook

# Codigos "em teste" que ainda nao tem uma fonte 100% confirmada e
# consistente -- ficam fora do codebook.json ate serem validados.
ESQUERDA_VERBATIM = (
    "b922a11133023302330233023302330233023302330233023302330233023302330233"
    "023302a7063302a7063302a7063302a7063302a7063302a7063302a7063302a706330"
    "2a7063302a706330233023302a7063302a70633023302330233023302a70633023302"
    "330233023302a70633023302330233023302a7063302a706330233023302d0fb"
)
ESQUERDA_SYNTH_HEX = "00FF9B64"
VOLUME_DOWN_ALT_HEX = "00FF8D72"  # candidato anterior, caso 8B74 pare de funcionar


def fire_saved(client, button_name: str):
    entry = codebook.get(button_name)
    if not entry:
        print(f"  [AVISO] '{button_name}' nao esta no codebook ainda.")
        return
    try:
        resp = client.send_raw_code(entry["code_b64"], label=f"REMOTE_{button_name}")
        print(f"  -> {button_name} (0x{entry.get('nec_hex', '?').upper()}) enviado. {resp.get('success')}")
    except TuyaAPIError as e:
        print(f"  [ERRO] {e}")


def fire_raw_verbatim(client, code: str, label: str):
    try:
        resp = client.send_raw_code(code, label=label)
        print(f"  -> [verbatim] {label} enviado. {resp.get('success')}")
    except TuyaAPIError as e:
        print(f"  [ERRO] {e}")


def fire_synth_hex(client, hex_code: str, label: str):
    try:
        resp = client.send_ir_code(hex_code, label=label)
        print(f"  -> [sintetizado] {label} (0x{hex_code}) enviado. {resp.get('success')}")
    except (TuyaAPIError, ValueError) as e:
        print(f"  [ERRO] {e}")


KEY_MAP_SAVED = {
    "1": "POWER",
    "2": "MUTE",
    "3": "INPUT",
    "4": "MENU",
    "5": "VOLTAR",
    "6": "OK",
    "w": "CIMA",
    "s": "BAIXO",
    "d": "DIREITA",
    "+": "VOLUME+",
    "-": "VOLUME-",
    "<": "REWIND",
    ">": "FORWARD",
    "p": "PLAY_PAUSE",
}


def print_legend():
    print(__doc__)


def get_key():
    """Le uma tecla sem precisar de ENTER. So funciona no Windows (msvcrt)."""
    try:
        import msvcrt
    except ImportError:
        # Fallback pra Linux/Mac: pede ENTER mesmo
        return input("Tecla: ").strip()[:1]
    ch = msvcrt.getch()
    try:
        return ch.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def main():
    print("Carregando configuracao (.env)...")
    try:
        cfg = load_config()
    except EnvironmentError as e:
        print(f"[ERRO] {e}")
        sys.exit(1)

    client = TuyaIRClient(cfg.endpoint, cfg.access_id, cfg.access_secret, cfg.device_id)
    print(f"Conectando a Tuya Cloud ({cfg.endpoint})...")
    try:
        client.connect()
    except Exception as e:
        print(f"[ERRO DE AUTENTICACAO] {e}")
        sys.exit(1)
    print("[OK] Autenticado.\n")

    print_legend()
    print("\nAponte o Hub pro projetor e comece a apertar as teclas.\n")

    while True:
        key = get_key()
        if not key:
            continue
        if key == "q":
            print("Saindo.")
            break
        if key in KEY_MAP_SAVED:
            fire_saved(client, KEY_MAP_SAVED[key])
        elif key == "a":
            fire_raw_verbatim(client, ESQUERDA_VERBATIM, "ESQUERDA_VERBATIM")
        elif key == "z":
            fire_raw_verbatim(client, ESQUERDA_VERBATIM, "ESQUERDA_VERBATIM_RETEST")
        elif key == "e":
            fire_synth_hex(client, ESQUERDA_SYNTH_HEX, "ESQUERDA_SYNTH")
        elif key == "_":
            fire_synth_hex(client, VOLUME_DOWN_ALT_HEX, "VOLUME_DOWN_ALT")
        else:
            print(f"  (tecla '{key}' nao mapeada -- aperte a legenda acima)")


if __name__ == "__main__":
    main()
