#!/usr/bin/env python3
"""
Testador interativo de candidatos -- rodar LOCALMENTE.

Mostra um candidato por vez. Voce aperta ENTER pra disparar o codigo
(a barra de volume eh aberta automaticamente logo antes de cada
candidato de VOLUME-, pra garantir que o OSD esteja visivel). Depois
de ver a reacao (ou falta dela) na tela, digita:

  s  = SIM, funcionou -> salva no codebook.json e encerra
  n  = nao funcionou -> pula pro proximo candidato
  r  = repetir o mesmo candidato (caso queira ver de novo)
  q  = sair sem salvar nada

Uso:
    python test_candidates_interactive.py
"""
import sys

from config import load_config
from tuya_client import TuyaIRClient, TuyaAPIError
import codebook
from nec_encoder import encode_nec

# Candidatos ainda nao confirmados por voce ao vivo (o de cima de cada
# lista eh o mais provavel).
VOLUME_DOWN_CANDIDATES = [
    ("8B", "VOLUME+ - 1 (sequencial, mesmo padrao usado no D-pad)"),
    ("8D", "VOLUME+ + 1 (sequencial)"),
    ("AC", "simetria com a fileira POWER/MUTE"),
    ("8E", "VOLUME+ com bit 1 invertido"),
    ("90", "proximo a MENU"),
    ("92", "proximo a MENU"),
    ("94", "proximo a CIMA"),
    ("96", "= ESQUERDA nao, ja testado como outro botao"),
]

ESQUERDA_CANDIDATE = ("9B", "confirmado pelo app Tuya como navigate_left")


def build_hex(cmd_hex: str) -> str:
    cmd = int(cmd_hex, 16)
    cmd_inv = (~cmd) & 0xFF
    return f"00FF{cmd:02X}{cmd_inv:02X}"


def fire(client: TuyaIRClient, hex_code: str, label: str, open_osd_first: bool = False):
    if open_osd_first:
        entry = codebook.get("VOLUME+")
        if entry:
            try:
                client.send_raw_code(entry["code_b64"], label="OPEN_OSD")
            except TuyaAPIError:
                pass
    try:
        client.send_ir_code(hex_code, label=label)
        print(f"  -> enviado 0x{hex_code}")
    except TuyaAPIError as e:
        print(f"  [ERRO] {e}")
    except ValueError as e:
        print(f"  [CODIGO INVALIDO] {e}")


def run_candidate_loop(client, button_name: str, candidates, open_osd_first: bool):
    print(f"\n=== Testando {button_name} ===")
    for cmd_hex, reason in candidates:
        hex_code = build_hex(cmd_hex)
        while True:
            print(f"\nCandidato: 0x{hex_code}  ({reason})")
            input("  Pressione ENTER pra disparar...")
            fire(client, hex_code, label=f"{button_name}_TEST", open_osd_first=open_osd_first)
            choice = input("  Funcionou? [s=sim salva / n=proximo / r=repetir / q=sair]: ").strip().lower()
            if choice == "s":
                codebook.set_entry(
                    button_name,
                    code_b64=encode_nec(hex_code),
                    nec_hex=hex_code.replace("0x", "").lower(),
                    source="inferred_confirmed",
                    checksum_ok=True,
                )
                print(f"  [SALVO] {button_name} = 0x{hex_code} gravado no codebook.json!")
                return True
            if choice == "q":
                print("Saindo sem salvar.")
                return False
            if choice == "r":
                continue  # repete o mesmo candidato
            break  # "n" ou qualquer outra coisa -> proximo candidato
    print(f"\nNenhum candidato de {button_name} foi confirmado nessa rodada.")
    return False


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

    print("O que quer testar?")
    print("  1) VOLUME- (varios candidatos, um por vez)")
    print("  2) ESQUERDA (o candidato que o app confirmou: 0x9B)")
    print("  3) Ambos, ESQUERDA primeiro")
    choice = input("Escolha: ").strip()

    if choice in ("2", "3"):
        cmd_hex, reason = ESQUERDA_CANDIDATE
        run_candidate_loop(client, "ESQUERDA", [(cmd_hex, reason)], open_osd_first=False)

    if choice in ("1", "3"):
        run_candidate_loop(client, "VOLUME-", VOLUME_DOWN_CANDIDATES, open_osd_first=True)

    print("\nStatus atual do codebook:")
    for k, v in sorted(codebook.all_entries().items()):
        print(f"  {k:<12} 0x{v['nec_hex'].upper() if v.get('nec_hex') else '?'}  (fonte: {v['source']})")


if __name__ == "__main__":
    main()
