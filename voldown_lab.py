#!/usr/bin/env python3
"""
Laboratorio de testes do VOLUME- -- roda LOCALMENTE (Windows).

VOCE controla cada disparo. Nenhum comando eh enviado sozinho, nunca.

Por que esse script existe
---------------------------
Todas as varreduras anteriores mandaram os candidatos via
`encode_nec()` (sintese do zero: base64+FastLZ, timings 9000/4500/
560/1690). Mas o ESQUERDA provou que isso nao eh confiavel: o codigo
CERTO (0x9B) foi testado por sintese e nao funcionou -- so funcionou
com o payload verbatim do app (hex cru, timings 8889/4513/563/1703).

Ou seja: a varredura pode ter passado pelo codigo certo do VOLUME- e
nao ter disparado nada. Esse script gera os candidatos usando o MOLDE
extraido do codigo verbatim que funciona (byte a byte identico ao que
o app produziu) e manda verbatim, sem passar pela sintese.

TESTES DE CONTROLE (faca esses PRIMEIRO)
------------------------------------------
    b = BAIXO via SINTESE (encode_nec)   <- se NAO funcionar, a sintese
                                            eh o problema, confirmado
    v = BAIXO via MOLDE (hex cru)        <- deve funcionar
    n = BAIXO verbatim do codebook       <- referencia, sempre funciona

Se 'n' funciona e 'b' nao, esta provado que a sintese estava sabotando
toda a varredura anterior.

VARREDURA DO VOLUME- (passo a passo, voce controla)
-----------------------------------------------------
    ESPACO = dispara o PROXIMO candidato da fila e mostra qual foi
    r      = repete o ultimo candidato disparado
    s      = SALVA o ultimo candidato disparado como VOLUME- e sai
    p      = mostra em que posicao da fila voce esta
    j      = pular para um comando especifico (digita o hex, ex: 8B)
    q      = sair

A fila cobre os 256 comandos possiveis, exceto os 14 ja confirmados,
comecando pelos mais plausiveis.
"""
import sys

from config import load_config
from tuya_client import TuyaIRClient, TuyaAPIError
import codebook

# ----------------------------------------------------------------------
# MOLDE extraido do codigo verbatim do ESQUERDA (0x00FF9B64), que
# funciona de verdade no projetor. Reproduz o payload do app byte a
# byte -- validado por comparacao exata.
# ----------------------------------------------------------------------
LEADER_MARK = 8889
LEADER_SPACE = 4513
BIT_MARK = 563
ZERO_SPACE = 563
ONE_SPACE = 1703
STOP_MARK = 563
FINAL_GAP = 64464

KNOWN_COMMAND_BYTES = {
    0x82, 0x88, 0x8C, 0x91, 0x93, 0x95, 0x97,
    0x98, 0x99, 0x9A, 0x9B, 0x9E, 0xA4, 0xA8,
}

# Candidatos mais plausiveis primeiro (vizinhos dos clusters conhecidos)
PRIORITY = [0x8B, 0x8D, 0x8A, 0x8E, 0x8F, 0x90, 0x92, 0x94, 0x96,
            0x9C, 0x9D, 0x9F, 0xAC, 0xA0, 0xA1, 0xA2, 0xA3, 0xA5,
            0xA6, 0xA7, 0xA9, 0xAA, 0xAB, 0x83, 0x84, 0x85, 0x86,
            0x87, 0x89, 0x81, 0x80]


def build_raw_hex(nec_hex: str) -> str:
    """Gera o codigo no formato hex cru da Tuya usando o molde verbatim."""
    nec_hex = nec_hex.lower().replace("0x", "")
    data = bytes.fromhex(nec_hex)
    durations = [LEADER_MARK, LEADER_SPACE]
    for byte in data:
        for bit_index in range(8):  # LSB-first, igual o decoder
            durations.append(BIT_MARK)
            durations.append(ONE_SPACE if (byte >> bit_index) & 1 else ZERO_SPACE)
    durations += [STOP_MARK, FINAL_GAP]
    out = bytearray()
    for v in durations:
        out.append(v & 0xFF)
        out.append((v >> 8) & 0xFF)
    return out.hex()


