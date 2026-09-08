"""
Heurísticas para "chutar" o código NEC de um botão fisicamente quebrado
(que nunca vai transmitir nada, então não dá pra capturar por
aprendizado), a partir de códigos já aprendidos de botões vizinhos que
funcionam no mesmo controle físico.

Importante: isto é uma estimativa, não uma leitura real. O fluxo
recomendado é gerar alguns candidatos plausíveis e testá-los um a um
direto no aparelho (apontando o Hub pra ele) até um funcionar. Depois
de confirmado visualmente, o código é salvo no codebook como
"source: inferred_confirmed".

Racional das heurísticas
--------------------------
Em controles remotos baratos com protocolo NEC, o byte de "endereço"
é fixo para todos os botões do mesmo controle — só o byte de "comando"
muda. Além disso, é muito comum que o chip do controle mapeie botões
fisicamente adjacentes (setas, volume+/-, canal+/-) trocando apenas
1 ou 2 bits do comando entre si, porque o layout do teclado matricial
do controle tende a virar diretamente os bits do código. Por isso:

  1. Se sabemos Up/Down/Right mas não Left, calculamos que bit(s)
     diferenciam Up de Down, e testamos se aplicar essa mesma
     diferença a Right (ou a Down) produz um valor plausível.
  2. Se sabemos Volume+ mas não Volume-, usamos o mesmo "bit de
     toggle" observado em outro par conhecido do mesmo controle
     (ex: Up/Down) como primeiro palpite, já que costuma ser uma
     característica do chip, não do par específico de botões.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import codebook
from nec_decoder import decode_tuya_code


@dataclass
class Candidate:
    hex_code: str
    reason: str


def _get_decoded_command(button_name: str) -> Optional[Tuple[int, int, bool]]:
    """Retorna (address, command, checksum_ok) de um botão já aprendido, se possível."""
    entry = codebook.get(button_name)
    if not entry:
        return None
    if entry.get("nec_hex"):
        hex_code = entry["nec_hex"]
    else:
        decoded = decode_tuya_code(entry["code_b64"])
        if not decoded.ok:
            return None
        hex_code = decoded.hex_code
    raw = bytes.fromhex(hex_code)
    addr, addr_inv, cmd, cmd_inv = raw
    checksum_ok = (addr ^ addr_inv == 0xFF) and (cmd ^ cmd_inv == 0xFF)
    return addr, cmd, checksum_ok


def _build_hex(address: int, command: int) -> str:
    """Monta um código NEC completo de 32 bits com complementos corretos."""
    addr_inv = (~address) & 0xFF
    cmd_inv = (~command) & 0xFF
    return bytes([address, addr_inv, command, cmd_inv]).hex()


def _rank_by_bit_simplicity(base: int, candidates: set) -> List[int]:
    """Prioriza candidatos que diferem do valor base por menos bits (mudança 'mais simples')."""
    def popcount(x):
        return bin(x).count("1")

    return sorted(candidates, key=lambda c: popcount(c ^ base))


def infer_from_cluster(
    target: str,
    known_siblings: List[str],
    extra_hint_pair: Optional[Tuple[str, str]] = None,
    max_candidates: int = 6,
) -> Tuple[List[Candidate], Optional[int]]:
    """
    Gera candidatos de comando (byte único) para `target`, a partir de
    botões vizinhos já aprendidos (`known_siblings`).

    extra_hint_pair: nomes de dois botões de OUTRO par conhecido no
    mesmo controle (ex: ("CIMA", "BAIXO")) cujo bit de diferença será
    reaproveitado como palpite adicional — útil quando `target` não
    tem nenhum irmão capturado (ex: Volume-, só temos Volume+).

    Returns:
        (lista de Candidate ordenada por probabilidade, address usado)
    """
    known_data = {}
    address = None
    for name in known_siblings:
        info = _get_decoded_command(name)
        if info:
            addr, cmd, _ = info
            known_data[name] = cmd
            address = addr  # assume mesmo endereço em todos os botões do controle

    if address is None:
        return [], None

    candidate_bytes = set()
    reasons = {}

    def add(value: int, reason: str):
        value &= 0xFF
        candidate_bytes.add(value)
        reasons.setdefault(value, reason)

    # Heurística 1: diferença de bit entre pares conhecidos, aplicada
    # ao vizinho mais próximo disponível.
    names = list(known_data.keys())
    for i in range(len(names)):
        for j in range(len(names)):
            if i == j:
                continue
            a, b = known_data[names[i]], known_data[names[j]]
            diff = a ^ b
            if bin(diff).count("1") <= 2:  # só considera diferenças "simples"
                # aplica a mesma diferença a partir de cada vizinho conhecido
                for k, v in known_data.items():
                    add(v ^ diff, f"toggle observado entre {names[i]}/{names[j]} aplicado a {k}")

    # Heurística 2: +-1 e +-2 em relação a cada vizinho (numeração sequencial)
    for k, v in known_data.items():
        add(v + 1, f"{k} + 1 (numeração sequencial)")
        add(v - 1, f"{k} - 1 (numeração sequencial)")
        add(v ^ 0x01, f"{k} com bit 0 invertido")
        add(v ^ 0x02, f"{k} com bit 1 invertido")

    # Heurística 3: reaproveita o bit de toggle de outro par conhecido no controle
    if extra_hint_pair:
        info_a = _get_decoded_command(extra_hint_pair[0])
        info_b = _get_decoded_command(extra_hint_pair[1])
        if info_a and info_b:
            hint_diff = info_a[1] ^ info_b[1]
            for k, v in known_data.items():
                add(
                    v ^ hint_diff,
                    f"reaproveitando o bit de diferença entre {extra_hint_pair[0]}/{extra_hint_pair[1]} "
                    f"(0x{hint_diff:02X}) aplicado a {k}",
                )

    # Remove candidatos que já são um botão conhecido (não seria "novo")
    known_values = set(known_data.values())
    candidate_bytes -= known_values

    if not candidate_bytes:
        return [], address

    ordered = _rank_by_bit_simplicity(next(iter(known_data.values())), candidate_bytes)
    candidates = [Candidate(_build_hex(address, v), reasons[v]) for v in ordered[:max_candidates]]
    return candidates, address


# Configuração específica para os dois botões quebrados do controle do AUN ET30
def infer_esquerda() -> List[Candidate]:
    return infer_from_cluster(
        target="ESQUERDA",
        known_siblings=[n for n in ("CIMA", "BAIXO", "DIREITA") if codebook.get(n)],
        extra_hint_pair=("CIMA", "BAIXO") if codebook.get("CIMA") and codebook.get("BAIXO") else None,
    )[0]


def infer_volume_down() -> List[Candidate]:
    return infer_from_cluster(
        target="VOLUME-",
        known_siblings=[n for n in ("VOLUME+",) if codebook.get(n)],
        extra_hint_pair=("CIMA", "BAIXO") if codebook.get("CIMA") and codebook.get("BAIXO") else None,
    )[0]
