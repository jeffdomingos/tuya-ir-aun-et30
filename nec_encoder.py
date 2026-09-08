"""
Encoder de codigos NEC (protocolo IR de 38 kHz) para o formato que a
Tuya usa nos endpoints "learning-codes" dos Hubs Smart IR.

ATENCAO -- formato correto (descoberto testando contra o Hub real)
-------------------------------------------------------------------
Existem DOIS formatos circulando na API da Tuya:

  1. base64 + FastLZ comprimido  -- documentado em varios projetos de
     engenharia reversa, e o que este modulo gerava originalmente.
  2. hex cru (duracoes uint16 little-endian, sem compressao, sem
     base64) -- e o que o endpoint
     POST /v2.0/infrareds/{id}/remotes/{remote_id}/learning-codes
     realmente emite neste Hub.

O formato (1) e ACEITO pela API (responde success: true) mas o Hub
**nao emite o IR corretamente** -- falha silenciosa. Isso invalidou
uma varredura inteira de 256 comandos: o codigo certo do botao
ESQUERDA (0x00FF9B64) foi testado por sintese e "nao funcionou",
quando na verdade o payload e que estava no formato errado. O mesmo
codigo, enviado verbatim em hex cru, funciona perfeitamente.

Por isso `encode_nec()` agora gera o formato (2) por padrao.

Os timings usados sao os do MOLDE extraido de um codigo real que
funciona neste projetor (capturado via o app Tuya). Gerar o
0x00FF9B64 com esse molde produz um payload **byte a byte identico**
ao que o app produziu -- validado por comparacao exata.

Referencias:
- Timings do protocolo NEC: https://www.sbprojects.net/knowledge/ir/nec.php
- Formato comprimido da Tuya (engenharia reversa):
  https://gist.github.com/mildsunrise/1d576669b63a260d2cff35fda63ec0b5
"""
import base64
import re

# ----------------------------------------------------------------------
# Timings do MOLDE -- extraidos de um codigo real capturado pelo app
# Tuya para este projetor e validados ao vivo no hardware.
# Nao sao os valores "de livro" do NEC (9000/4500/560/1690), e sim os
# valores reais que o Hub/projetor aceitam.
# ----------------------------------------------------------------------
LEADER_MARK = 8889
LEADER_SPACE = 4513
BIT_MARK = 563
ZERO_SPACE = 563
ONE_SPACE = 1703
STOP_MARK = 563
FINAL_GAP = 64464

# Variante NECx2 (leader mark curto), mantida para dispositivos que a usem
LEADER_MARK_NECX2 = 4500

# Timings "de livro", usados apenas pelo encoder legado em base64
_STD_LEADER_MARK = 9000
_STD_LEADER_SPACE = 4500
_STD_BIT_MARK = 560
_STD_ZERO_SPACE = 1125 - _STD_BIT_MARK
_STD_ONE_SPACE = 2250 - _STD_BIT_MARK


def _le16(value: int) -> bytes:
    """Codifica um inteiro em little-endian de 16 bits (2 bytes)."""
    value &= 0xFFFF
    return bytes([value & 0xFF, value >> 8])


def normalize_hex(hex_code: str) -> str:
    """Remove prefixos (0x), espacos e underscores, e valida o formato."""
    cleaned = re.sub(r"(0x|0X|\s|_)", "", hex_code.strip())
    if not re.fullmatch(r"[0-9a-fA-F]{8}", cleaned):
        raise ValueError(
            f"Codigo NEC invalido: '{hex_code}'. "
            "Use 8 digitos hexadecimais (4 bytes), ex: 00FF02FD ou 0x00FF02FD."
        )
    return cleaned.lower()


def durations_for(hex_code: str, necx2: bool = False) -> list:
    """Lista de duracoes (us) do frame NEC completo, usando o molde."""
    data = bytes.fromhex(normalize_hex(hex_code))
    leader_mark = LEADER_MARK_NECX2 if necx2 else LEADER_MARK
    durations = [leader_mark, LEADER_SPACE]
    for byte in data:
        for bit_index in range(8):  # NEC transmite LSB-first
            durations.append(BIT_MARK)
            durations.append(ONE_SPACE if (byte >> bit_index) & 1 else ZERO_SPACE)
    durations.append(STOP_MARK)
    durations.append(FINAL_GAP)
    return durations


def encode_nec(hex_code: str, necx2: bool = False) -> str:
    """
    Converte um codigo NEC de 32 bits (endereco, ~endereco, comando,
    ~comando) no payload que o Hub realmente emite: hex cru, com as
    duracoes em uint16 little-endian.

    Args:
        hex_code: codigo NEC em hex, 8 digitos (ex: "00FF02FD").
        necx2: True para a variante NECx2 (leader mark de 4500us).

    Returns:
        String hex pronta para o campo "code" dos endpoints
        .../learning-codes.
    """
    out = bytearray()
    for value in durations_for(hex_code, necx2=necx2):
        out += _le16(value)
    return out.hex()


def encode_nec_base64_legacy(hex_code: str, necx2: bool = False) -> str:
    """
    Encoder ANTIGO: base64 + FastLZ (apenas blocos literais), com os
    timings "de livro" do NEC.

    Mantido so para referencia e para decodificacao de payloads antigos.
    **Nao use para enviar comandos** -- a API aceita, mas este Hub nao
    emite o IR corretamente com esse formato. Veja o cabecalho do
    modulo.
    """
    data = bytes.fromhex(normalize_hex(hex_code))
    leader_mark = LEADER_MARK_NECX2 if necx2 else _STD_LEADER_MARK

    output = bytearray()
    output.append(4 - 1)  # bloco literal: leader mark + leader space
    output += _le16(leader_mark)
    output += _le16(_STD_LEADER_SPACE)

    for byte in data:
        output.append(32 - 1)  # 8 bits * 2 valores * 2 bytes
        for i in range(8):
            output += _le16(_STD_BIT_MARK)
            output += _le16(_STD_ONE_SPACE if byte & (1 << i) else _STD_ZERO_SPACE)

    output.append(2 - 1)
    output += _le16(_STD_BIT_MARK)

    return base64.b64encode(bytes(output)).decode()


if __name__ == "__main__":
    import sys

    code = sys.argv[1] if len(sys.argv) > 1 else "00FF9B64"
    print(f"NEC {code}")
    print(f"  hex cru (formato correto): {encode_nec(code)}")
    print(f"  base64 legado (NAO usar):  {encode_nec_base64_legacy(code)}")

    # Auto-teste: o molde deve reproduzir exatamente o payload real do
    # botao ESQUERDA capturado pelo app.
    esquerda_verbatim = (
        "b922a11133023302330233023302330233023302330233023302330233023302330233"
        "023302a7063302a7063302a7063302a7063302a7063302a7063302a7063302a7063302"
        "a7063302a706330233023302a7063302a70633023302330233023302a7063302330233"
        "0233023302a70633023302330233023302a7063302a706330233023302d0fb"
    )
    gerado = encode_nec("00FF9B64")
    assert gerado == esquerda_verbatim, "Molde nao bate com o codigo real!"
    print("\nROUND-TRIP OK: molde reproduz o ESQUERDA verbatim byte a byte.")
