#!/usr/bin/env python3
"""
Controle remoto no terminal so pra testar candidatos de VOLUME- --
roda LOCALMENTE (Windows). Aperta uma tecla (1-9, 0) e ele dispara
SOMENTE aquele candidato -- nenhum outro comando eh enviado antes ou
depois. Sem combos, sem "abrir a barra primeiro".

Se algum funcionar, aperta a tecla de novo pra confirmar, e me avisa
qual foi (ex: "funcionou o 3") que eu salvo no codebook.json.

Uso:
    python remote_voldown.py

Teclas -> candidatos (comando NEC, endereco 0x00):
    1 = 0x8B  (VOLUME+ - 1, sequencial)
    2 = 0x8D  (VOLUME+ + 1, sequencial)
    3 = 0xAC  (simetria com a fileira POWER/MUTE)
    4 = 0x8E  (VOLUME+ com bit 1 invertido)
    5 = 0x8A  (VOLUME+ - 2)
    6 = 0x8F  (VOLUME+ + 3)
    7 = 0x90  (proximo a MENU)
    8 = 0x84  (proximo a FORWARD)
    9 = 0x9C  (perto do cluster do D-pad, vizinho de ESQUERDA=0x9B)
    0 = 0x9D  (perto do cluster do D-pad, vizinho de OK=0x9E)
    q = sair
"""
import sys

from config import load_config
from tuya_client import TuyaIRClient, TuyaAPIError

CANDIDATES = {
    "1": "8B",
    "2": "8D",
    "3": "AC",
    "4": "8E",
    "5": "8A",
    "6": "8F",
    "7": "90",
    "8": "84",
    "9": "9C",
    "0": "9D",
}


def build_hex(cmd_hex: str) -> str:
    cmd = int(cmd_hex, 16)
    cmd_inv = (~cmd) & 0xFF
    return f"00FF{cmd:02X}{cmd_inv:02X}"


def fire_candidate(client, cmd_hex: str, key: str):
    hex_code = build_hex(cmd_hex)
    try:
        client.send_ir_code(hex_code, label=f"VOLDOWN_{key}")
        print(f"  -> [{key}] enviado 0x{hex_code} (SOMENTE esse comando, nada mais)")
    except (TuyaAPIError, ValueError) as e:
        print(f"  [ERRO] {e}")


def get_key():
    try:
        import msvcrt
    except ImportError:
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

    print(__doc__)
    print("\nAponte o Hub pro projetor. Cada tecla dispara SO o candidato,")
    print("nada mais. Fique de olho na tela / no som do volume.\n")

    while True:
        key = get_key()
        if not key:
            continue
        if key == "q":
            print("Saindo.")
            break
        if key in CANDIDATES:
            cmd_hex = CANDIDATES[key]
            print(f"Testando tecla {key} -> comando 0x{cmd_hex} (isolado)")
            fire_candidate(client, cmd_hex, key)
        else:
            print(f"  (tecla '{key}' nao mapeada)")


if __name__ == "__main__":
    main()
