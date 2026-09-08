"""
Decodificador do formato binário da Tuya para códigos IR.

Faz o caminho inverso de nec_encoder.py: recebe a string que o Hub
retorna quando "aprende" um código de um controle físico e tenta
recuperar:
  1. A lista de durações de pulso (microssegundos).
  2. Se o sinal seguir o protocolo NEC padrão, os 4 bytes
     (endereço, ~endereço, comando, ~comando) em hexadecimal.

Isso permite ver o código hex "real" de um botão do controle físico
(para os botões que funcionam) e comparar padrões de bits entre
botões, o que ajuda a inferir o código dos botões quebrados.

IMPORTANTE — dois formatos de payload coexistem na API da Tuya:
  1. Base64 + FastLZ comprimido (variante nível 1, documentada por
     engenharia reversa em
     https://gist.github.com/mildsunrise/1d576669b63a260d2cff35fda63ec0b5).
     É o formato produzido por nec_encoder.py e usado ao provisionar
     um controle virtual novo (POST .../learning-codes).
  2. Hex cru (sem compressão, sem base64) — pares de bytes little-endian
     representando as durações diretamente. É o formato observado nas
     respostas de GET .../remotes/{remote_id}/learning-codes (usado
     tanto para reenviar comandos aprendidos quanto para importar
     códigos de um controle virtual já existente, ex: criado pelo app
     Tuya Smart/Smart Life).

durations_from_tuya_code() tenta o caminho (1) primeiro e cai para o
caminho (2) se a descompressão falhar, em vez de propagar uma exceção
não tratada.
"""
import base64
from dataclasses import dataclass, field
from typing import List, Optional


# ----------------------------------------------------------------------
# Descompressão FastLZ (variante Tuya)
# ----------------------------------------------------------------------
def fastlz_decompress(data: bytes) -> bytes:
    """
    Descompacta o payload no formato FastLZ usado pela Tuya.

    Formato de cada bloco (header byte):
      - 3 bits mais significativos == 0  -> bloco literal:
            5 bits restantes = comprimento-1 (1 a 32 bytes seguintes)
      - 3 bits mais significativos == 1..6 -> bloco comprimido curto:
            top3 = comprimento-2 (L = top3+2, 3 a 8 bytes)
            distância = ((5 bits restantes) << 8 | próximo byte) + 1
      - 3 bits mais significativos == 7 -> bloco comprimido longo:
            comprimento extra em um byte adicional (L = 9 + extra)
            distância = ((5 bits restantes) << 8 | próximo byte) + 1
    """
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        header = data[i]
        i += 1
        top3 = header >> 5

        if top3 == 0:
            length = (header & 0x1F) + 1
            out += data[i : i + length]
            i += length
        else:
            if top3 == 7:
                extra = data[i]
                i += 1
                length = 9 + extra
            else:
                length = top3 + 2
            dist_hi = header & 0x1F
            dist_lo = data[i]
            i += 1
            distance = ((dist_hi << 8) | dist_lo) + 1

            start = len(out) - distance
            if start < 0:
                raise ValueError("Payload comprimido inválido (distância fora do buffer).")
            for k in range(length):
                out.append(out[start + k])
    return bytes(out)


def durations_from_tuya_code(code: str) -> List[int]:
    """
    Decodifica o código IR da Tuya (base64+FastLZ OU hex cru — ver
    docstring do módulo) em uma lista de durações (microssegundos),
    alternando nível alto/baixo, começando em alto.
    """
    decompressed = None
    try:
        raw = base64.b64decode(code, validate=True)
        decompressed = fastlz_decompress(raw)
    except Exception:
        decompressed = None

    if decompressed is None:
        try:
            decompressed = bytes.fromhex(code)
        except ValueError as exc:
            raise ValueError(
                "Não foi possível interpretar o código: não é base64+FastLZ "
                "válido nem hex cru."
            ) from exc

    if len(decompressed) % 2 != 0:
        decompressed = decompressed[:-1]  # descarta byte solto, se houver
    durations = []
    for j in range(0, len(decompressed), 2):
        value = decompressed[j] | (decompressed[j + 1] << 8)
        durations.append(value)
    return durations


# ----------------------------------------------------------------------
# Decodificação do protocolo NEC a partir das durações
# ----------------------------------------------------------------------
def _within(value: int, target: int, tolerance: int = 250) -> bool:
    return abs(value - target) <= tolerance