def nec_from_command(cmd: int) -> str:
    return f"00FF{cmd:02X}{(~cmd) & 0xFF:02X}"


def build_queue():
    queue = []
    seen = set()
    for cmd in PRIORITY:
        if cmd not in KNOWN_COMMAND_BYTES and cmd not in seen:
            seen.add(cmd)
            queue.append(cmd)
    for cmd in range(0x100):
        if cmd not in KNOWN_COMMAND_BYTES and cmd not in seen:
            seen.add(cmd)
            queue.append(cmd)
    return queue


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

    queue = build_queue()
    pos = 0
    last_cmd = None

    def fire_raw(code_hex, descricao):
        try:
            client.send_raw_code(code_hex, label="VOLDOWN_LAB")
            print(f"  -> {descricao}")
        except TuyaAPIError as e:
            print(f"  [ERRO] {e}")

    print(f"\nFila: {len(queue)} candidatos. Aperte ESPACO pra disparar o primeiro.\n")

    while True:
        key = get_key()
        if not key:
            continue

        if key == "q":
            print("Saindo.")
            break

        elif key == "b":
            try:
                client.send_ir_code("00FF9A65", label="CTRL_BAIXO_SINTESE")
                print("  -> [CONTROLE] BAIXO via SINTESE (encode_nec). O cursor desceu?")
            except (TuyaAPIError, ValueError) as e:
                print(f"  [ERRO] {e}")

        elif key == "v":
            fire_raw(build_raw_hex("00FF9A65"),
                     "[CONTROLE] BAIXO via MOLDE (hex cru). O cursor desceu?")

        elif key == "n":
            entry = codebook.get("BAIXO")
            fire_raw(entry["code_b64"],
                     "[CONTROLE] BAIXO verbatim do codebook. O cursor desceu?")

        elif key == " ":
            if pos >= len(queue):
                print("  Fim da fila -- todos os candidatos foram testados.")
                continue
            cmd = queue[pos]
            last_cmd = cmd
            pos += 1
            nec = nec_from_command(cmd)
            fire_raw(build_raw_hex(nec),
                     f"[{pos}/{len(queue)}] candidato 0x{cmd:02X}  (NEC 0x{nec})")

        elif key == "r":
            if last_cmd is None:
                print("  Nenhum candidato disparado ainda.")
                continue
            nec = nec_from_command(last_cmd)
            fire_raw(build_raw_hex(nec), f"[repetindo] 0x{last_cmd:02X}  (NEC 0x{nec})")

        elif key == "j":
            alvo = input("  Comando hex (ex: 8B): ").strip()
            try:
                cmd = int(alvo, 16) & 0xFF
            except ValueError:
                print("  Valor invalido.")
                continue
            last_cmd = cmd
            nec = nec_from_command(cmd)
            fire_raw(build_raw_hex(nec), f"[manual] 0x{cmd:02X}  (NEC 0x{nec})")

        elif key == "p":
            print(f"  Posicao: {pos}/{len(queue)}. Ultimo disparado: "
                  f"{'0x%02X' % last_cmd if last_cmd is not None else 'nenhum'}")

        elif key == "s":
            if last_cmd is None:
                print("  Nenhum candidato disparado ainda -- nada pra salvar.")
                continue
            nec = nec_from_command(last_cmd)
            codebook.set_entry(
                "VOLUME-",
                code_b64=build_raw_hex(nec),
                nec_hex=nec.lower(),
                source="inferred_confirmed",
                checksum_ok=True,
            )
            print(f"\n  [SALVO] VOLUME- = 0x{nec} (comando 0x{last_cmd:02X})")
            print("  Gravado no codebook.json no formato molde (hex cru).")
            break

        else:
            print(f"  (tecla '{key}' nao mapeada)")


if __name__ == "__main__":
    main()
