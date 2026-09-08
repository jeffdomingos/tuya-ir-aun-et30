#!/usr/bin/env python3
"""
Varredura em lote (rodar LOCALMENTE, fora do CLI principal) pra achar os
codigos NEC que faltam: VOLUME- e ESQUERDA.

Por que existe esse script separado
------------------------------------
O agente que ajudou a montar isso tem um limite de ~40s por comando de
terminal, o que obriga a quebrar a varredura em lotes pequenos e pedir
confirmacao a cada lote -- lento e cansativo. Rodando local, voce deixa
o loop rolando sozinho e so aperta Ctrl+C no instante exato em que o
projetor reagir (mudou o volume / cursor foi pra esquerda).

O que ja foi descartado (nao esta na lista de novo)
------------------------------------------------------
- ESQUERDA: TODOS os 256 comandos possiveis no endereco 0x00 (mesmo
  endereco dos outros 13 botoes confirmados) ja foram testados sem
  sucesso. Por isso, os candidatos de ESQUERDA aqui usam ENDERECOS
  alternativos (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80) --
  hipotese de que o botao caiu numa trilha separada da matriz do
  controle (comum em placas baratas com pouco espaco).
- VOLUME-: reenvia o range inteiro no endereco 0x00 (exceto os 13
  comandos ja confirmados). ABRA a barra de volume antes (aperte
  Volume+ no controle) pra garantir que vai dar pra ver a reacao.

Controle de velocidade / rate limit
-------------------------------------
Comeca com 0.6s entre disparos. Se a API da Tuya recusar por excesso de
requisicoes (HTTP 429, ou erro da Tuya tipo "too many requests" /
"frequently"), o script pausa 3s, AUMENTA o delay padrao em +0.2s (pra
sempre, nao so dessa vez) e reenvia o mesmo codigo que falhou antes de
seguir pra frente -- assim nenhum candidato eh pulado por causa de rate
limit.

Como usar
---------
1. Aponte o Hub Smart IR pro projetor.
2. Se for procurar VOLUME-, deixe a barra de volume visivel na tela
   (aperte Volume+ uma vez antes de rodar, se precisar).
3. Rode: python scan_missing_buttons.py
4. Fique de olho na tela. No INSTANTE em que o projetor reagir
   (cursor foi pra esquerda OU volume mudou), aperte Ctrl+C.
5. O script imprime destacado qual foi o ultimo codigo enviado --
   esse eh o candidato certo. Anote o codigo hex mostrado.
"""
import sys
import time

from config import load_config
from tuya_client import TuyaIRClient, TuyaAPIError

# ----------------------------------------------------------------------
# Comandos ja confirmados -- NUNCA reenviar como "candidato", so serve
# pra excluir da lista de busca.
# ----------------------------------------------------------------------
KNOWN_COMMAND_BYTES = {
    0x82,  # FORWARD
    0x88,  # MUTE
    0x8C,  # VOLUME+
    0x91,  # MENU
    0x93,  # PLAY_PAUSE
    0x95,  # CIMA
    0x97,  # INPUT
    0x98,  # REWIND
    0x99,  # DIREITA
    0x9A,  # BAIXO
    0x9E,  # OK
    0xA4,  # VOLTAR
    0xA8,  # POWER
}

INITIAL_DELAY_SECONDS = 0.6
DELAY_STEP_ON_RATE_LIMIT = 0.2
RATE_LIMIT_PAUSE_SECONDS = 3.0

# Palavras que costumam aparecer na mensagem de erro da Tuya quando o
# problema eh excesso de requisicoes (varia conforme a regiao/versao da
# API, entao checa varias variantes).
RATE_LIMIT_HINTS = (
    "too many",
    "too frequent",
    "frequently",
    "frequent",
    "429",
    "qps",
    "rate limit",
    "over the limit",
)


def build_nec_hex(address: int, command: int) -> str:
    """Monta um codigo NEC de 32 bits (addr, ~addr, cmd, ~cmd) em hex."""
    addr_inv = (~address) & 0xFF
    cmd_inv = (~command) & 0xFF
    return f"{address:02X}{addr_inv:02X}{command:02X}{cmd_inv:02X}"


def build_candidate_list():
    """
    Retorna lista de tuplas (hex_code, label) com todos os candidatos
    restantes de VOLUME- e ESQUERDA, sem duplicatas.
    """
    candidates = []
    seen = set()

    def add(hex_code: str, label: str):
        if hex_code not in seen:
            seen.add(hex_code)
            candidates.append((hex_code, label))

    # --- VOLUME-: varredura completa no endereco 0x00, exceto os ja
    # conhecidos. Prioriza os "suspeitos" (proximos de VOLUME+ e do
    # padrao POWER/MUTE) antes do resto.
    priority_cmds = [0xAC, 0x8D, 0x8B, 0x8E, 0x90, 0x92, 0x94, 0x96]
    for cmd in priority_cmds:
        if cmd not in KNOWN_COMMAND_BYTES:
            add(build_nec_hex(0x00, cmd), f"VOLUME- candidato prioritario (cmd=0x{cmd:02X})")

    for cmd in range(0x00, 0x100):
        if cmd in KNOWN_COMMAND_BYTES:
            continue
        add(build_nec_hex(0x00, cmd), f"VOLUME- varredura endereco 0x00 (cmd=0x{cmd:02X})")

    # --- ESQUERDA: endereco 0x00 ja foi 100% varrido sem sucesso antes
    # (nao repete aqui). Testa enderecos alternativos com os comandos
    # mais plausiveis.
    alt_addresses = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80]
    esquerda_cmd_guesses = [0x69, 0x6B, 0x64, 0x96, 0x94, 0x9B, 0x66, 0x99, 0x9A, 0x95]
    for addr in alt_addresses:
        for cmd in esquerda_cmd_guesses:
            add(
                build_nec_hex(addr, cmd),
                f"ESQUERDA endereco alternativo 0x{addr:02X} (cmd=0x{cmd:02X})",
            )

    return candidates


