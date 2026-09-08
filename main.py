#!/usr/bin/env python3
"""
CLI interativa para disparar códigos IR (NEC, 38kHz) no projetor
AUN ET30 através de um Hub Smart IR da Tuya, via API Cloud.

Suporta três formas de obter um código IR:
  1. Aprendizado real: aponta o controle físico pro Hub e captura o
     sinal de verdade (mais confiável, use para botões que funcionam).
  2. Inferência: para botões fisicamente quebrados (não transmitem
     nada), gera candidatos plausíveis a partir de botões vizinhos já
     aprendidos e permite testar cada um ao vivo no aparelho.
  3. Placeholder sintético: os códigos de exemplo originais (gerados
     por hex "chutado" antes de qualquer captura real) — só usados se
     nada tiver sido aprendido ainda para aquele botão.

Uso:
    python3 main.py
"""
import sys

import codebook
import inference
from config import load_config
from tuya_client import TuyaAPIError, TuyaAuthError, TuyaIRClient, TuyaLearningTimeout

# Botões do controle físico (nome de exibição -> chave no codebook)
WORKING_BUTTONS = [
    ("POWER", "POWER"),
    ("MUTE", "MUTE"),
    ("REWIND (<<)", "REWIND"),
    ("PLAY / PAUSE", "PLAY_PAUSE"),
    ("FORWARD (>>)", "FORWARD"),
    ("CIMA", "CIMA"),
    ("DIREITA", "DIREITA"),
    ("BAIXO", "BAIXO"),
    ("OK", "OK"),
    ("VOLTAR", "VOLTAR"),
    ("MENU", "MENU"),
    ("INPUT / SOURCE", "INPUT"),
    ("VOLUME +", "VOLUME+"),
]

BROKEN_BUTTONS = [
    ("ESQUERDA", "ESQUERDA"),
    ("VOLUME -", "VOLUME-"),
]

ALL_BUTTONS = WORKING_BUTTONS + BROKEN_BUTTONS

# Placeholders sintéticos originais (usados apenas como último recurso,
# antes de qualquer aprendizado real ter sido feito). Não têm relação
# confirmada com o controle físico real do usuário.
SYNTHETIC_PLACEHOLDERS = {
    "POWER": "00FF02FD",
    "INPUT": "00FF0DF2",
    "CIMA": "00FF00FF",
    "BAIXO": "00FF01FE",
    "ESQUERDA": "00FF03FC",
    "DIREITA": "00FF04FB",
    "OK": "00FF05FA",
    "MENU": "00FF0EF1",
    "VOLTAR": "00FF0FF0",
}


def print_main_menu():
    print("\n" + "=" * 60)
    print(" Controle IR — Projetor AUN ET30 (Tuya Smart IR Hub)")
    print("=" * 60)
    print("  1) Enviar comando")
    print("  2) Aprender código de um botão (controle físico -> Hub)")
    print("  3) Inferir + testar código de um botão quebrado")
    print("  4) Ver status dos códigos (codebook)")
    print("  5) Importar códigos de um controle virtual já existente (app)")
    print("  m) Enviar código NEC manual (hex)")
    print("  q) Sair")
    print("-" * 60)


def status_for(key: str) -> str:
    entry = codebook.get(key)
    if entry:
        tag = entry.get("source", "?")
        if tag == "learned":
            chk = "OK" if entry.get("checksum_ok") else "checksum suspeito"
            return f"aprendido ({chk})"
        if tag == "inferred_confirmed":
            return "inferido e confirmado no aparelho"
        if tag == "imported_from_app":
            chk = "OK" if entry.get("checksum_ok") else "checksum suspeito/desconhecido"
            return f"importado do app ({chk})"
        return tag
    if key in SYNTHETIC_PLACEHOLDERS:
        return "placeholder (não confirmado)"
    return "sem código"


def resolve_code_for_send(key: str):
    """
    Retorna (modo, valor) onde modo é 'raw' (base64 aprendido/inferido
    confirmado) ou 'hex' (código NEC sintético, via placeholder).
    """
    entry = codebook.get(key)
    if entry:
        return "raw", entry["code_b64"]
    if key in SYNTHETIC_PLACEHOLDERS:
        return "hex", SYNTHETIC_PLACEHOLDERS[key]
    return None, None