@dataclass
class NecDecodeResult:
    ok: bool
    hex_code: Optional[str] = None
    bytes_: Optional[bytes] = None
    address: Optional[int] = None
    address_inv: Optional[int] = None
    command: Optional[int] = None
    command_inv: Optional[int] = None
    checksum_ok: bool = False
    is_repeat_frame: bool = False
    necx2: bool = False
    reason: str = ""
    raw_durations: List[int] = field(default_factory=list)


def decode_nec(durations: List[int]) -> NecDecodeResult:
    """
    Tenta interpretar uma lista de durações (mark/space em us) como um
    frame NEC padrão de 32 bits. Não assume que os bytes de checksum
    (complementos) estão corretos — apenas reporta se estão, para o
    usuário avaliar a confiabilidade da leitura.
    """
    result = NecDecodeResult(ok=False, raw_durations=durations)

    if len(durations) < 4:
        result.reason = "Sinal curto demais para ser um frame NEC."
        return result

    leader_mark, leader_space = durations[0], durations[1]

    # Frame de repetição NEC (usado quando o botão é mantido pressionado)
    if _within(leader_mark, 9000) and _within(leader_space, 2250, 400):
        result.is_repeat_frame = True
        result.reason = "Frame de repetição NEC (sem dados de botão)."
        return result

    necx2 = False
    if _within(leader_mark, 9000) and _within(leader_space, 4500, 400):
        pass
    elif _within(leader_mark, 4500) and _within(leader_space, 4500, 400):
        necx2 = True
    else:
        result.reason = (
            f"Cabeçalho não bate com NEC padrão (mark={leader_mark}us, space={leader_space}us). "
            "Pode ser outro protocolo (RC5, SIRC, protocolo proprietário, etc.)."
        )
        return result

    bit_pairs = durations[2:66]  # 32 bits * 2 valores = 64 durações
    if len(bit_pairs) < 64:
        result.reason = f"Frame incompleto: esperava 64 durações de dados, recebeu {len(bit_pairs)}."
        return result

    bits = []
    for i in range(32):
        mark = bit_pairs[2 * i]
        space = bit_pairs[2 * i + 1]
        if not _within(mark, 560, 250):
            result.reason = f"Pulso de bit #{i} fora do padrão NEC (mark={mark}us)."
            return result
        if _within(space, 560, 250):
            bits.append(0)
        elif _within(space, 1690, 350):
            bits.append(1)
        else:
            result.reason = f"Espaço de bit #{i} ambíguo ({space}us) — não bate com 0 nem 1."
            return result

    data = bytearray()
    for byte_index in range(4):
        byte_val = 0
        for bit_index in range(8):
            if bits[byte_index * 8 + bit_index]:
                byte_val |= 1 << bit_index
        data.append(byte_val)

    addr, addr_inv, cmd, cmd_inv = data
    checksum_ok = (addr ^ addr_inv == 0xFF) and (cmd ^ cmd_inv == 0xFF)

    result.ok = True
    result.hex_code = data.hex()
    result.bytes_ = bytes(data)
    result.address = addr
    result.address_inv = addr_inv
    result.command = cmd
    result.command_inv = cmd_inv
    result.checksum_ok = checksum_ok
    result.necx2 = necx2
    result.reason = "OK" if checksum_ok else "Decodificado, mas checksum (complementos) não bate — confira manualmente."
    return result


def decode_tuya_code(code: str) -> NecDecodeResult:
    """Atalho: código da Tuya (base64+FastLZ ou hex cru) -> resultado da decodificação NEC."""
    durations = durations_from_tuya_code(code)
    return decode_nec(durations)


if __name__ == "__main__":
    import sys
    from nec_encoder import encode_nec

    # Auto-teste: codifica um código conhecido e decodifica de volta
    test_hex = sys.argv[1] if len(sys.argv) > 1 else "00FF02FD"
    encoded = encode_nec(test_hex)
    decoded = decode_tuya_code(encoded)
    print(f"Original: {test_hex}")
    print(f"Base64:   {encoded}")
    print(f"Decodificado: {decoded.hex_code} (checksum_ok={decoded.checksum_ok}, reason={decoded.reason})")
    assert decoded.hex_code == test_hex.lower().replace("0x", ""), "Round-trip falhou!"
    print("ROUND-TRIP OK")