def looks_like_rate_limit(exc: Exception) -> bool:
    """Tenta identificar se uma excecao veio de excesso de requisicoes."""
    text = str(exc).lower()
    return any(hint in text for hint in RATE_LIMIT_HINTS)


class DelayState:
    """Guarda o delay atual (mutavel, pode subir permanentemente)."""

    def __init__(self, initial: float):
        self.value = initial

    def bump(self, step: float):
        self.value += step


def send_one(client, hex_code: str, label: str, delay_state: DelayState) -> bool:
    """
    Envia um candidato, com retry automatico em caso de rate limit.
    Retorna True se o envio (eventualmente) deu certo, False se foi um
    erro real (nao relacionado a rate limit) que nao adianta repetir.
    """
    while True:
        try:
            resp = client.send_ir_code(hex_code, label=label)
        except TuyaAPIError as e:
            if looks_like_rate_limit(e):
                print(f"  [RATE LIMIT] {e} -- pausando {RATE_LIMIT_PAUSE_SECONDS}s e "
                      f"aumentando delay padrao em +{DELAY_STEP_ON_RATE_LIMIT}s...")
                time.sleep(RATE_LIMIT_PAUSE_SECONDS)
                delay_state.bump(DELAY_STEP_ON_RATE_LIMIT)
                continue
            print(f"  [ERRO API] {e} -- pulando este candidato.")
            return False
        except ValueError as e:
            print(f"  [CODIGO INVALIDO] {e} -- pulando este candidato.")
            return False
        except Exception as e:
            # resp veio None (ex: HTTP 429 sem corpo JSON tratavel) ou
            # outro problema de transporte -- trata como rate limit,
            # pausa e tenta de novo em vez de perder o candidato.
            if looks_like_rate_limit(e):
                print(f"  [RATE LIMIT] {type(e).__name__}: {e} -- pausando "
                      f"{RATE_LIMIT_PAUSE_SECONDS}s e aumentando delay padrao em "
                      f"+{DELAY_STEP_ON_RATE_LIMIT}s...")
            else:
                print(f"  [FALHA DE TRANSPORTE] {type(e).__name__}: {e} -- tratando como "
                      f"possivel rate limit. Pausando {RATE_LIMIT_PAUSE_SECONDS}s e "
                      f"aumentando delay padrao em +{DELAY_STEP_ON_RATE_LIMIT}s...")
            time.sleep(RATE_LIMIT_PAUSE_SECONDS)
            delay_state.bump(DELAY_STEP_ON_RATE_LIMIT)
            continue
        else:
            if resp is None:
                print(f"  [RATE LIMIT] resposta vazia da API -- pausando "
                      f"{RATE_LIMIT_PAUSE_SECONDS}s e aumentando delay padrao em "
                      f"+{DELAY_STEP_ON_RATE_LIMIT}s...")
                time.sleep(RATE_LIMIT_PAUSE_SECONDS)
                delay_state.bump(DELAY_STEP_ON_RATE_LIMIT)
                continue
            return True


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
    print("[OK] Autenticado com sucesso.\n")

    candidates = build_candidate_list()
    total = len(candidates)
    delay_state = DelayState(INITIAL_DELAY_SECONDS)

    print(f"{total} candidatos na fila (VOLUME- + ESQUERDA endereco alternativo).")
    print(f"Delay inicial entre disparos: {delay_state.value:.1f}s (sobe +{DELAY_STEP_ON_RATE_LIMIT}s "
          f"a cada rate limit detectado).")
    print("Aponte o Hub pro projetor. Quando o projetor reagir, aperte Ctrl+C IMEDIATAMENTE.\n")
    input("Pressione ENTER pra comecar...")

    last_sent = None
    try:
        for i, (hex_code, label) in enumerate(candidates, start=1):
            last_sent = (hex_code, label)
            print(f"Enviando candidato {i} de {total} codigo 0x{hex_code} ({label})")
            send_one(client, hex_code, label=f"SCAN_{i}", delay_state=delay_state)
            time.sleep(delay_state.value)
        print("\nVarredura completa terminou sem interrupcao. Nenhum candidato foi confirmado.")
    except KeyboardInterrupt:
        print("\n" + "=" * 70)
        if last_sent:
            hex_code, label = last_sent
            print(f"Busca interrompida. O ultimo codigo enviado foi 0x{hex_code}")
            print(f"  -> {label}")
        else:
            print("Busca interrompida. Nenhum codigo tinha sido enviado ainda.")
        print("=" * 70)
        print("\nAnote esse codigo e me avisa (ou salve direto no codebook.json).")
        sys.exit(0)


if __name__ == "__main__":
    main()