def menu_enviar(client: TuyaIRClient):
    print("\n-- Enviar comando --")
    for i, (label, key) in enumerate(ALL_BUTTONS, start=1):
        print(f"  {i:>2}) {label:<16} [{status_for(key)}]")
    print("   0) Voltar")
    choice = input("Escolha: ").strip()
    if choice == "0":
        return
    try:
        idx = int(choice) - 1
        label, key = ALL_BUTTONS[idx]
    except (ValueError, IndexError):
        print("[AVISO] Opção inválida.")
        return

    mode, value = resolve_code_for_send(key)
    if mode is None:
        print(f"[AVISO] Nenhum código disponível para '{label}' ainda. Aprenda ou infira primeiro.")
        return

    try:
        if mode == "raw":
            resp = client.send_raw_code(value, label=label)
        else:
            resp = client.send_ir_code(value, label=label)
    except TuyaAPIError as e:
        print(f"[FALHA] {e}")
        return
    except Exception as e:
        print(f"[ERRO INESPERADO] {type(e).__name__}: {e}")
        return

    if resp.get("provisioned"):
        print(f"[OK] Controle virtual provisionado e comando '{label}' disparado.")
    else:
        print(f"[OK] Comando '{label}' aceito pelo Hub.")


def menu_aprender(client: TuyaIRClient):
    print("\n-- Aprender código de um botão --")
    print("Aponte o controle físico direto para o Hub Smart IR antes de confirmar.")
    for i, (label, key) in enumerate(WORKING_BUTTONS, start=1):
        print(f"  {i:>2}) {label:<16} [{status_for(key)}]")
    print("   0) Voltar")
    choice = input("Qual botão você vai aprender: ").strip()
    if choice == "0":
        return
    try:
        idx = int(choice) - 1
        label, key = WORKING_BUTTONS[idx]
    except (ValueError, IndexError):
        print("[AVISO] Opção inválida.")
        return

    input(f"Aponte o controle pro Hub e pressione ENTER aqui, DEPOIS aperte '{label}' no controle rapidamente...")
    print("Aguardando sinal IR (até 20s)...")
    try:
        result = client.learn_button(key, timeout=20.0)
    except TuyaLearningTimeout as e:
        print(f"[SEM SINAL] {e}")
        return
    except TuyaAPIError as e:
        print(f"[FALHA] {e}")
        return

    decoded = result["decoded"]
    if decoded.ok:
        checksum_note = "checksum OK" if decoded.checksum_ok else "checksum não bateu — pode não ser NEC padrão"
        print(f"[OK] Capturado! Código NEC decodificado: 0x{decoded.hex_code.upper()} ({checksum_note})")
    else:
        print(f"[OK] Capturado, mas não foi possível decodificar como NEC padrão ({decoded.reason}).")
        print("     O código bruto foi salvo mesmo assim e pode ser reenviado normalmente.")
    print(f"Salvo no codebook como '{key}'.")


def menu_inferir(client: TuyaIRClient):
    print("\n-- Inferir + testar botão quebrado --")
    print("  1) ESQUERDA")
    print("  2) VOLUME -")
    print("  0) Voltar")
    choice = input("Qual botão: ").strip()
    if choice == "1":
        key, label = "ESQUERDA", "ESQUERDA"
        candidates = inference.infer_esquerda()
    elif choice == "2":
        key, label = "VOLUME-", "VOLUME -"
        candidates = inference.infer_volume_down()
    else:
        return

    if not candidates:
        print(
            "[AVISO] Não há códigos vizinhos suficientes aprendidos ainda para gerar candidatos.\n"
            "        Aprenda primeiro CIMA/BAIXO/DIREITA (para Esquerda) ou VOLUME+ (para Volume-)."
        )
        return

    print(f"\n{len(candidates)} candidato(s) gerado(s) para '{label}'. Vou testar um por vez.")
    print("Observe o projetor após cada envio.")
    for i, cand in enumerate(candidates, start=1):
        input(f"\n[{i}/{len(candidates)}] Pressione ENTER para testar 0x{cand.hex_code.upper()} ({cand.reason})...")
        try:
            resp = client.send_ir_code(cand.hex_code, label=f"{label}_CANDIDATE_{i}")
        except TuyaAPIError as e:
            print(f"[FALHA AO ENVIAR] {e}")
            continue
        print("[ENVIADO] O projetor reagiu como esperado para este botão?")
        confirm = input("  (s = sim, confirmar e salvar / n = não, próximo / q = parar): ").strip().lower()
        if confirm == "s":
            from nec_encoder import encode_nec

            codebook.set_entry(
                key,
                code_b64=encode_nec(cand.hex_code),
                nec_hex=cand.hex_code,
                source="inferred_confirmed",
                checksum_ok=True,
            )
            print(f"[OK] Confirmado e salvo! '{label}' = 0x{cand.hex_code.upper()}")
            return
        if confirm == "q":
            print("Parando os testes.")
            return
    print("Nenhum candidato funcionou. Pode ser necessário revisar as heurísticas ou tentar outro protocolo.")


def menu_importar(client: TuyaIRClient):
    print("\n-- Importar códigos de um controle virtual já existente --")
    print("Use isto para reaproveitar botões que você já aprendeu pelo")
    print("app Tuya Smart/Smart Life (ex: um controle 'Projetor' criado por lá).")
    remote_id = input("Device ID / remote_id do controle virtual (ex: ebcd3a6ddab7c79bbbelvg): ").strip()
    if not remote_id:
        print("[AVISO] Nenhum ID informado.")
        return

    from nec_decoder import decode_tuya_code

    try:
        codes = client.list_remote_codes(remote_id)
    except TuyaAPIError as e:
        print(f"[FALHA] {e}")
        return

    if not codes:
        print("[AVISO] Nenhum código encontrado para esse remote_id (lista vazia).")
        return

    print(f"\n{len(codes)} código(s) encontrado(s):")
    button_keys = [key for _, key in ALL_BUTTONS]
    for entry in codes:
        name = entry.get("name") or ""
        key_name = entry.get("key_name") or ""
        code_b64 = entry.get("code")
        decoded = decode_tuya_code(code_b64) if code_b64 else None
        hex_preview = f"0x{decoded.hex_code.upper()}" if decoded and decoded.ok else "(não decodificável como NEC)"
        print(f"\n  name='{name}'  key_name='{key_name}'  {hex_preview}")
        print("  Mapear para qual botão do nosso projeto?")
        for i, (label, key) in enumerate(ALL_BUTTONS, start=1):
            print(f"    {i:>2}) {label}")
        print("     0) Pular (não importar este)")
        choice = input("  Escolha: ").strip()
        if choice == "0" or not choice:
            continue
        try:
            idx = int(choice) - 1
            label, key = ALL_BUTTONS[idx]
        except (ValueError, IndexError):
            print("  [AVISO] Opção inválida, pulando este código.")
            continue

        codebook.set_entry(
            key,
            code_b64=code_b64,
            nec_hex=decoded.hex_code if decoded and decoded.ok else None,
            source="imported_from_app",
            checksum_ok=decoded.checksum_ok if decoded and decoded.ok else None,
        )
        print(f"  [OK] Importado como '{label}'.")


def menu_status():
    print("\n-- Status dos códigos --")
    for label, key in ALL_BUTTONS:
        print(f"  {label:<16} : {status_for(key)}")


def main():
    print("Carregando configuração (.env)...")
    try:
        cfg = load_config()
    except EnvironmentError as e:
        print(f"[ERRO] {e}")
        sys.exit(1)

    client = TuyaIRClient(cfg.endpoint, cfg.access_id, cfg.access_secret, cfg.device_id)

    print(f"Conectando à Tuya Cloud ({cfg.endpoint})...")
    try:
        client.connect()
    except TuyaAuthError as e:
        print(f"[ERRO DE AUTENTICAÇÃO] {e}")
        sys.exit(1)
    print("[OK] Autenticado com sucesso.")

    while True:
        print_main_menu()
        choice = input("Escolha uma opção: ").strip().lower()

        if choice == "q":
            print("Saindo...")
            break
        elif choice == "1":
            menu_enviar(client)
        elif choice == "2":
            menu_aprender(client)
        elif choice == "3":
            menu_inferir(client)
        elif choice == "4":
            menu_status()
        elif choice == "5":
            menu_importar(client)
        elif choice == "m":
            raw_code = input("Digite o código NEC em hex (ex: 00FF02FD): ").strip()
            try:
                resp = client.send_ir_code(raw_code, label="MANUAL")
                print(f"[OK] Código manual 0x{raw_code.upper().replace('0X','')} enviado.")
            except ValueError as e:
                print(f"[ERRO] {e}")
            except TuyaAPIError as e:
                print(f"[FALHA] {e}")
            except Exception as e:
                print(f"[ERRO INESPERADO] {type(e).__name__}: {e}")
        else:
            print("[AVISO] Opção inválida. Tente novamente.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
        sys.exit(0)
